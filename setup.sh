#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

WITH_QLIB=0
WITH_LEAN=0

usage() {
  cat <<'EOF'
Usage:
  bash setup.sh [--with-qlib] [--with-lean] [--python /path/to/python]

Options:
  --with-qlib       Install pyqlib (optional)
  --with-lean       Install lean CLI package (optional)
  --python PATH     Python executable (default: python3)
  -h, --help        Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-qlib)
      WITH_QLIB=1
      shift
      ;;
    --with-lean)
      WITH_LEAN=1
      shift
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

echo "[setup] project: $ROOT_DIR"
echo "[setup] python : $PYTHON_BIN"
echo "[setup] venv   : $VENV_DIR"

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
pip install -r "$ROOT_DIR/requirements.txt"
pip install -e "$ROOT_DIR"

if [[ $WITH_QLIB -eq 1 ]]; then
  pip install "pyqlib>=0.9.6"
fi

if [[ $WITH_LEAN -eq 1 ]]; then
  pip install "lean>=1.0.0"
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

echo "[setup] done"
echo "[setup] activate: source $VENV_DIR/bin/activate"
