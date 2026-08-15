#!/usr/bin/env bash
# ------------------------------------------------------------
# Script: scripts/run-linux.sh
# Purpose: Run the app with the project .venv interpreter (Linux).
#          Run: bash scripts/install-linux.sh  once to create .venv.
# ------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/main.py" ]]; then
  echo "[ERROR] main.py not found in: $ROOT" >&2
  exit 1
fi

VENV_PY="$ROOT/.venv/bin/python"
if [[ -x "$VENV_PY" ]]; then
  exec "$VENV_PY" "$ROOT/main.py"
fi

echo "[ERROR] Virtual environment not found or incomplete." >&2
echo "        Run:  bash scripts/install-linux.sh" >&2
exit 1
