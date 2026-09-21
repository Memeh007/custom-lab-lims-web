# Custom Lab LIMS Web — User Guide

In-app mirror: sign in and open **Guide** (`/guide`).

## Purpose

Custom Lab LIMS Web is a lightweight Laboratory Information Management System for **any lab type**. Stack: **FastAPI + Jinja2 + SQLite**. No Streamlit. Designed for local use, demos, and portfolio walkthroughs.

## First-run setup

1. Install dependencies and start the server (see **Run** below).
2. Open http://127.0.0.1:8000 — you will be redirected to **/setup** if no lab exists.
3. Enter lab name, code, type, theme colors, timezone, admin account, and module toggles.
4. Sign in with the admin you created.

If you used `python seed.py --reset`, change the demo passwords immediately (listed in README).

## Per-lab databases

| Path | Role |
|------|------|
| `data/labs_registry.json` | Active lab pointer + catalog |
| `data/labs/<LAB_CODE>/lab.db` | Isolated SQLite for that lab |
| `data/lab_lims.db` | Legacy single DB (migrated on first setup) |

- **Create** an empty lab from Settings (admin). It starts with schema only — switch to it and complete `/setup` for that DB.
- **Switch** active lab from Settings. Your session is cleared so credentials cannot cross labs.
- Lab **code** is the folder key and is not renamed from Settings.

## Compounds & SMILES

**Compounds → Fetch SMILES** resolves common names via:

1. PubChem PUG REST (with retries on 429/5xx)
2. NIH CACTUS Chemical Identifier Resolver (fallback)

Results include `source`, and when available `mw` / `formula`. The add form is autofilled so you can save in one step.

## Modules

| Module | What it does |
|--------|----------------|
| Samples | Inventory records |
| Compounds | Library + SMILES lookup |
| Experiments | Flexible assays |
| Husbandry | Events; nav label configurable |
| Protocols | Text / Markdown body |
| Proteins | RCSB, UniProt, 3Dmol.js |
| Bioinformatics | FASTA search, CIF→PDB, SMILES |
| Analytics | Charts, CSV, R ggplot2 script |
| Integrations | Optional tools (not bundled) |
| Users / Audit | Roles + activity |

Toggle modules under **Settings**.

## Security

This is a **local lab tool**. Default bind address is `127.0.0.1`. Do not expose it to the public internet without authentication at the reverse-proxy layer, TLS, and a threat model.

- Secrets: `data/.session_secret` (gitignored)
- DBs & uploads: gitignored
- Upload filenames sanitized; structure reads confined to `uploads/structures/`
- See **SECURITY.md**

## Backups

Stop the app (or use SQLite online backup), then copy:

```bash
mkdir -p data/backups
cp -a data/labs/DEMO data/backups/DEMO-YYYYMMDD
cp data/labs_registry.json data/backups/
# optional
cp -a uploads data/backups/uploads-YYYYMMDD
```

## Run

### Linux / macOS

```bash
cd custom-lab-lims-web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Or: `bash run.sh`

### Windows

```bat
cd custom-lab-lims-web
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Or: `run.bat`

### Optional AutoDock Vina

Not required. See `docs/VINA.md` and the Integrations page.
