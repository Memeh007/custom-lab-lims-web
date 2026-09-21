"""
Per-lab SQLite routing.

Layout:
  data/labs_registry.json  — { "active": "CODE", "labs": [{code, name, path}] }
  data/labs/<LAB_CODE>/lab.db
  data/lab_lims.db         — legacy single-DB (migrated on first use)

Thread-safe enough for local FastAPI (lock around cache swap).
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LABS_DIR = DATA_DIR / "labs"
REGISTRY_PATH = DATA_DIR / "labs_registry.json"
LEGACY_DB = DATA_DIR / "lab_lims.db"

_LAB_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
_lock = threading.RLock()


def validate_lab_code(code: str) -> str:
    code = (code or "").strip().upper()
    if not _LAB_CODE_RE.match(code):
        raise ValueError(
            "Lab code must start with a letter and contain only A–Z, 0–9, underscore (max 32)."
        )
    return code


def lab_db_path(code: str) -> Path:
    code = validate_lab_code(code)
    return LABS_DIR / code / "lab.db"


def _default_registry() -> dict[str, Any]:
    return {"active": None, "labs": []}


def load_registry() -> dict[str, Any]:
    with _lock:
        if not REGISTRY_PATH.exists():
            return _default_registry()
        try:
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return _default_registry()
        if not isinstance(data, dict):
            return _default_registry()
        data.setdefault("active", None)
        data.setdefault("labs", [])
        if not isinstance(data["labs"], list):
            data["labs"] = []
        return data


def save_registry(reg: dict[str, Any]) -> None:
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = REGISTRY_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
        tmp.replace(REGISTRY_PATH)


def _peek_legacy_code(db_path: Path) -> Optional[tuple[str, str]]:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT lab_code, lab_name FROM lab_config WHERE id = 1"
            ).fetchone()
            if row and row[0]:
                return str(row[0]).strip().upper(), (row[1] or str(row[0])).strip()
        finally:
            conn.close()
    except Exception:
        pass
    return None


def ensure_labs_layout() -> dict[str, Any]:
    """Migrate legacy DB if needed; return current registry."""
    with _lock:
        LABS_DIR.mkdir(parents=True, exist_ok=True)
        reg = load_registry()

        # Already registered
        if reg.get("labs"):
            # Ensure active points at a known lab
            codes = {x.get("code") for x in reg["labs"] if isinstance(x, dict)}
            if reg.get("active") not in codes:
                reg["active"] = next(iter(codes), None)
                save_registry(reg)
            return reg

        # Migrate legacy single DB when it has a configured lab
        peeked = _peek_legacy_code(LEGACY_DB)
        if peeked:
            code, name = peeked
            try:
                code = validate_lab_code(code)
            except ValueError:
                code = "LEGACY"
                name = name or "Migrated Lab"
            dest = lab_db_path(code)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(LEGACY_DB, dest)
            # Keep legacy file as inactive backup (do not delete user data)
            rel = str(dest.relative_to(ROOT)).replace("\\", "/")
            reg = {
                "active": code,
                "labs": [{"code": code, "name": name, "path": rel}],
            }
            save_registry(reg)
        return reg


def resolve_active_db_path() -> Path:
    """Return SQLite path for the active lab (or legacy path pre-setup)."""
    reg = ensure_labs_layout()
    active = reg.get("active")
    if active:
        for lab in reg.get("labs") or []:
            if isinstance(lab, dict) and lab.get("code") == active:
                p = lab.get("path") or str(lab_db_path(active).relative_to(ROOT))
                path = Path(p)
                if not path.is_absolute():
                    path = ROOT / path
                path.parent.mkdir(parents=True, exist_ok=True)
                return path
        # Active code known but missing entry — fall through to lab_db_path
        path = lab_db_path(active)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # Pre-setup / empty registry: use legacy path so wizard can write
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return LEGACY_DB


def register_lab(code: str, name: str, *, make_active: bool = True) -> Path:
    """Ensure labs/<code>/lab.db exists and is listed in the registry."""
    code = validate_lab_code(code)
    name = (name or code).strip()
    path = lab_db_path(code)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _lock:
        reg = ensure_labs_layout()
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        found = False
        for lab in reg["labs"]:
            if lab.get("code") == code:
                lab["name"] = name
                lab["path"] = rel
                found = True
                break
        if not found:
            reg["labs"].append({"code": code, "name": name, "path": rel})
        if make_active or not reg.get("active"):
            reg["active"] = code
        save_registry(reg)

        # If we were writing to legacy during first setup, move it into place
        if LEGACY_DB.exists() and path.resolve() != LEGACY_DB.resolve():
            if not path.exists() or path.stat().st_size < LEGACY_DB.stat().st_size:
                shutil.copy2(LEGACY_DB, path)

    return path


def create_empty_lab(code: str, name: str) -> Path:
    """Create a brand-new empty lab DB (schema only) and register it (not auto-active)."""
    from db import Database  # local import avoids cycle at module load

    code = validate_lab_code(code)
    name = (name or code).strip()
    path = lab_db_path(code)
    if path.exists():
        raise ValueError(f"Lab '{code}' already exists on disk.")
    with _lock:
        reg = ensure_labs_layout()
        if any(l.get("code") == code for l in reg.get("labs") or []):
            raise ValueError(f"Lab '{code}' is already registered.")
        path.parent.mkdir(parents=True, exist_ok=True)
        Database(path)  # creates schema
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        reg["labs"].append({"code": code, "name": name, "path": rel})
        save_registry(reg)
    return path


def switch_active_lab(code: str) -> Path:
    code = validate_lab_code(code)
    with _lock:
        reg = ensure_labs_layout()
        match = next((l for l in reg["labs"] if l.get("code") == code), None)
        if not match:
            raise ValueError(f"Unknown lab '{code}'.")
        reg["active"] = code
        save_registry(reg)
        # Invalidate DB cache in db module
        try:
            from db import reset_db_cache

            reset_db_cache()
        except Exception:
            pass
        p = Path(match["path"])
        if not p.is_absolute():
            p = ROOT / p
        return p


def list_labs() -> list[dict[str, Any]]:
    reg = ensure_labs_layout()
    active = reg.get("active")
    out = []
    for lab in reg.get("labs") or []:
        if not isinstance(lab, dict):
            continue
        item = dict(lab)
        item["is_active"] = item.get("code") == active
        out.append(item)
    return out


def active_lab_code() -> Optional[str]:
    return ensure_labs_layout().get("active")


def update_lab_display_name(code: str, name: str) -> None:
    code = validate_lab_code(code)
    with _lock:
        reg = load_registry()
        for lab in reg.get("labs") or []:
            if lab.get("code") == code:
                lab["name"] = name.strip() or code
                save_registry(reg)
                return
