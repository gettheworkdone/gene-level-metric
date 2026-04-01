#!/usr/bin/env bash
set -euo pipefail

export CONDA_DIR="${CONDA_DIR:-/opt/conda}"
export PATH="$CONDA_DIR/bin:$PATH"

install_miniconda() {
  echo "[startup] Installing Miniconda..."
  curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b -p "$CONDA_DIR"
  rm -f /tmp/miniconda.sh
}

install_busco() {
  echo "[startup] Installing BUSCO 5.7.1 (first run only)..."
  conda config --set always_yes yes --set changeps1 no
  conda config --set channel_priority strict
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true
  conda install -c conda-forge -c bioconda busco==5.7.1
  conda clean -afy
}

if [ ! -x "$CONDA_DIR/bin/conda" ]; then
  install_miniconda
fi

if ! command -v busco >/dev/null 2>&1; then
  install_busco
else
  echo "[startup] BUSCO already installed."
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port 7860
