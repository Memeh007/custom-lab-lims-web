"""Demo seed data — generic biomedical lab (not organism-specific)."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from auth import hash_password
from db import DEFAULT_MODULES, Database, get_db


def seed_demo(db: Optional[Database] = None, reset: bool = False) -> Database:
    """Create 'Demo Biomedical Lab' with sample compounds, assays, protocols."""
    if db is None:
        db = get_db()

    if reset and db.db_path.exists():
        db.db_path.unlink()
        db = get_db(db.db_path)

    modules = dict(DEFAULT_MODULES)
    db.save_lab_config(
        lab_name="Demo Biomedical Lab",
        lab_code="DEMO",
        primary_color="#2563eb",
        accent_color="#0d9488",
        timezone="America/Los_Angeles",
        logo_path=None,
        modules=modules,
        lab_type="Biochemistry",
        husbandry_label="Cultures",
    )

    if not db.get_user_by_username("admin"):
        db.create_user("admin", hash_password("change-me-admin"), "admin", "Lab Admin")
    if not db.get_user_by_username("researcher"):
        db.create_user(
            "researcher",
            hash_password("change-me-researcher"),
            "researcher",
            "Demo Researcher",
        )
    if not db.get_user_by_username("viewer"):
        db.create_user(
            "viewer", hash_password("change-me-viewer"), "viewer", "Demo Viewer"
        )

    if not db.list_compounds():
        c1 = db.add_compound(
            "Metformin",
            status="active",
            mw=129.16,
            smiles="CN(C)C(=N)NC(=N)N",
            notes="Biguanide reference compound",
        )
        c2 = db.add_compound(
            "DMSO Vehicle",
            status="control",
            mw=78.13,
            smiles="CS(=O)C",
            notes="Solvent control",
        )
        c3 = db.add_compound(
            "Compound X-12",
            status="screening",
            mw=312.4,
            smiles=None,
            notes="Example screening candidate",
        )

        today = date.today()
        db.add_assay(
            compound_id=c1,
            assay_type="viability",
            dose=1.0,
            survival_percent=92.0,
            notes="Cell viability @ 1 mM, 24h",
            assay_date=str(today - timedelta(days=3)),
            researcher="Demo Researcher",
        )
        db.add_assay(
            compound_id=c1,
            assay_type="growth",
            dose=1.0,
            survival_percent=78.0,
            notes="Relative growth index",
            assay_date=str(today - timedelta(days=1)),
            researcher="Demo Researcher",
        )
        db.add_assay(
            compound_id=c2,
            assay_type="viability",
            dose=0.0,
            survival_percent=98.0,
            notes="Vehicle control",
            assay_date=str(today - timedelta(days=3)),
            researcher="Demo Researcher",
        )
        db.add_assay(
            compound_id=c3,
            assay_type="binding",
            dose=10.0,
            survival_percent=65.0,
            notes="Binding score proxy (higher = stronger)",
            assay_date=str(today),
            researcher="Demo Researcher",
        )

        db.add_husbandry(
            event_date=str(today - timedelta(days=2)),
            researcher="Demo Researcher",
            organism_label="HEK293 stock flask A",
            count=1,
            notes="Routine passage / media change",
            related_compound_id=None,
        )
        db.add_husbandry(
            event_date=str(today),
            researcher="Demo Researcher",
            organism_label="Treatment plate B",
            count=96,
            notes="96-well plate on Metformin titration",
            related_compound_id=c1,
        )

        db.add_sample(
            name="Metformin stock 100 mM",
            sample_type="compound_stock",
            quantity=5.0,
            unit="mL",
            location="Freezer A / Box 2",
            status="available",
            notes="Aliquoted",
            created_by="admin",
        )
        db.add_sample(
            name="RNA extraction kit",
            sample_type="reagent",
            quantity=2.0,
            unit="kits",
            location="Bench fridge",
            status="available",
            notes="",
            created_by="admin",
        )

        db.add_protocol(
            title="General viability assay SOP",
            category="assays",
            content=(
                "# Viability Assay\n\n"
                "1. Prepare compound dilutions in appropriate vehicle.\n"
                "2. Expose cultures / samples for the designated timepoint.\n"
                "3. Score viability or other metric.\n"
                "4. Record dose, metric value, researcher, and notes in LIMS.\n"
            ),
            author="Lab Admin",
            version=1,
        )
        db.add_protocol(
            title="Culture maintenance checklist",
            category="cultures",
            content=(
                "# Culture Checklist\n\n"
                "- Confirm culture / vessel label and count\n"
                "- Log media change or passage\n"
                "- Note any compound-related treatment\n"
            ),
            author="Lab Admin",
            version=1,
        )

        db.add_protein(
            name="Example — Human insulin (placeholder metadata)",
            accession="P01308",
            organism="Homo sapiens",
            source="seed",
            local_path=None,
            sequence=None,
            notes="Fetch full sequence via UniProt in the Proteins module.",
        )

    db.audit("seed_demo", username="system", role="system", details="Demo Biomedical Lab seeded")
    return db


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed Custom Lab LIMS demo data")
    parser.add_argument("--reset", action="store_true", help="Delete existing DB then seed")
    parser.add_argument("--db", type=str, default=None, help="Optional DB path")
    args = parser.parse_args()
    database = get_db(Path(args.db) if args.db else None)
    seed_demo(database, reset=args.reset)
    print(f"Demo seeded at {database.db_path}")
