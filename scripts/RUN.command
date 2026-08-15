#!/bin/bash
# ------------------------------------------------------------
# Double-click launcher for macOS (Terminal.app opens .command files).
# Requires: bash scripts/install-macos.sh  (creates .venv)
# ------------------------------------------------------------
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/run-macos.sh"
