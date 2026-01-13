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

## 8) Run this repo in stub mode

```bash
SCRAP_BACKEND=stub python -m sim.experiment_hypatia
```

## 9) Run this repo in real Hypatia mode

Assuming Hypatia exposes a CLI that can write a connectivity schedule:

```bash
export HYPATIA_CMD="python -m hypatia.cli"
python -m sim.experiment_hypatia \
  --hypatia-mode real \
  --hypatia-cmd "$HYPATIA_CMD" \
  --n-sats 10 \
  --n-ground 2 \
  --steps 5
```

The command must emit a JSON artifact with a `steps` array (see `sim/hypatia_real.py` for schema).
