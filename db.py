"""
Custom Lab LIMS — SQLite database layer.
Universal schema for any lab type.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "lab_lims.db"

DEFAULT_MODULES = {
    "samples": True,
    "experiments": True,
    "compounds": True,
    "protocols": True,
    "husbandry": True,
    "bioinformatics": True,
    "proteins": True,
    "analytics": True,
    "users": True,
    "audit": True,
}

LAB_TYPE_OPTIONS = [
    "General",
    "Cell culture",
    "Microbiology",
    "Biochemistry",
    "Computational biology",
    "Animal colony",
    "Clinical research",
    "Materials",
    "Other",
]

HUSBANDRY_LABEL_OPTIONS = [
    "Organisms",
    "Colonies",
    "Cultures",
    "Animals",
    "Cells",
]

ASSAY_TYPE_SUGGESTIONS = [
    "viability",
    "growth",
    "binding",
    "sequencing_qc",
    "toxicity",
    "enzyme_activity",
    "expression",
    "custom",
    "other",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class Database:
    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            c = conn.cursor()
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS lab_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    lab_name TEXT NOT NULL,
                    lab_code TEXT NOT NULL,
                    primary_color TEXT NOT NULL DEFAULT '#2563eb',
                    accent_color TEXT NOT NULL DEFAULT '#0d9488',
                    timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles',
                    logo_path TEXT,
                    lab_type TEXT DEFAULT 'General',
                    husbandry_label TEXT DEFAULT 'Organisms',
                    modules TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'researcher', 'viewer')),
                    display_name TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sample_type TEXT DEFAULT 'general',
                    quantity REAL DEFAULT 0,
                    unit TEXT DEFAULT 'units',
                    location TEXT,
                    status TEXT DEFAULT 'available',
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS compounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    status TEXT DEFAULT 'active',
                    mw REAL,
                    smiles TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS assays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    compound_id INTEGER,
                    assay_type TEXT NOT NULL DEFAULT 'other',
                    dose REAL,
                    survival_percent REAL,
                    notes TEXT,
                    assay_date TEXT NOT NULL,
                    researcher TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS husbandry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_date TEXT NOT NULL,
                    researcher TEXT,
                    organism_label TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    notes TEXT,
                    related_compound_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (related_compound_id) REFERENCES compounds(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS protocols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    content TEXT,
                    author TEXT,
                    version INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proteins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accession TEXT,
                    name TEXT NOT NULL,
                    organism TEXT,
                    source TEXT,
                    local_path TEXT,
                    sequence TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    role TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_assays_compound ON assays(compound_id);
                CREATE INDEX IF NOT EXISTS idx_husbandry_compound ON husbandry_events(related_compound_id);
                CREATE INDEX IF NOT EXISTS idx_proteins_accession ON proteins(accession);
                CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp);
                """
            )
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        # lab_config new columns
        cols = {r[1] for r in conn.execute("PRAGMA table_info(lab_config)").fetchall()}
        if cols:
            if "lab_type" not in cols:
                conn.execute(
                    "ALTER TABLE lab_config ADD COLUMN lab_type TEXT DEFAULT 'General'"
                )
            if "husbandry_label" not in cols:
                conn.execute(
                    "ALTER TABLE lab_config ADD COLUMN husbandry_label TEXT DEFAULT 'Organisms'"
                )

        # Relax old assays CHECK (viability/regeneration/other)
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='assays'"
        ).fetchone()
        if row and row[0] and "CHECK" in row[0] and "regeneration" in row[0]:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS assays_mig (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    compound_id INTEGER,
                    assay_type TEXT NOT NULL DEFAULT 'other',
                    dose REAL,
                    survival_percent REAL,
                    notes TEXT,
                    assay_date TEXT NOT NULL,
                    researcher TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE SET NULL
                );
                INSERT INTO assays_mig
                    (id, compound_id, assay_type, dose, survival_percent, notes,
                     assay_date, researcher, created_at)
                SELECT id, compound_id, assay_type, dose, survival_percent, notes,
                       assay_date, researcher, created_at FROM assays;
                DROP TABLE assays;
                ALTER TABLE assays_mig RENAME TO assays;
                CREATE INDEX IF NOT EXISTS idx_assays_compound ON assays(compound_id);
                """
            )

        # Merge new module keys into existing configs
        cfg = conn.execute("SELECT modules FROM lab_config WHERE id = 1").fetchone()
        if cfg and cfg[0]:
            try:
                mods = json.loads(cfg[0])
            except json.JSONDecodeError:
                mods = {}
            changed = False
            for k, v in DEFAULT_MODULES.items():
                if k not in mods:
                    mods[k] = v
                    changed = True
            if changed:
                conn.execute(
                    "UPDATE lab_config SET modules = ? WHERE id = 1",
                    (json.dumps(mods),),
                )

    # ── lab config ──────────────────────────────────────────────
    def has_lab_config(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM lab_config WHERE id = 1").fetchone()
            return row is not None

    def get_lab_config(self) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM lab_config WHERE id = 1").fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                mods = json.loads(d["modules"])
            except (TypeError, json.JSONDecodeError):
                mods = {}
            merged = dict(DEFAULT_MODULES)
            merged.update(mods or {})
            d["modules"] = merged
            d.setdefault("lab_type", "General")
            d.setdefault("husbandry_label", "Organisms")
            return d

    def save_lab_config(
        self,
        lab_name: str,
        lab_code: str,
        primary_color: str,
        accent_color: str,
        timezone: str,
        logo_path: Optional[str] = None,
        modules: Optional[dict] = None,
        lab_type: str = "General",
        husbandry_label: str = "Organisms",
    ) -> None:
        mods = json.dumps(modules or DEFAULT_MODULES)
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO lab_config
                    (id, lab_name, lab_code, primary_color, accent_color,
                     timezone, logo_path, lab_type, husbandry_label, modules, created_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    lab_name=excluded.lab_name,
                    lab_code=excluded.lab_code,
                    primary_color=excluded.primary_color,
                    accent_color=excluded.accent_color,
                    timezone=excluded.timezone,
                    logo_path=excluded.logo_path,
                    lab_type=excluded.lab_type,
                    husbandry_label=excluded.husbandry_label,
                    modules=excluded.modules
                """,
                (
                    lab_name,
                    lab_code,
                    primary_color,
                    accent_color,
                    timezone,
                    logo_path,
                    lab_type,
                    husbandry_label,
                    mods,
                    now,
                ),
            )

    def update_modules(self, modules: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE lab_config SET modules = ? WHERE id = 1",
                (json.dumps(modules),),
            )

    def update_theme(self, primary_color: str, accent_color: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE lab_config SET primary_color = ?, accent_color = ? WHERE id = 1",
                (primary_color, accent_color),
            )

    # ── users ───────────────────────────────────────────────────
    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str,
        display_name: Optional[str] = None,
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, display_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, password_hash, role, display_name or username, now),
            )
            return int(cur.lastrowid)

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
            ).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, display_name, active, created_at FROM users ORDER BY username"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_user(
        self,
        user_id: int,
        role: Optional[str] = None,
        active: Optional[int] = None,
        password_hash: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> None:
        fields, vals = [], []
        if role is not None:
            fields.append("role = ?")
            vals.append(role)
        if active is not None:
            fields.append("active = ?")
            vals.append(active)
        if password_hash is not None:
            fields.append("password_hash = ?")
            vals.append(password_hash)
        if display_name is not None:
            fields.append("display_name = ?")
            vals.append(display_name)
        if not fields:
            return
        vals.append(user_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", vals)

    def delete_user(self, user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    # ── audit ───────────────────────────────────────────────────
    def audit(
        self,
        action: str,
        username: Optional[str] = None,
        role: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (username, role, action, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, role, action, details, utc_now()),
            )

    def recent_audit(self, limit: int = 20) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── samples ─────────────────────────────────────────────────
    def list_samples(self) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute("SELECT * FROM samples ORDER BY id DESC").fetchall()
            ]

    def add_sample(self, **kwargs) -> int:
        now = utc_now()
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        with self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO samples ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )
            return int(cur.lastrowid)

    def update_sample(self, sample_id: int, **kwargs) -> None:
        kwargs["updated_at"] = utc_now()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE samples SET {sets} WHERE id = ?",
                (*kwargs.values(), sample_id),
            )

    def delete_sample(self, sample_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))

    # ── compounds ───────────────────────────────────────────────
    def list_compounds(self) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute("SELECT * FROM compounds ORDER BY name").fetchall()
            ]

    def add_compound(
        self,
        name: str,
        status: str = "active",
        mw: Optional[float] = None,
        smiles: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO compounds (name, status, mw, smiles, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, status, mw, smiles, notes, utc_now()),
            )
            return int(cur.lastrowid)

    def update_compound(self, compound_id: int, **kwargs) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE compounds SET {sets} WHERE id = ?",
                (*kwargs.values(), compound_id),
            )

    def delete_compound(self, compound_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM compounds WHERE id = ?", (compound_id,))

    def get_compound(self, compound_id: int) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM compounds WHERE id = ?", (compound_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── assays ──────────────────────────────────────────────────
    def list_assays(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, c.name AS compound_name
                FROM assays a
                LEFT JOIN compounds c ON c.id = a.compound_id
                ORDER BY a.assay_date DESC, a.id DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def add_assay(self, **kwargs) -> int:
        kwargs.setdefault("created_at", utc_now())
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        with self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO assays ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )
            return int(cur.lastrowid)

    def update_assay(self, assay_id: int, **kwargs) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE assays SET {sets} WHERE id = ?",
                (*kwargs.values(), assay_id),
            )

    def delete_assay(self, assay_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM assays WHERE id = ?", (assay_id,))

    # ── husbandry ───────────────────────────────────────────────
    def list_husbandry(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT h.*, c.name AS compound_name
                FROM husbandry_events h
                LEFT JOIN compounds c ON c.id = h.related_compound_id
                ORDER BY h.event_date DESC, h.id DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def add_husbandry(self, **kwargs) -> int:
        kwargs.setdefault("created_at", utc_now())
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        with self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO husbandry_events ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )
            return int(cur.lastrowid)

    def update_husbandry(self, event_id: int, **kwargs) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE husbandry_events SET {sets} WHERE id = ?",
                (*kwargs.values(), event_id),
            )

    def delete_husbandry(self, event_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM husbandry_events WHERE id = ?", (event_id,))

    # ── protocols ───────────────────────────────────────────────
    def list_protocols(self) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute("SELECT * FROM protocols ORDER BY title").fetchall()
            ]

    def get_protocol(self, protocol_id: int) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM protocols WHERE id = ?", (protocol_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_protocol(
        self,
        title: str,
        category: str,
        content: str,
        author: str,
        version: int = 1,
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO protocols
                    (title, category, content, author, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (title, category, content, author, version, now, now),
            )
            return int(cur.lastrowid)

    def update_protocol(self, protocol_id: int, **kwargs) -> None:
        kwargs["updated_at"] = utc_now()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE protocols SET {sets} WHERE id = ?",
                (*kwargs.values(), protocol_id),
            )

    def delete_protocol(self, protocol_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM protocols WHERE id = ?", (protocol_id,))

    # ── proteins ────────────────────────────────────────────────
    def list_proteins(self) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM proteins ORDER BY name"
                ).fetchall()
            ]

    def get_protein(self, protein_id: int) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM proteins WHERE id = ?", (protein_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_protein(self, **kwargs) -> int:
        now = utc_now()
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        with self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO proteins ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )
            return int(cur.lastrowid)

    def update_protein(self, protein_id: int, **kwargs) -> None:
        kwargs["updated_at"] = utc_now()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE proteins SET {sets} WHERE id = ?",
                (*kwargs.values(), protein_id),
            )

    def delete_protein(self, protein_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM proteins WHERE id = ?", (protein_id,))

    # ── counts / dashboard ──────────────────────────────────────
    def dashboard_counts(self) -> dict[str, int]:
        with self.connect() as conn:

            def count(table: str) -> int:
                return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

            return {
                "samples": count("samples"),
                "compounds": count("compounds"),
                "assays": count("assays"),
                "husbandry": count("husbandry_events"),
                "protocols": count("protocols"),
                "proteins": count("proteins"),
                "users": count("users"),
                "audit": count("audit_log"),
            }


def get_db(db_path: Optional[Path | str] = None) -> Database:
    return Database(db_path)
