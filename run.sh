#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "[run] virtualenv not found: $VENV_DIR"
  echo "[run] 먼저 실행: bash setup.sh"
  exit 1
fi

source "$VENV_DIR/bin/activate"

if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
fi

usage() {
  cat <<'EOF'
Usage:
  bash run.sh <command> [options]

Commands:
  sample                Copy sample signal CSV -> data/generated_signals.csv
  qlib                  Generate signals with qlib
  validate              Validate signal CSV schema and duplicates
  paper                 Run local paper simulation
  pipeline              Run event-driven pipeline (generate -> validate -> paper)
  lean                  Run LEAN backtest wrapper
  live                  Run LEAN live deploy wrapper
  help                  Show help

Examples:
  bash run.sh sample
  bash run.sh validate --signal-csv neon_alpha/data/generated_signals.csv
  bash run.sh paper --signal-csv neon_alpha/data/generated_signals.csv --price-csv neon_alpha/data/sample_prices.csv
  bash run.sh pipeline --mode sample --price-csv neon_alpha/data/sample_prices.csv
  bash run.sh qlib --provider-uri ~/.qlib/qlib_data/us_data --start 2022-01-01 --end 2025-12-31
  bash run.sh lean --lean-project /path/to/lean-project --signal-csv neon_alpha/data/generated_signals.csv --long-count 3
  bash run.sh live --lean-project /path/to/lean-project --signal-csv neon_alpha/data/generated_signals.csv --long-count 3 --max-positions 3
  bash run.sh live --lean-project /path/to/lean-project -- --brokerage "Paper Trading" --data-provider-live "Alpaca"
EOF
}

cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$cmd" in
  sample)
    python -m neon_alpha.cli sample "$@"
    ;;
  qlib)
    python -m neon_alpha.cli qlib "$@"
    ;;
  validate)
    python -m neon_alpha.cli validate "$@"
    ;;
  paper)
    python -m neon_alpha.cli paper "$@"
    ;;
  pipeline)
    python -m neon_alpha.cli pipeline "$@"
    ;;
  lean)
    LEAN_PROJECT=""
    SIGNAL_CSV="${SIGNAL_CSV:-$ROOT_DIR/data/generated_signals.csv}"
    LONG_COUNT="${LONG_COUNT:-3}"
    MAX_POSITIONS="${MAX_POSITIONS:-$LONG_COUNT}"
    MIN_SCORE="${MIN_SCORE:--1e9}"
    MAX_WEIGHT_PER_SYMBOL="${MAX_WEIGHT_PER_SYMBOL:-0.5}"
    MAX_DAILY_TURNOVER="${MAX_DAILY_TURNOVER:-1.0}"
    EXTRA_ARGS=()

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --lean-project)
          LEAN_PROJECT="$2"
          shift 2
          ;;
        --signal-csv)
          SIGNAL_CSV="$2"
          shift 2
          ;;
        --long-count)
          LONG_COUNT="$2"
          shift 2
          ;;
        --max-positions)
          MAX_POSITIONS="$2"
          shift 2
          ;;
        --min-score)
          MIN_SCORE="$2"
          shift 2
          ;;
        --max-weight-per-symbol)
          MAX_WEIGHT_PER_SYMBOL="$2"
          shift 2
          ;;
        --max-daily-turnover)
          MAX_DAILY_TURNOVER="$2"
          shift 2
          ;;
        --)
          shift
          EXTRA_ARGS+=("$@")
          break
          ;;
        *)
          EXTRA_ARGS+=("$1")
          shift
          ;;
      esac
    done

    if [[ -z "$LEAN_PROJECT" ]]; then
      echo "[run] --lean-project is required for lean command."
      exit 1
    fi
    if [[ ! -f "$SIGNAL_CSV" ]]; then
      echo "[run] signal csv not found: $SIGNAL_CSV"
      exit 1
    fi
    if ! command -v lean >/dev/null 2>&1; then
      echo "[run] lean command not found. install with: bash setup.sh --with-lean"
      exit 1
    fi

    mkdir -p "$LEAN_PROJECT"
    mkdir -p "$LEAN_PROJECT/data"
    cp "$ROOT_DIR/execution/lean/HybridQlibLeanAlgorithm.py" "$LEAN_PROJECT/main.py"
    cp "$SIGNAL_CSV" "$LEAN_PROJECT/data/signals.csv"

    lean backtest "$LEAN_PROJECT" \
      --parameter "signal_csv=$LEAN_PROJECT/data/signals.csv" \
      --parameter "long_count=$LONG_COUNT" \
      --parameter "max_positions=$MAX_POSITIONS" \
      --parameter "min_score=$MIN_SCORE" \
      --parameter "max_weight_per_symbol=$MAX_WEIGHT_PER_SYMBOL" \
      --parameter "max_daily_turnover=$MAX_DAILY_TURNOVER" \
      "${EXTRA_ARGS[@]}"
    ;;
  live)
    LEAN_PROJECT=""
    SIGNAL_CSV="${SIGNAL_CSV:-$ROOT_DIR/data/generated_signals.csv}"
    LONG_COUNT="${LONG_COUNT:-3}"
    MAX_POSITIONS="${MAX_POSITIONS:-$LONG_COUNT}"
    MIN_SCORE="${MIN_SCORE:--1e9}"
    MAX_WEIGHT_PER_SYMBOL="${MAX_WEIGHT_PER_SYMBOL:-0.5}"
    MAX_DAILY_TURNOVER="${MAX_DAILY_TURNOVER:-1.0}"
    EXTRA_ARGS=()

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --lean-project)
          LEAN_PROJECT="$2"
          shift 2
          ;;
        --signal-csv)
          SIGNAL_CSV="$2"
          shift 2
          ;;
        --long-count)
          LONG_COUNT="$2"
          shift 2
          ;;
        --max-positions)
          MAX_POSITIONS="$2"
          shift 2
          ;;
        --min-score)
          MIN_SCORE="$2"
          shift 2
          ;;
        --max-weight-per-symbol)
          MAX_WEIGHT_PER_SYMBOL="$2"
          shift 2
          ;;
        --max-daily-turnover)
          MAX_DAILY_TURNOVER="$2"
          shift 2
          ;;
        --)
          shift
          EXTRA_ARGS+=("$@")
          break
          ;;
        *)
          EXTRA_ARGS+=("$1")
          shift
          ;;
      esac
    done

    if [[ -z "$LEAN_PROJECT" ]]; then
      echo "[run] --lean-project is required for live command."
      exit 1
    fi
    if [[ ! -f "$SIGNAL_CSV" ]]; then
      echo "[run] signal csv not found: $SIGNAL_CSV"
      exit 1
    fi
    if ! command -v lean >/dev/null 2>&1; then
      echo "[run] lean command not found. install with: bash setup.sh --with-lean"
      exit 1
    fi

    mkdir -p "$LEAN_PROJECT"
    mkdir -p "$LEAN_PROJECT/data"
    cp "$ROOT_DIR/execution/lean/HybridQlibLeanAlgorithm.py" "$LEAN_PROJECT/main.py"
    cp "$SIGNAL_CSV" "$LEAN_PROJECT/data/signals.csv"

    lean live deploy "$LEAN_PROJECT" \
      --parameter "signal_csv=$LEAN_PROJECT/data/signals.csv" \
      --parameter "long_count=$LONG_COUNT" \
      --parameter "max_positions=$MAX_POSITIONS" \
      --parameter "min_score=$MIN_SCORE" \
      --parameter "max_weight_per_symbol=$MAX_WEIGHT_PER_SYMBOL" \
      --parameter "max_daily_turnover=$MAX_DAILY_TURNOVER" \
      "${EXTRA_ARGS[@]}"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "[run] unknown command: $cmd"
    usage
    exit 1
    ;;
esac
