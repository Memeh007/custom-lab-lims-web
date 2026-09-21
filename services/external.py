"""
Lightweight web helpers: RCSB PDB, UniProt REST, PubChem name→SMILES.
No docking / AlphaFold binaries — fetch & browse only.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

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


# ── PubChem ─────────────────────────────────────────────────────
def pubchem_name_to_smiles(name: str) -> Optional[str]:
    """Resolve compound name to SMILES via PubChem PUG REST."""
    name = name.strip()
    if not name:
        return None
    # Request several property aliases — PubChem field names vary by API version
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{requests.utils.quote(name)}/property/"
        "CanonicalSMILES,IsomericSMILES,ConnectivitySMILES,SMILES,MolecularWeight/JSON"
    )
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    props = (r.json().get("PropertyTable") or {}).get("Properties") or []
    if not props:
        return None
    p0 = props[0]
    return (
        p0.get("CanonicalSMILES")
        or p0.get("IsomericSMILES")
        or p0.get("ConnectivitySMILES")
        or p0.get("SMILES")
    )


def pubchem_lookup(name: str) -> dict[str, Any]:
    smiles = pubchem_name_to_smiles(name)
    if not smiles:
        raise RuntimeError(f"No PubChem hit for '{name}'")
    return {"name": name, "smiles": smiles, "source": "PubChem"}


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
