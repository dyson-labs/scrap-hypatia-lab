#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${ROOT_DIR}/.venv"
HYPATIA_DIR="${ROOT_DIR}/deps/hypatia"
HYPATIA_COMMIT="${HYPATIA_COMMIT:-<PINNED_COMMIT_HASH>}"

echo "==> Installing system dependencies"
sudo apt-get update -y
sudo apt-get install -y git python3-venv python3-pip build-essential

if [[ ! -d "${VENV_PATH}" ]]; then
  echo "==> Creating virtual environment at ${VENV_PATH}"
  python3 -m venv "${VENV_PATH}"
fi

echo "==> Activating virtual environment"
source "${VENV_PATH}/bin/activate"

echo "==> Installing Python tools"
pip install --upgrade pip setuptools wheel pytest

if [[ ! -d "${HYPATIA_DIR}" ]]; then
  echo "==> Cloning Hypatia to ${HYPATIA_DIR}"
  git clone https://github.com/snkas/hypatia "${HYPATIA_DIR}"
fi

if [[ "${HYPATIA_COMMIT}" != "<PINNED_COMMIT_HASH>" ]]; then
  echo "==> Checking out Hypatia commit ${HYPATIA_COMMIT}"
  git -C "${HYPATIA_DIR}" fetch --all
  git -C "${HYPATIA_DIR}" checkout "${HYPATIA_COMMIT}"
fi

echo "==> Installing Hypatia in editable mode"
pip install -e "${HYPATIA_DIR}"

echo "==> Hypatia smoke test"
python -c "import hypatia; print('Hypatia import OK:', hypatia.__file__)"

echo "PASS: WSL2 Hypatia setup complete."
