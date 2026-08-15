#!/usr/bin/env bash
# ------------------------------------------------------------
# Script: scripts/update-and-rebuild.sh
# Purpose: Called from the app when the user accepts an update
#          (Linux / macOS). Waits briefly for the app to exit,
#          gets the latest public code (git pull OR GitHub zip),
#          then relaunches via the OS run script.
#
# No GitHub username/PAT required for a public repo.
# ------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
PUBLIC_URL="${PUBLIC_URL:-https://github.com/derya-kromeka/total-commander-clone.git}"

echo
echo "============================================================"
echo " Total Commander Clone - Update"
echo "============================================================"
echo " Project: $ROOT"
echo

echo "[INFO] Waiting for the app to exit..."
sleep 2

update_via_zip() {
  echo "[INFO] Updating via public GitHub zip download..."
  local py=""
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    py="$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    py="python3"
  elif command -v python >/dev/null 2>&1; then
    py="python"
  else
    echo "[ERROR] Python not found for zip update." >&2
    return 1
  fi
  "$py" "$SCRIPT_DIR/download-public-update.py" "$ROOT" "$BRANCH"
}

update_via_git() {
  if [[ ! -d "$ROOT/.git" ]]; then
    echo "[WARN] No .git folder - falling back to zip download."
    update_via_zip
    return $?
  fi
  if ! git -C "$ROOT" remote get-url "$REMOTE" >/dev/null 2>&1; then
    echo "[INFO] Adding public remote $REMOTE -> $PUBLIC_URL"
    git -C "$ROOT" remote add "$REMOTE" "$PUBLIC_URL"
  fi
  echo "[INFO] Fetching $REMOTE/$BRANCH..."
  GIT_TERMINAL_PROMPT=0 git -C "$ROOT" fetch "$REMOTE" "$BRANCH"
  echo "[INFO] Merging $REMOTE/$BRANCH into local branch..."
  if ! git -C "$ROOT" merge --no-edit "$REMOTE/$BRANCH"; then
    echo "[ERROR] git merge failed (conflicts or local changes?)." >&2
    echo "        Resolve conflicts, then start the app again." >&2
    return 1
  fi
}

if [[ -d "$ROOT/.git" ]] && command -v git >/dev/null 2>&1; then
  BRANCH="$(git -C "$ROOT" branch --show-current 2>/dev/null || echo "$BRANCH")"
  [[ -n "$BRANCH" ]] || BRANCH="main"
  echo "[INFO] Git found - updating via git fetch/merge (public HTTPS, no login)..."
  update_via_git
else
  echo "[INFO] Git is not available - updating via public GitHub zip download..."
  update_via_zip
fi

echo
echo "[INFO] Starting updated app..."
case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin*)
    exec bash "$SCRIPT_DIR/run-macos.sh"
    ;;
  *)
    exec bash "$SCRIPT_DIR/run-linux.sh"
    ;;
esac
