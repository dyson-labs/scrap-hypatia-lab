# WSL2 Hypatia Setup

This guide documents a WSL2-based workflow for running real Hypatia connectivity alongside the SCRAP/SISL experiments.

## 1) Install WSL2 + Ubuntu

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted, then open **Ubuntu** from the Start menu.

## 2) Open this repo inside WSL

From Windows, open the repo folder in VS Code and reopen in WSL:

```powershell
code .
```

When prompted, choose **Reopen in WSL**.

## 3) Create and activate a Python venv (WSL)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 4) Install system dependencies

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip build-essential
```

Alternatively, run the helper:

```bash
./scripts/setup_wsl2_hypatia.sh
```

## 5) Clone Hypatia

```bash
mkdir -p deps
git clone https://github.com/snkas/hypatia deps/hypatia
cd deps/hypatia
git checkout <PINNED_COMMIT_HASH>
cd ../..
```

## 6) Install Hypatia in the venv

```bash
pip install -e deps/hypatia
```

## 7) Hypatia smoke test

```bash
python -c "import hypatia; print(hypatia.__file__)"
```

## 8) Generate a Hypatia schedule artifact

Use the sample config in this repo (edit the ranges/time window if you need more links):

```bash
python -m hypatia.cli \
  --config docs/hypatia/sample_config.yaml \
  --output runs/hypatia_schedule.json
```

Sanity-check that the schedule contains edges (ISL + ground links) in the first step:

```bash
python - <<'PY'
import json
from pathlib import Path

schedule = json.loads(Path("runs/hypatia_schedule.json").read_text())
first_edges = schedule["steps"][0]["edges"]
print(f"edges in step 0: {len(first_edges)}")
PY
```

## 9) Run this repo in stub mode

```bash
SCRAP_BACKEND=stub python -m sim.experiment_hypatia
```

## 10) Run this repo in real Hypatia mode

Point the experiment at the generated schedule:

```bash
python -m sim.experiment_hypatia \
  --hypatia-mode real \
  --hypatia-artifact runs/hypatia_schedule.json \
  --n-sats 24 \
  --n-ground 3 \
  --steps 30
```

The command must emit a JSON artifact with a `steps` array (see `sim/hypatia_real.py` for schema).
