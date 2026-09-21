"""
Lightweight web helpers: RCSB PDB, UniProt REST, PubChem name→SMILES.
No docking / AlphaFold binaries — fetch & browse only.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

import time

import requests

TIMEOUT = 30
UA = {"User-Agent": "CustomLabLIMS/1.0 (research; educational)"}


# ── RCSB PDB ────────────────────────────────────────────────────
def fetch_rcsb_structure(pdb_id: str, fmt: str = "pdb") -> tuple[str, bytes]:
    """Download structure from files.rcsb.org. fmt: pdb | cif"""
    pdb_id = pdb_id.strip().upper()
    if not pdb_id or len(pdb_id) > 8:
        raise ValueError("Invalid PDB ID")
    fmt = fmt.lower()
    if fmt not in ("pdb", "cif"):
        raise ValueError("fmt must be pdb or cif")
    # Prefer compressed-free endpoints
    if fmt == "pdb":
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    else:
        url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"RCSB download failed ({r.status_code}) for {pdb_id}.{fmt}")
    return url, r.content


def fetch_rcsb_entry_meta(pdb_id: str) -> dict[str, Any]:
    """Basic entry metadata via RCSB data API."""
    pdb_id = pdb_id.strip().upper()
    url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"RCSB metadata failed ({r.status_code}) for {pdb_id}")
    data = r.json()
    title = None
    try:
        title = data.get("struct", {}).get("title")
    except Exception:
        pass
    method = None
    try:
        method = (data.get("exptl") or [{}])[0].get("method")
    except Exception:
        pass
    return {
        "pdb_id": pdb_id,
        "title": title,
        "method": method,
        "raw_keys": list(data.keys())[:20],
    }


# ── UniProt ─────────────────────────────────────────────────────
def uniprot_search(query: str, size: int = 10) -> list[dict[str, Any]]:
    """Search UniProt REST; returns compact hit list."""
    q = query.strip()
    if not q:
        return []
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": q,
        "format": "json",
        "size": min(max(size, 1), 25),
        "fields": "accession,id,protein_name,organism_name,length",
    }
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"UniProt search failed ({r.status_code})")
    results = r.json().get("results") or []
    out = []
    for item in results:
        acc = item.get("primaryAccession") or item.get("uniProtkbId")
        name = None
        try:
            name = (
                item.get("proteinDescription", {})
                .get("recommendedName", {})
                .get("fullName", {})
                .get("value")
            )
        except Exception:
            name = None
        if not name:
            name = item.get("uniProtkbId") or acc
        org = None
        try:
            org = item.get("organism", {}).get("scientificName")
        except Exception:
            pass
        out.append(
            {
                "accession": acc,
                "name": name,
                "organism": org,
                "length": item.get("sequence", {}).get("length")
                if isinstance(item.get("sequence"), dict)
                else None,
            }
        )
    return out


def uniprot_fetch(accession: str) -> dict[str, Any]:
    """Fetch UniProt entry JSON + FASTA sequence."""
    acc = accession.strip().upper()
    if not acc:
        raise ValueError("Accession required")
    meta_url = f"https://rest.uniprot.org/uniprotkb/{acc}.json"
    fasta_url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    rm = requests.get(meta_url, headers=UA, timeout=TIMEOUT)
    if rm.status_code != 200:
        raise RuntimeError(f"UniProt fetch failed ({rm.status_code}) for {acc}")
    data = rm.json()
    name = None
    try:
        name = (
            data.get("proteinDescription", {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value")
        )
    except Exception:
        name = acc
    org = None
    try:
        org = data.get("organism", {}).get("scientificName")
    except Exception:
        pass
    seq = None
    try:
        seq = data.get("sequence", {}).get("value")
    except Exception:
        seq = None
    if not seq:
        rf = requests.get(fasta_url, headers=UA, timeout=TIMEOUT)
        if rf.status_code == 200:
            lines = rf.text.splitlines()
            seq = "".join(l.strip() for l in lines if not l.startswith(">"))
    return {
        "accession": acc,
        "name": name or acc,
        "organism": org,
        "sequence": seq,
        "length": len(seq) if seq else None,
        "source": "UniProt",
    }


# ── PubChem / CACTUS ────────────────────────────────────────────
def _pubchem_properties(name: str) -> Optional[dict[str, Any]]:
    """Fetch PubChem property table row with light retries."""
    name = name.strip()
    if not name:
        return None
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{requests.utils.quote(name)}/property/"
        "CanonicalSMILES,IsomericSMILES,ConnectivitySMILES,SMILES,"
        "MolecularWeight,MolecularFormula/JSON"
    )
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.status_code == 404:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.6 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None
            props = (r.json().get("PropertyTable") or {}).get("Properties") or []
            return props[0] if props else None
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    if last_err:
        raise RuntimeError(f"PubChem request failed: {last_err}") from last_err
    return None


def cactus_name_to_smiles(name: str) -> Optional[str]:
    """NIH CACTUS Chemical Identifier Resolver fallback."""
    name = name.strip()
    if not name:
        return None
    url = (
        "https://cactus.nci.nih.gov/chemical/structure/"
        f"{requests.utils.quote(name)}/smiles"
    )
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        smiles = (r.text or "").strip()
        if not smiles or smiles.lower().startswith("<!") or "page not found" in smiles.lower():
            return None
        return smiles
    except requests.RequestException:
        return None


def pubchem_name_to_smiles(name: str) -> Optional[str]:
    """Resolve compound name to SMILES via PubChem PUG REST."""
    props = _pubchem_properties(name)
    if not props:
        return None
    return (
        props.get("CanonicalSMILES")
        or props.get("IsomericSMILES")
        or props.get("ConnectivitySMILES")
        or props.get("SMILES")
    )


def pubchem_lookup(name: str) -> dict[str, Any]:
    """Resolve name → SMILES (+ MW / formula when available).

    Tries PubChem (with retries), then NIH CACTUS as fallback.
    """
    name = name.strip()
    if not name:
        raise RuntimeError("Compound name required")

    props = _pubchem_properties(name)
    smiles = None
    mw = None
    formula = None
    source = "PubChem"
    if props:
        smiles = (
            props.get("CanonicalSMILES")
            or props.get("IsomericSMILES")
            or props.get("ConnectivitySMILES")
            or props.get("SMILES")
        )
        mw_raw = props.get("MolecularWeight")
        try:
            mw = float(mw_raw) if mw_raw is not None else None
        except (TypeError, ValueError):
            mw = None
        formula = props.get("MolecularFormula")

    if not smiles:
        smiles = cactus_name_to_smiles(name)
        source = "NIH CACTUS"
        mw = None
        formula = None

    if not smiles:
        raise RuntimeError(f"No SMILES found for '{name}' (PubChem + CACTUS)")

    return {
        "name": name,
        "smiles": smiles,
        "source": source,
        "mw": mw,
        "formula": formula,
    }


# ── CIF → PDB ───────────────────────────────────────────────────
def cif_to_pdb(cif_text: str) -> str:
    """Convert mmCIF text to PDB using Biopython when available."""
    try:
        from Bio.PDB import MMCIFParser, PDBIO
    except ImportError as e:
        raise RuntimeError("Biopython required for CIF→PDB conversion") from e

    parser = MMCIFParser(QUIET=True)
    structure = parser.get_structure("struct", io.StringIO(cif_text))
    buf = io.StringIO()
    io_out = PDBIO()
    io_out.set_structure(structure)
    io_out.save(buf)
    return buf.getvalue()


def save_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
