# Custom Lab LIMS (Web)

A clean, portfolio-ready **Laboratory Information Management System** for **any lab type**, built with **FastAPI + Jinja2 + SQLite**.

**Author:** Alexander Cecena / Memeh007  
Derived from Munroe Lab workflows, generalized for any lab. Munroe identity is never hardcoded — the shipped demo is **Demo Biomedical Lab**.

> **Not Streamlit.** Dark scientific UI (navy / teal / violet glass cards) for LinkedIn demos and readability.

## Features

- **First-run Lab Setup wizard** — lab name, code, lab type, colors, timezone, admin account, module toggles, configurable husbandry label
- **Per-lab SQLite databases** — `data/labs/<CODE>/lab.db` + `labs_registry.json`; create/switch labs in Settings without data leakage
- **Module toggles** hide nav items: samples, experiments, compounds, protocols, husbandry, bioinformatics, proteins, analytics, users, audit
- Samples, Compounds, flexible Assays (viability, growth, binding, sequencing QC, custom, …)
- Husbandry / colony events with configurable nav label
- Protocols (Markdown text)
- **Proteins**: library + **RCSB PDB** download + **UniProt** search/fetch + **3Dmol.js** viewer
- **Bioinformatics**: local FASTA search, **CIF→PDB**, **PubChem** name→SMILES (+ NIH CACTUS fallback)
- **Analytics**: Chart.js graphs, CSV export, downloadable **R ggplot2** script
- **In-app Guide** (`/guide`) + `GUIDE.md`
- **Integrations** stubs for Vina / OpenBabel / AlphaFold (optional — see `docs/VINA.md`)
- Users/roles (admin / researcher / viewer) + audit log
- Sessions via Starlette SessionMiddleware + Werkzeug password hashing

## Security (local tool)

- Default listen address: **`127.0.0.1`** — not for public internet by default
- Secrets, databases, and uploads are **gitignored**
- Upload path traversal checks; see **SECURITY.md**
- Optional HTTPS via reverse proxy (notes in SECURITY.md)

## Theme

- Deep navy background with teal / violet accents
- Glass-style cards, high-contrast tables, IBM Plex Sans/Mono
- Lab primary/accent colors still override via setup/settings

## Quick start

### Linux / macOS

```bash
cd custom-lab-lims-web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Or: `bash run.sh`

Open http://127.0.0.1:8000 — if no lab exists you will see **/setup**.

### Windows

```bat
cd custom-lab-lims-web
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Or `run.bat`.

### Demo seed

```bash
source venv/bin/activate
python seed.py --reset
```

After seeding, register/migrate into per-lab layout happens on first app use / setup path.

## Default demo passwords

Change immediately. Hashed in DB; plaintext **only** here:

| Username     | Password               | Role       |
|--------------|------------------------|------------|
| `admin`      | `change-me-admin`      | admin      |
| `researcher` | `change-me-researcher` | researcher |
| `viewer`     | `change-me-viewer`     | viewer     |

## Docs

| File | Contents |
|------|----------|
| `GUIDE.md` | Setup, modules, SMILES, backups, run |
| `SECURITY.md` | Local threat model, gitignore, HTTPS note |
| `docs/VINA.md` | Optional AutoDock Vina binary path |

## What this is not

- No OpenBabel / AutoDock Vina / ColabFold binaries required  
- No huge genome FASTA hosting  
- **No Streamlit** — FastAPI server-rendered pages only

## License

MIT — see `LICENSE`.
