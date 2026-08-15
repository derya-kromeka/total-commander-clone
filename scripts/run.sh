#!/usr/bin/env bash
# ------------------------------------------------------------
# Script: scripts/run.sh
# Purpose: Dispatch to the OS-specific runner.
#          Prefer: bash scripts/run-linux.sh  or  bash scripts/run-macos.sh
# ------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin*)
    exec bash "$SCRIPT_DIR/run-macos.sh" "$@"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    exec cmd.exe //c "$SCRIPT_DIR/run-windows.bat" "$@"
    ;;
  *)
    exec bash "$SCRIPT_DIR/run-linux.sh" "$@"
    ;;
esac
