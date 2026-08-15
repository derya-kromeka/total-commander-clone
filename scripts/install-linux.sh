#!/usr/bin/env bash
# ------------------------------------------------------------
# Script: scripts/install-linux.sh
# Purpose: Linux setup — install Python 3.8+ when missing, create
#          .venv, install requirements.txt. Git credentials
#          (remote URL, username, PAT) are configured in the app:
#          Help → Git settings.
# Usage:   bash scripts/install-linux.sh
#          Then start with: bash scripts/run-linux.sh
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
echo " Total Commander Clone - Linux install"
echo "============================================================"
echo " Project: $ROOT"
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
  return 1
}

install_system_python() {
  info "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ not found; installing via the distro package manager..."
  if [[ ! -f /etc/os-release ]]; then
    err "Cannot detect distro (/etc/os-release missing). Install Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ and re-run."
    return 1
  fi
  # shellcheck source=/dev/null
  . /etc/os-release
  case "${ID:-}" in
    ubuntu|debian|pop|linuxmint|raspbian)
      run_sudo apt-get update -qq
      run_sudo apt-get install -y python3 python3-pip python3-venv git
      return 0
      ;;
    fedora|rhel|centos|rocky|almalinux)
      run_sudo dnf install -y python3 python3-pip git
      return 0
      ;;
    arch|manjaro|endeavouros)
      run_sudo pacman -S --needed --noconfirm python python-pip git
      return 0
      ;;
    opensuse*|suse)
      run_sudo zypper install -y python3 python3-pip git
      return 0
      ;;
    alpine)
      run_sudo apk add --no-cache python3 py3-pip git
      return 0
      ;;
  esac
  case "${ID_LIKE:-}" in
    *debian*|*ubuntu*)
      run_sudo apt-get update -qq
      run_sudo apt-get install -y python3 python3-pip python3-venv git
      return 0
      ;;
    *rhel*|*fedora*)
      run_sudo dnf install -y python3 python3-pip git
      return 0
      ;;
  esac
  err "Unsupported Linux distribution (${ID:-unknown}). Install Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+, pip, and git, then re-run."
  return 1
}

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    info "Git: $(git --version 2>/dev/null | head -n1)"
    return 0
  fi
  warn "Git is not installed. Pull/push from the app needs Git."
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    case "${ID:-}" in
      ubuntu|debian|pop|linuxmint|raspbian) warn "  sudo apt-get install -y git" ;;
      fedora|rhel|centos|rocky|almalinux) warn "  sudo dnf install -y git" ;;
      arch|manjaro|endeavouros) warn "  sudo pacman -S git" ;;
      opensuse*|suse) warn "  sudo zypper install -y git" ;;
      alpine) warn "  sudo apk add git" ;;
      *) warn "  Install git with your package manager, then re-open the terminal." ;;
    esac
  fi
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
  err "  Debian/Ubuntu: sudo apt-get install -y python3-pip python3-venv"
  return 1
}

PY_CMD=()
found="$(find_python_cmd)" || true
if [[ -n "${found:-}" ]]; then
  # shellcheck disable=SC2206
  PY_CMD=($found)
else
  install_system_python
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
  if ! "${PY_CMD[@]}" -m venv "$VENV_DIR"; then
    err "venv creation failed. On Debian/Ubuntu install: sudo apt-get install -y python3-venv"
    exit 1
  fi
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

ensure_git

echo
info "Done."
info "  Start the app:  bash scripts/run-linux.sh"
info "  Git remote / username / PAT:  Help → Git settings  (inside the app)"
echo
