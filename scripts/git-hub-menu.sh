#!/usr/bin/env bash
#
# Git / GitHub all-in-one menu (Unix / macOS / Git Bash).
# Put this file in:  YOUR_PROJECT/scripts/git-hub-menu.sh
# Project root: one folder above this script, OR GIT_MENU_PROJECT_ROOT, OR $1
# Run from any folder: full path to this script (no cd needed).
#
# Optional project root:
#   GIT_MENU_PROJECT_ROOT=/path/to/repo ./scripts/git-hub-menu.sh
#   ./scripts/git-hub-menu.sh /path/to/repo
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${GIT_MENU_PROJECT_ROOT:-}" && -d "$GIT_MENU_PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(cd "$GIT_MENU_PROJECT_ROOT" && pwd)"
elif [[ -n "${1:-}" && -d "$1" ]]; then
  PROJECT_ROOT="$(cd "$1" && pwd)"
else
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

GIT_OK=0
command -v git >/dev/null 2>&1 && GIT_OK=1

# Set by option 6 when redirecting to option 3; cleared after remote is set.
GIT_MENU_FROM_COMMIT=""

# First ## [X.Y.Z] in CHANGELOG.md that is not [Unreleased] (Keep a Changelog: latest release).
changelog_version() {
  local f="$PROJECT_ROOT/CHANGELOG.md"
  [[ -f "$f" ]] || { echo ""; return; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^##[[:space:]]+\[([^]]+)\] ]]; then
      local v="${BASH_REMATCH[1]}"
      if [[ "$v" != "Unreleased" ]]; then
        echo "$v"
        return
      fi
    fi
  done < "$f"
  echo ""
}

banner_success() {
  echo ""
  echo "**********************************************************************"
  echo "*  SUCCESS                                                           *"
  echo "**********************************************************************"
  echo ""
}

banner_fail() {
  echo ""
  echo "**********************************************************************"
  echo "*  FAILED                                                            *"
  echo "**********************************************************************"
  echo ""
}

print_menu_top() {
  echo ""
  echo "**********************************************************************"
  echo "*  Git / GitHub helper                                             *"
  echo "**********************************************************************"
  echo "  Project root: $PROJECT_ROOT"
  echo "  This script:  $SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
  echo "**********************************************************************"
  echo ""
}

# Summary under the menu: origin, identity, HTTPS token file (no network test).
print_menu_context() {
  echo "**********************************************************************"
  echo "*  GIT                                                             *"
  echo "**********************************************************************"
  if [[ "$GIT_OK" -ne 1 ]]; then
    echo "  Git is NOT in PATH  —  install or use option 1"
    echo "**********************************************************************"
    echo ""
    return 0
  fi
  echo "  $(git --version 2>/dev/null | head -n1)"
  echo "**********************************************************************"
  echo ""
  echo "**********************************************************************"
  echo "*  THIS REPO  —  remote, commit identity, HTTPS token               *"
  echo "*    (read from your PC - not a live online check)                *"
  echo "**********************************************************************"
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    echo "  Not a Git repository yet  —  use option 2 (git init)"
    echo "**********************************************************************"
    echo ""
    return 0
  fi
  local CTX_ORIG CTX_UN CTX_UE
  CTX_ORIG="$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null || true)"
  if [[ -z "${CTX_ORIG// }" ]]; then
    echo "  origin (remote):  (not set — use option 3)"
  else
    echo "  origin (remote):  $CTX_ORIG"
  fi
  CTX_UN="$(git -C "$PROJECT_ROOT" config user.name 2>/dev/null || true)"
  CTX_UE="$(git -C "$PROJECT_ROOT" config user.email 2>/dev/null || true)"
  if [[ -z "${CTX_UN// }" ]]; then
    echo "  commit name:       (not set — option 7)"
  else
    echo "  commit name:       $CTX_UN"
  fi
  if [[ -z "${CTX_UE// }" ]]; then
    echo "  commit email:      (not set — option 7)"
  else
    echo "  commit email:      $CTX_UE"
  fi
  if [[ -f "$PROJECT_ROOT/.git/gh-credential-store" ]]; then
    echo "  HTTPS token:       saved in .git for this repo (HTTPS only; option 11)"
  else
    echo "  HTTPS token:       not saved here (if GitHub asks for a password, option 11)"
  fi
  echo "**********************************************************************"
  echo ""
}

suggest_install_git() {
  echo ">>> Git is not installed or not in PATH."
  echo ""
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    case "${ID:-}" in
      arch) echo "    Arch:    sudo pacman -S git" ;;
      ubuntu|debian) echo "    Debian/Ubuntu:  sudo apt update && sudo apt install -y git" ;;
      fedora) echo "    Fedora:  sudo dnf install -y git" ;;
      *) echo "    Install the 'git' package with your distro package manager." ;;
    esac
  else
    echo "    Install the 'git' package (e.g. apt, dnf, pacman, brew)."
  fi
  echo "    macOS:   xcode-select --install   OR   brew install git"
  echo "    Windows: https://git-scm.com/download/win"
  echo "             or:  winget install --id Git.Git -e --source winget"
  echo ""
}

cmd_check_git() {
  if [[ "$GIT_OK" -eq 1 ]]; then
    echo ">>> Git is OK:"
    git --version
  else
    suggest_install_git
  fi
  read -r -p "Press Enter to continue..."
}

cmd_init_repo() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ -d "$PROJECT_ROOT/.git" ]]; then
    echo "Already a Git repository (.git exists)."
  else
    (cd "$PROJECT_ROOT" && git init && git branch -M main)
    echo "Done."
  fi
  read -r -p "Press Enter to continue..."
}

cmd_set_remote() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    echo "Not a Git repo yet. Use option 2 first."
    read -r -p "Press Enter to continue..."
    return
  fi
  echo "Paste GitHub repo URL (HTTPS or git@... SSH). Empty = cancel."
  read -r -p "origin URL: " URL
  if [[ -z "${URL// }" ]]; then
    echo "Cancelled."
    GIT_MENU_FROM_COMMIT=""
    read -r -p "Press Enter to continue..."
    return
  fi
  if git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo "Remote origin exists. Updating URL."
    git -C "$PROJECT_ROOT" remote set-url origin "$URL"
  else
    git -C "$PROJECT_ROOT" remote add origin "$URL"
  fi
  git -C "$PROJECT_ROOT" remote -v
  if [[ "${GIT_MENU_FROM_COMMIT:-}" == "1" ]]; then
    GIT_MENU_FROM_COMMIT=""
    echo ""
    echo "Continuing option 6: add, commit, push..."
    cmd_commit_push
    return
  fi
  read -r -p "Press Enter to continue..."
}

cmd_pull() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo "Not a Git repo."; read -r -p "Press Enter to continue..."; return; fi
  echo "git pull --rebase"
  if git -C "$PROJECT_ROOT" pull --rebase; then
    banner_success
  else
    banner_fail
  fi
  echo "git status"
  git -C "$PROJECT_ROOT" status -sb
  read -r -p "Press Enter to continue..."
}

cmd_status() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo "Not a Git repo."; read -r -p "Press Enter to continue..."; return; fi
  git -C "$PROJECT_ROOT" status
  read -r -p "Press Enter to continue..."
}

cmd_commit_push() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo "Not a Git repo."; read -r -p "Press Enter to continue..."; return; fi

  if ! git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo ""
    echo "No \"origin\" remote is set yet. You need your GitHub repo URL (HTTPS or SSH)."
    echo "On GitHub: open your repo - green \"Code\" button - copy the URL."
    echo "Then use menu option 3, or set remote now below."
    echo ""
    read -r -p "Set remote now? [y/N]: " CP_OR
    if [[ "${CP_OR,,}" == "y" || "${CP_OR,,}" == "yes" ]]; then
      GIT_MENU_FROM_COMMIT=1
      cmd_set_remote
      return
    fi
    echo "Cancelled."
    read -r -p "Press Enter to continue..."
    return
  fi

  GIT_UN="$(git -C "$PROJECT_ROOT" config --get user.name 2>/dev/null || true)"
  GIT_UE="$(git -C "$PROJECT_ROOT" config --get user.email 2>/dev/null || true)"
  if [[ -z "${GIT_UN// }" || -z "${GIT_UE// }" ]]; then
    echo ""
    echo "Git user.name or user.email is not set. Commits will fail until you set them."
    echo "Use menu option 7 (global name/email)."
    read -r -p "Configure identity now? [y/N]: " CP_ID
    if [[ "${CP_ID,,}" == "y" || "${CP_ID,,}" == "yes" ]]; then
      cmd_identity
    fi
    echo "Continuing anyway (commit may fail)."
  fi

  local SUG MSG
  SUG="$(changelog_version)"
  if [[ -n "$SUG" ]]; then
    echo "Suggested from CHANGELOG.md: $SUG"
    read -r -p "Commit message [$SUG] (Enter = use version): " MSG
    MSG=${MSG:-$SUG}
  else
    read -r -p "Commit message: " MSG
  fi
  if [[ -z "${MSG// }" ]]; then echo "Empty message. Cancelled."; read -r -p "Press Enter to continue..."; return; fi

  local CUR_BRANCH
  CUR_BRANCH="$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || true)"
  [[ -z "${CUR_BRANCH// }" ]] && CUR_BRANCH="(unknown)"
  echo ""
  echo "Will run: git add -A  ->  commit  ->  push to origin (current branch: $CUR_BRANCH)"
  read -r -p "Proceed? [Y/n]: " CP_GO
  if [[ "${CP_GO,,}" == "n" || "${CP_GO,,}" == "no" ]]; then echo "Cancelled."; read -r -p "Press Enter to continue..."; return; fi

  local TMP_LS_ERR
  TMP_LS_ERR="$(mktemp)"
  if ! git -C "$PROJECT_ROOT" ls-remote --heads origin >/dev/null 2>"$TMP_LS_ERR"; then
    echo ""
    echo "Could not reach the remote (offline, firewall, DNS, or missing auth for ls-remote)."
    echo "You can fix credentials with option 11 or diagnosis with option 12."
    read -r -p "Try push anyway? [Y/n]: " CP_TRY
    if [[ "${CP_TRY,,}" == "n" || "${CP_TRY,,}" == "no" ]]; then
      rm -f "$TMP_LS_ERR"
      read -r -p "Press Enter to continue..."
      return
    fi
  fi
  rm -f "$TMP_LS_ERR"

  echo ""
  git -C "$PROJECT_ROOT" add -A
  if ! git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null; then
    local COMMIT_MSG_FILE
    COMMIT_MSG_FILE="$(mktemp)"
    printf '%s' "$MSG" >"$COMMIT_MSG_FILE"
    if ! git -C "$PROJECT_ROOT" commit -F "$COMMIT_MSG_FILE"; then
      rm -f "$COMMIT_MSG_FILE"
      echo ""
      echo "Commit failed. Set user.name and user.email with option 7, or fix pre-commit hooks."
      banner_fail
      read -r -p "Press Enter to continue..."
      return
    fi
    rm -f "$COMMIT_MSG_FILE"
  else
    echo "No new changes to commit (nothing different from your last commit)."
    echo "That usually means everything is already saved in Git, or files are outside this folder."
    if ! git -C "$PROJECT_ROOT" rev-parse HEAD >/dev/null 2>&1; then
      echo ""
      echo "You have no commits yet. Git only tracks files inside this folder:"
      echo "  $PROJECT_ROOT"
      echo "Add or save your project files here, then run option 6 again (or use option 8)."
      banner_fail
      read -r -p "Press Enter to continue..."
      return
    fi
  fi

  local TMP_PUSH_ERR
  TMP_PUSH_ERR="$(mktemp)"
  echo ""
  echo "git push"
  if ! git -C "$PROJECT_ROOT" push 2>"$TMP_PUSH_ERR"; then
    echo ""
    echo "Push did not succeed. Tips:"
    echo "  Try:  git push -u origin main"
    echo "  Remote has commits:  git pull --rebase origin main  then push again."
    echo "  Unrelated histories:  git pull origin main --allow-unrelated-histories --no-edit"
    echo "  HTTPS: use a Personal Access Token (option 11), not your GitHub password."
    echo "  Diagnosis: option 12."
    echo ""
    echo "Last lines from Git:"
    tail -n 12 "$TMP_PUSH_ERR" 2>/dev/null || true
    rm -f "$TMP_PUSH_ERR"
    banner_fail
  else
    rm -f "$TMP_PUSH_ERR"
    banner_success
  fi
  read -r -p "Press Enter to continue..."
}

cmd_force_push() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo "Not a Git repo."; read -r -p "Press Enter to continue..."; return; fi
  echo "Force push overwrites the remote branch with your local history."
  echo "Use ONLY after a history rewrite or if you know why."
  read -r -p "Type YES to run git push --force-with-lease origin main: " CONF
  if [[ "$CONF" != "YES" ]]; then echo "Cancelled."; read -r -p "Press Enter to continue..."; return; fi
  echo "git push --force-with-lease origin main"
  if git -C "$PROJECT_ROOT" push --force-with-lease origin main; then
    banner_success
  else
    echo "Fix errors above (auth, branch name)."
    banner_fail
  fi
  read -r -p "Press Enter to continue..."
}

_first_time_push_do_push() {
  if ! git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo "No origin remote. Use option 3, then option 6."
    read -r -p "Press Enter to continue..."
    return
  fi
  echo "Fetching origin..."
  git -C "$PROJECT_ROOT" fetch origin 2>/dev/null || true
  if git -C "$PROJECT_ROOT" rev-parse origin/main >/dev/null 2>&1; then
    echo "If GitHub already has commits (README), pull before push:"
    echo "  git pull --rebase origin main"
    echo "If you see unrelated histories:"
    echo "  git pull origin main --allow-unrelated-histories --no-edit"
    echo ""
  fi
  echo "git push -u origin main"
  if ! git -C "$PROJECT_ROOT" push -u origin main; then
    echo ""
    echo "Push failed. Try: git pull --rebase origin main"
    echo "Then push again. HTTPS needs a token (option 11 on this menu)."
    echo "Unrelated histories: git pull origin main --allow-unrelated-histories --no-edit"
    banner_fail
  else
    banner_success
  fi
  read -r -p "Press Enter to continue..."
}

cmd_first_time_push() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi

  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    git -C "$PROJECT_ROOT" init
    git -C "$PROJECT_ROOT" branch -M main
  fi
  if ! git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo "Paste your GitHub repo URL (HTTPS or SSH)."
    echo "Empty repo OR repo with README both work — if push fails, pull first: git pull --rebase origin main"
    read -r -p "origin URL: " URL
    if [[ -n "${URL// }" ]]; then
      git -C "$PROJECT_ROOT" remote add origin "$URL"
    fi
  else
    echo "Remote origin already set:"
    git -C "$PROJECT_ROOT" remote -v
  fi

  local DEF_MSG MSG
  DEF_MSG="$(changelog_version)"
  if [[ -n "$DEF_MSG" ]]; then
    read -r -p "First commit message [$DEF_MSG] (Enter = use version): " MSG
    MSG=${MSG:-$DEF_MSG}
  else
    read -r -p "First commit message [Initial commit]: " MSG
    MSG=${MSG:-Initial commit}
  fi

  git -C "$PROJECT_ROOT" add -A
  if git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null; then
    echo "No new changes to stage (nothing different from what Git already has)."
    echo "If this is your first commit and the folder looks empty to Git, we add a tiny .gitkeep file."
    if [[ ! -f "$PROJECT_ROOT/.gitkeep" ]]; then
      printf '%s\n' '# Placeholder so the first commit has a file. You can delete this after real files are tracked.' >"$PROJECT_ROOT/.gitkeep"
    fi
    git -C "$PROJECT_ROOT" add -A
    if ! git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null; then
      git -C "$PROJECT_ROOT" commit -m "$MSG"
      _first_time_push_do_push
      return
    fi
    if git -C "$PROJECT_ROOT" rev-parse HEAD >/dev/null 2>&1; then
      echo ""
      echo "Your repo already has commits (everything may already be saved)."
      echo "Use option 6 when you change files, or option 4 to pull from GitHub."
      banner_success
      read -r -p "Press Enter to continue..."
      return
    fi
    echo "Creating an empty first commit (allowed by Git) so you can push to GitHub..."
    if ! git -C "$PROJECT_ROOT" commit --allow-empty -m "$MSG"; then
      banner_fail
      read -r -p "Press Enter to continue..."
      return
    fi
    _first_time_push_do_push
    return
  fi

  git -C "$PROJECT_ROOT" commit -m "$MSG"
  _first_time_push_do_push
}

cmd_clone_help() {
  echo ""
  echo "----- Clone this repo on ANOTHER computer -----"
  echo "1. Install Git for your OS (see option 1 on this menu)."
  echo "2. On GitHub: green Code button - copy HTTPS or SSH URL."
  echo "3. Run:  git clone <URL> <folder-name>"
  echo "4. Open folder in Cursor. Each session: Pull (option 4)."
  echo "5. When done: Save to GitHub (option 6)."
  echo ""
  read -r -p "Press Enter to continue..."
}

cmd_identity() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  echo "Current global user.name:"
  git config --global user.name 2>/dev/null || echo "  (not set)"
  echo "Current global user.email:"
  git config --global user.email 2>/dev/null || echo "  (not set)"
  echo ""
  read -r -p "Set global user.name (empty = skip): " N
  if [[ -n "${N// }" ]]; then git config --global user.name "$N"; fi
  read -r -p "Set global user.email (empty = skip): " E
  if [[ -n "${E// }" ]]; then git config --global user.email "$E"; fi
  echo ">>> Now:"
  git config --global --get user.name
  git config --global --get user.email
  read -r -p "Press Enter to continue..."
}

cmd_github_https_token() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo "Not a Git repo. Use option 2 first."; read -r -p "Press Enter to continue..."; return; fi

  echo ""
  echo "========== GitHub HTTPS — Personal Access Token =========="
  echo ""
  echo "GitHub no longer accepts account passwords for git over HTTPS."
  echo "You need a token (like an app password) and store it for this repo only."
  echo ""
  echo "--- How to create a token (pick one) ---"
  echo ""
  echo "A) CLASSIC token (simple):"
  echo "   1) Open:  https://github.com/settings/tokens"
  echo "   2) \"Generate new token\" → \"Generate new token (classic)\""
  echo "   3) Name: e.g. candling-laptop   Expiration: your choice"
  echo "   4) Scope: enable \"repo\" (full control of private repositories)"
  echo "   5) Generate, then COPY the token (starts with ghp_...) — shown once."
  echo ""
  echo "B) FINE-GRAINED token (least access):"
  echo "   1) Open:  https://github.com/settings/personal-access-tokens/new"
  echo "   2) Repository access: only the repos you need"
  echo "   3) Permissions: Repository contents → Read and write; Metadata → Read"
  echo "   4) Generate and copy the token."
  echo ""
  echo "Where it is stored (safe):"
  echo "   • File:  $PROJECT_ROOT/.git/gh-credential-store"
  echo "   • That path is INSIDE .git/ — it is NEVER committed or pushed."
  echo "   • This repo uses: git config credential.helper store --file=... (local only)"
  echo ""
  read -r -p "Open GitHub token page in browser now? [y/N]: " OPEN
  if [[ "${OPEN,,}" == "y" || "${OPEN,,}" == "yes" ]]; then
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "https://github.com/settings/tokens" 2>/dev/null || true
    elif command -v open >/dev/null 2>&1; then open "https://github.com/settings/tokens" 2>/dev/null || true
    else echo "Open manually: https://github.com/settings/tokens"
    fi
  fi
  echo ""
  echo "--- Save token for THIS repository ---"
  echo "    (empty username = cancel)"
  read -r -p "GitHub USERNAME (login name, not email): " GH_USER
  if [[ -z "${GH_USER// }" ]]; then echo "Cancelled."; read -r -p "Press Enter..."; return; fi
  read -r -s -p "Paste TOKEN (input hidden): " GH_TOKEN
  echo ""
  GH_TOKEN=$(echo "$GH_TOKEN" | tr -d '\n\r')
  if [[ -z "${GH_TOKEN// }" ]]; then echo "Empty token. Cancelled."; read -r -p "Press Enter..."; return; fi

  store="$PROJECT_ROOT/.git/gh-credential-store"
  printf 'https://%s:%s@github.com\n' "$GH_USER" "$GH_TOKEN" >"$store"
  chmod 600 "$store" 2>/dev/null || true

  git -C "$PROJECT_ROOT" config --local credential.helper "store --file=$store"
  echo ""
  echo ">>> Saved. Credential helper is set for this repo only."
  echo ">>> Try: option (4) Pull  or  option (6) Save to GitHub"
  echo ""
  read -r -p "Remove saved token from this PC? [y/N]: " RM
  if [[ "${RM,,}" == "y" || "${RM,,}" == "yes" ]]; then
    rm -f "$store"
    git -C "$PROJECT_ROOT" config --local --unset credential.helper 2>/dev/null || true
    echo ">>> Removed .git/gh-credential-store and local credential.helper."
  fi
  read -r -p "Press Enter to continue..."
}

cmd_diagnose_push_auth() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo "Not a Git repo. Use option 2 first."; read -r -p "Press Enter to continue..."; return; fi

  command -v clear >/dev/null 2>&1 && clear
  echo ""
  echo "========== Diagnose push / auth / remote =========="
  echo ""

  ORIGIN_URL="$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null || true)"
  if [[ -z "${ORIGIN_URL// }" ]]; then
    echo "No 'origin' remote is set."
    echo "Fix: use option (3) to set your GitHub repo URL."
    read -r -p "Open option (3) now? [Y/n]: " GO_REMOTE
    if [[ -z "${GO_REMOTE// }" || "${GO_REMOTE,,}" == "y" || "${GO_REMOTE,,}" == "yes" ]]; then
      cmd_set_remote
      return
    fi
    read -r -p "Press Enter to continue..."
    return
  fi

  echo "origin URL:"
  echo "  $ORIGIN_URL"
  echo ""

  if [[ "$ORIGIN_URL" =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    GH_OWNER="${BASH_REMATCH[1]}"
    GH_REPO="${BASH_REMATCH[2]}"
    echo "Detected GitHub target: $GH_OWNER/$GH_REPO"
    echo "Check in browser:"
    echo "  https://github.com/$GH_OWNER/$GH_REPO"
  else
    echo "Remote URL is not a standard github.com URL."
    echo "If this repo is on GitHub, verify option (3) URL."
  fi
  echo ""

  echo "Testing remote access: git ls-remote --heads origin"
  TMP_ERR="$(mktemp)"
  if git -C "$PROJECT_ROOT" ls-remote --heads origin >/dev/null 2>"$TMP_ERR"; then
    echo "Remote access OK."
  else
    ERR_TEXT="$(<"$TMP_ERR")"
    echo ">>> Access test failed."
    echo "Error output:"
    sed 's/^/    /' "$TMP_ERR"
    echo ""
    if [[ "$ERR_TEXT" =~ Repository[[:space:]]not[[:space:]]found ]]; then
      echo "Interpretation:"
      echo "  • Wrong remote URL, OR"
      echo "  • The repository is private and your credentials are missing/invalid, OR"
      echo "  • Your account has no access to that repository."
    elif [[ "$ERR_TEXT" =~ Authentication[[:space:]]failed|401|403|Invalid[[:space:]]username[[:space:]]or[[:space:]]password|Missing[[:space:]]or[[:space:]]invalid[[:space:]]credentials|could[[:space:]]not[[:space:]]read[[:space:]]Username ]]; then
      echo "Interpretation:"
      echo "  • Credentials/token are missing, expired, or wrong for this repo."
    else
      echo "Interpretation:"
      echo "  • Network, auth, or remote URL issue. See error above."
    fi
  fi
  rm -f "$TMP_ERR"
  echo ""

  echo "Credential helper (repo-local):"
  git -C "$PROJECT_ROOT" config --local --get credential.helper 2>/dev/null || echo "  (not set)"
  echo "Credential helper (global):"
  git -C "$PROJECT_ROOT" config --global --get credential.helper 2>/dev/null || echo "  (not set)"
  echo ""

  if [[ "$ORIGIN_URL" == https://github.com/* ]]; then
    echo "For HTTPS remotes, use option (11) to save a GitHub token for this repo."
  elif [[ "$ORIGIN_URL" == git@github.com:* ]]; then
    echo "This is SSH remote. If push fails, check SSH key access on GitHub."
  fi
  echo ""

  echo "Quick fixes:"
  echo "  1) Set/change origin URL now"
  echo "  2) Save GitHub HTTPS token now"
  echo "  Enter = back"
  read -r -p "Choice: " FIX
  case "$FIX" in
    1) cmd_set_remote ;;
    2) cmd_github_https_token ;;
    *) ;;
  esac
}

main_menu() {
  while true; do
    command -v clear >/dev/null 2>&1 && clear
    print_menu_top
    print_menu_context
    echo "**********************************************************************"
    echo "*  MENU  —  type a number, then press Enter                        *"
    echo "**********************************************************************"
    echo "  1 - Check Git / install instructions"
    echo "  2 - Init repository here (git init, branch main)"
    echo "  3 - Set or change remote origin (GitHub URL)"
    echo "  4 - Pull from GitHub (pull --rebase + status)"
    echo "  5 - Status (full)"
    echo "  6 - Save to GitHub (add all + commit + push)"
    echo "  7 - Set my name and email (git config --global)"
    echo "  8 - First-time wizard (init + remote + first push)"
    echo "  9 - How to clone on another PC"
    echo " 10 - Force push (after history rewrite; --force-with-lease)"
    echo " 11 - GitHub HTTPS token - how-to + save (fixes 401)"
    echo " 12 - Diagnose push/auth/remote errors (401, repository not found)"
    echo "  0 - Exit"
    echo "**********************************************************************"
    echo ""
    read -r -p "Enter choice [0-12]: " choice
    case "$choice" in
      1) cmd_check_git ;;
      2) cmd_init_repo ;;
      3) cmd_set_remote ;;
      4) cmd_pull ;;
      5) cmd_status ;;
      6) cmd_commit_push ;;
      7) cmd_identity ;;
      8) cmd_first_time_push ;;
      9) cmd_clone_help ;;
      10) cmd_force_push ;;
      11) cmd_github_https_token ;;
      12) cmd_diagnose_push_auth ;;
      0) echo "Bye."; exit 0 ;;
      *) echo "Unknown option."; sleep 1 ;;
    esac
  done
}

main_menu
