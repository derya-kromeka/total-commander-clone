#!/usr/bin/env bash
# ------------------------------------------------------------
# Script: scripts/install.sh
# Purpose: Dispatch to the OS-specific installer.
#          Prefer calling the named script directly:
#            bash scripts/install-linux.sh
#            bash scripts/install-macos.sh
#            scripts\install-windows.bat
# ------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin*)
    exec bash "$SCRIPT_DIR/install-macos.sh" "$@"
    ;;
  Linux*)
    exec bash "$SCRIPT_DIR/install-linux.sh" "$@"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "[INFO] Windows detected. Running scripts/install-windows.bat ..."
    exec cmd.exe //c "$SCRIPT_DIR/install-windows.bat" "$@"
    ;;
  *)
    echo "[ERROR] Unsupported OS. Use one of:" >&2
    echo "        bash scripts/install-linux.sh" >&2
    echo "        bash scripts/install-macos.sh" >&2
    echo "        scripts\\install-windows.bat" >&2
    exit 1
    ;;
esac
