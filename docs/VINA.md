# Optional AutoDock Vina

**AutoDock Vina is not required to run Custom Lab LIMS Web.**

The app stores compounds (including SMILES), protein structures, and metadata. Docking is an optional external step you can wire later.

## Install Vina yourself

- Obtain a binary from the [AutoDock Vina](https://vina.scripps.edu/) / OpenEye-compatible community builds for your OS.
- Place it somewhere stable, e.g. `C:\Tools\vina\vina.exe` or `/usr/local/bin/vina`.

## Suggested environment variable

```bash
# Linux / macOS
export VINA_BIN=/usr/local/bin/vina

# Windows (PowerShell)
$env:VINA_BIN = "C:\Tools\vina\vina.exe"
```

A future runner could spawn `$VINA_BIN --receptor ... --ligand ...` and attach scores to an assay record. That runner is **not** shipped yet — see Integrations in the UI.

## What you need for a real docking workflow

1. Receptor prepared as PDBQT (often via OpenBabel / Meeko — also not bundled).
2. Ligand from SMILES → 3D → PDBQT.
3. Box / exhaustiveness parameters appropriate to your system.
4. Validation against known poses — LIMS storage alone is not a docking engine.

## Portfolio note

Keeping Vina optional keeps the demo honest: the web app runs with `pip install -r requirements.txt` and no native chemistry binaries.
