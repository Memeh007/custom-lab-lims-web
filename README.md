# Custom Lab LIMS (Web)

A clean, portfolio-ready **Laboratory Information Management System** for **any lab type**, built with **FastAPI + Jinja2 + SQLite**.

**Author:** Alexander Cecena / Memeh007  
Derived from Munroe Lab workflows, generalized for any lab. Munroe identity is never hardcoded — the shipped demo is **Demo Biomedical Lab**.

> **Not Streamlit.** High-contrast UI (near-black headings on soft slate background) for LinkedIn demos and accessibility.

## Features

- **First-run Lab Setup wizard** — lab name, code, lab type, colors, timezone, admin account, module toggles, configurable husbandry label
- **Module toggles** hide nav items: samples, experiments, compounds, protocols, husbandry, bioinformatics, proteins, analytics, users, audit
- Samples, Compounds, flexible Assays (viability, growth, binding, sequencing QC, custom, …)
- Husbandry / culture events with configurable nav label
- Protocols (Markdown text)
- **Proteins**: library + **RCSB PDB** download + **UniProt** search/fetch + **3Dmol.js** viewer
- **Bioinformatics**: local FASTA search, **CIF→PDB**, **PubChem** name→SMILES
- **Analytics**: Chart.js graphs, CSV export, downloadable **R ggplot2** script
- **Integrations** stubs for Vina / OpenBabel / AlphaFold (not bundled — portfolio-honest)
- Users/roles (admin / researcher / viewer) + audit log
- Sessions via Starlette SessionMiddleware + Werkzeug password hashing

## Contrast / UX

- Body & headings: `#0f172a` on `#f1f5f9`
- Labels: `#334155`; placeholders: `#64748b`
- Cards: white `#ffffff`
- Primary buttons: lab primary color with **white** text
- Visible focus rings

## Quick start

### Linux / macOS

```bash
cd /workspace/custom-lab-lims-web
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

## Default demo passwords

Change immediately. Hashed in DB; plaintext **only** here:

| Username     | Password               | Role       |
|--------------|------------------------|------------|
| `admin`      | `change-me-admin`      | admin      |
| `researcher` | `change-me-researcher` | researcher |
| `viewer`     | `change-me-viewer`     | viewer     |

## What this is not

- No OpenBabel / AutoDock Vina / ColabFold binaries  
- No huge genome FASTA hosting  
- **No Streamlit** — FastAPI server-rendered pages only

## License

MIT — see `LICENSE`.
