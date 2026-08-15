#!/usr/bin/env bash
# ------------------------------------------------------------
# Script: scripts/install-macos.sh
# Purpose: macOS setup — find or install Python 3.8+, create
#          .venv, install requirements.txt. Git credentials
#          (remote URL, username, PAT) are configured in the app:
#          Help → Git settings.
# Usage:   bash scripts/install-macos.sh
#          Then start with: bash scripts/run-macos.sh
#          Finder: double-click scripts/RUN.command
# ------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

REQUIREMENTS="requirements.txt"
VENV_DIR="$ROOT/.venv"
MIN_PY_MAJOR=3
MIN_PY_MINOR=8

info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
err() { echo "[ERROR] $*" >&2; }

echo
echo "============================================================"
echo " Total Commander Clone - macOS install"
echo "============================================================"
echo " Project: $ROOT"
echo " Hardware: $(uname -m)"
echo

SUDO=()
if [[ "$(id -u)" -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
  SUDO=(sudo)
fi

run_sudo() {
  if [[ ${#SUDO[@]} -gt 0 ]]; then
    "${SUDO[@]}" "$@"
  else
    "$@"
  fi
}

python_ok() {
  local py="$1"
  "$py" -c "import sys; v=sys.version_info; raise SystemExit(0 if (v.major,v.minor)>=(${MIN_PY_MAJOR},${MIN_PY_MINOR}) else 1)" 2>/dev/null
}

find_python_cmd() {
  if command -v python3 >/dev/null 2>&1 && python_ok python3; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1 && python_ok python; then
    echo "python"
    return 0
  fi
  local p _majmin
  for p in \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /opt/local/bin/python3 \
    /opt/local/bin/python3.12 \
    /opt/local/bin/python3.11
  do
    if [[ -x "$p" ]] && python_ok "$p"; then
      echo "$p"
      return 0
    fi
  done
  for _majmin in 3.14 3.13 3.12 3.11 3.10 3.9 3.8; do
    p="/Library/Frameworks/Python.framework/Versions/${_majmin}/bin/python3"
    if [[ -x "$p" ]] && python_ok "$p"; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

install_macos_python() {
  info "Installing Python (Homebrew preferred, else MacPorts)..."

  if [[ -x /opt/homebrew/bin/brew ]]; then
    info "Using Homebrew (Apple Silicon: /opt/homebrew)..."
    eval "$(/opt/homebrew/bin/brew shellenv)"
    brew install python git
    hash -r 2>/dev/null || true
    return 0
  fi
  if [[ -x /usr/local/bin/brew ]]; then
    info "Using Homebrew (Intel: /usr/local)..."
    eval "$(/usr/local/bin/brew shellenv)"
    brew install python git
    hash -r 2>/dev/null || true
    return 0
  fi
  if command -v brew >/dev/null 2>&1; then
    info "Using Homebrew (from PATH)..."
    eval "$(brew shellenv)"
    brew install python git
    hash -r 2>/dev/null || true
    return 0
  fi

  if command -v port >/dev/null 2>&1; then
    info "Using MacPorts..."
    run_sudo port install python312 git
    export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
    run_sudo port select --set python3 python312 2>/dev/null || true
    hash -r 2>/dev/null || true
    return 0
  fi

  err "Could not auto-install Python (Homebrew and MacPorts not found)."
  err "Install one of the following, then re-run this script:"
  err "  • Homebrew:  https://brew.sh  →  brew install python git"
  err "  • MacPorts:  https://www.macports.org/install.php"
  err "      sudo port install python312 git && sudo port select --set python3 python312"
  err "  • Official installer:  https://www.python.org/downloads/macos/"
  return 1
}

ensure_venv_pip() {
  local venv_python="$1"
  if "$venv_python" -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  info "pip missing in venv; running ensurepip..."
  if "$venv_python" -m ensurepip --upgrade 2>/dev/null; then
    return 0
  fi
  err "Could not install pip into the venv."
  err "  Use a full Python 3 install (brew install python), not only the Xcode stub."
  return 1
}

PY_CMD=()
found="$(find_python_cmd)" || true
if [[ -n "${found:-}" ]]; then
  # shellcheck disable=SC2206
  PY_CMD=($found)
else
  install_macos_python
  hash -r 2>/dev/null || true
  found="$(find_python_cmd)" || true
  if [[ -z "${found:-}" ]]; then
    err "Could not find a usable Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ after install attempt."
    exit 1
  fi
  # shellcheck disable=SC2206
  PY_CMD=($found)
fi

info "Using Python: ${PY_CMD[*]}"
"${PY_CMD[@]}" --version

if [[ -f "$VENV_DIR/pyvenv.cfg" ]]; then
  info "Virtual environment already exists at .venv — refreshing packages."
else
  info "Creating virtual environment at .venv ..."
  "${PY_CMD[@]}" -m venv "$VENV_DIR"
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  err "venv is missing an interpreter at .venv/bin/python"
  exit 1
fi

ensure_venv_pip "$VENV_DIR/bin/python"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
if [[ -f "$ROOT/$REQUIREMENTS" ]]; then
  info "Installing packages from $REQUIREMENTS ..."
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT/$REQUIREMENTS"
else
  warn "No $REQUIREMENTS; skipping package install."
fi

if command -v git >/dev/null 2>&1; then
  info "Git: $(git --version 2>/dev/null | head -n1)"
else
  warn "Git is not installed. Pull/push from the app needs Git."
  warn "  xcode-select --install    OR    brew install git"
fi

chmod +x "$SCRIPT_DIR/run-macos.sh" "$SCRIPT_DIR/RUN.command" 2>/dev/null || true

echo
info "Done."
info "  Start from Terminal:  bash scripts/run-macos.sh"
info "  Finder:               double-click scripts/RUN.command"
info "  Git remote / username / PAT:  Help → Git settings  (inside the app)"
echo
