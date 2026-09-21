"""FASTA parsing and local sequence search helpers."""
from __future__ import annotations

import io
from typing import Iterable


def _parse_fasta_biopython(text: str) -> list[tuple[str, str]]:
    from Bio import SeqIO

    return [(rec.id, str(rec.seq).upper()) for rec in SeqIO.parse(io.StringIO(text), "fasta")]


def _parse_fasta_plain(text: str) -> list[tuple[str, str]]:
    records = []
    header, seq_parts = None, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(seq_parts).upper()))
            header = line[1:].split()[0] if line[1:] else "unnamed"
            seq_parts = []
        else:
            seq_parts.append("".join(ch for ch in line if ch.isalpha()))
    if header is not None:
        records.append((header, "".join(seq_parts).upper()))
    return records


def parse_fasta(text: str) -> list[tuple[str, str]]:
    try:
        return _parse_fasta_biopython(text)
    except Exception:
        return _parse_fasta_plain(text)


def local_search(query: str, subjects: Iterable[tuple[str, str]]) -> list[dict]:
    query = "".join(ch for ch in query.upper() if ch.isalpha())
    results = []
    if not query:
        return results
    try:
        from Bio import pairwise2

        use_bio = True
    except Exception:
        use_bio = False

    for sid, seq in subjects:
        if use_bio:
            try:
                alns = pairwise2.align.localms(
                    query, seq, 2, -1, -0.5, -0.1, one_alignment_only=True
                )
                if alns:
                    score = alns[0].score
                    start = seq.find(query) if query in seq else -1
                    results.append(
                        {
                            "subject": sid,
                            "score": round(float(score), 2),
                            "method": "Biopython local alignment",
                            "exact_start": start if start >= 0 else None,
                            "subject_len": len(seq),
                        }
                    )
                continue
            except Exception:
                pass
        positions = []
        start = 0
        while True:
            idx = seq.find(query, start)
            if idx < 0:
                break
            positions.append(idx)
            start = idx + 1
        if positions:
            results.append(
                {
                    "subject": sid,
                    "score": len(query) * len(positions),
                    "method": "substring",
                    "exact_start": positions[0],
                    "hits": len(positions),
                    "subject_len": len(seq),
                }
            )
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return results
