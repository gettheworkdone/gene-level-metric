#!/usr/bin/env bash
set -euo pipefail

export CONDA_DIR="${CONDA_DIR:-/opt/conda}"
export PATH="$CONDA_DIR/bin:$PATH"
BUSCO_ENV_NAME="busco_env"
BUSCO_WRAPPER="/usr/local/bin/busco"

install_miniconda() {
  echo "[startup] Installing Miniconda..."
  curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b -p "$CONDA_DIR"
  rm -f /tmp/miniconda.sh
}

ensure_busco_wrapper() {
  cat > "$BUSCO_WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$CONDA_DIR/bin/conda" run --no-capture-output -n "$BUSCO_ENV_NAME" busco "\$@"
EOF
  chmod +x "$BUSCO_WRAPPER"
}

install_busco() {
  echo "[startup] Installing BUSCO 5.7.1 in conda env (first run only)..."
  conda config --set always_yes yes --set changeps1 no
  conda config --set channel_priority strict
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true
  conda create -n "$BUSCO_ENV_NAME" -c conda-forge -c bioconda python=3.12 busco==5.7.1
  conda clean -afy
  ensure_busco_wrapper
}

if [ ! -x "$CONDA_DIR/bin/conda" ]; then
  install_miniconda
fi

if conda env list | awk '{print $1}' | grep -qx "$BUSCO_ENV_NAME"; then
  ensure_busco_wrapper
  echo "[startup] BUSCO env already installed."
else
  install_busco
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port 7860
