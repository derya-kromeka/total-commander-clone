#!/usr/bin/env bash
#
# Git / GitHub all-in-one menu.
# Default: this file lives in YOUR_PROJECT/scripts/ → project root is one folder up.
#
# Run from ANY directory — no "cd" needed:
#   /full/path/to/Candling-Rust/scripts/git-hub-menu.sh
#   /full/path/to/Candling-Rust/git-menu          (short launcher in repo root)
#
# Optional project root (overrides the path above):
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

cd "$PROJECT_ROOT" || exit 1

GIT_OK=0
command -v git >/dev/null 2>&1 && GIT_OK=1

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

print_header() {
  echo ""
  echo "=========================================="
  echo "  Git / GitHub helper"
  echo "=========================================="
  echo "  Project root: $PROJECT_ROOT"
  echo "  This script:  $SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
  echo "=========================================="
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
    echo ">>> Already a Git repository (.git exists)."
  else
    echo ">>> git init + branch main"
    (cd "$PROJECT_ROOT" && git init && git branch -M main)
    echo ">>> Done."
  fi
  read -r -p "Press Enter to continue..."
}

cmd_set_remote() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    echo ">>> Not a Git repo yet. Use option (2) Init first."
    read -r -p "Press Enter to continue..."
    return
  fi
  echo "Paste GitHub repo URL (HTTPS or git@... SSH). Empty = cancel."
  read -r -p "origin URL: " URL
  if [[ -z "${URL// }" ]]; then echo "Cancelled."; read -r -p "Press Enter..."; return; fi
  if git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo ">>> Remote 'origin' exists. Updating URL."
    git -C "$PROJECT_ROOT" remote set-url origin "$URL"
  else
    git -C "$PROJECT_ROOT" remote add origin "$URL"
  fi
  echo ">>> origin is now:"
  git -C "$PROJECT_ROOT" remote -v
  read -r -p "Press Enter to continue..."
}

cmd_show_remote() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo."; read -r -p "Press Enter..."; return; fi
  git -C "$PROJECT_ROOT" remote -v || true
  read -r -p "Press Enter to continue..."
}

cmd_pull() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo."; read -r -p "Press Enter..."; return; fi
  echo ">>> git pull --rebase"
  git -C "$PROJECT_ROOT" pull --rebase || true
  echo ">>> git status"
  git -C "$PROJECT_ROOT" status -sb
  read -r -p "Press Enter to continue..."
}

cmd_status() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo."; read -r -p "Press Enter..."; return; fi
  git -C "$PROJECT_ROOT" status
  read -r -p "Press Enter to continue..."
}

cmd_commit_push() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo."; read -r -p "Press Enter..."; return; fi

  if ! git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo ""
    echo ">>> No \"origin\" remote is set yet. You need your GitHub repo URL (HTTPS or SSH)."
    echo "    On GitHub: open your repo — green \"Code\" button — copy the URL."
    echo "    Then use menu option (3), or set remote now."
    read -r -p "Set remote now? [y/N]: " CP_OR
    if [[ "${CP_OR,,}" == "y" || "${CP_OR,,}" == "yes" ]]; then
      cmd_set_remote
    fi
    return
  fi

  GIT_UN="$(git -C "$PROJECT_ROOT" config --get user.name 2>/dev/null || true)"
  GIT_UE="$(git -C "$PROJECT_ROOT" config --get user.email 2>/dev/null || true)"
  if [[ -z "${GIT_UN// }" || -z "${GIT_UE// }" ]]; then
    echo ""
    echo ">>> Git user.name or user.email is not set. Commits will fail until you set them."
    echo "    Use menu option (7) for global name/email."
    read -r -p "Configure identity now? [y/N]: " CP_ID
    if [[ "${CP_ID,,}" == "y" || "${CP_ID,,}" == "yes" ]]; then
      cmd_identity
      return
    fi
    echo ">>> Continuing anyway (commit may fail)."
  fi

  SUG="$(changelog_version)"
  if [[ -n "$SUG" ]]; then
    echo "Suggested from CHANGELOG.md: $SUG"
    read -r -p "Commit message [$SUG] (Enter = use version): " MSG
    MSG=${MSG:-$SUG}
  else
    read -r -p "Commit message: " MSG
  fi
  if [[ -z "${MSG// }" ]]; then echo "Empty message. Cancelled."; read -r -p "Press Enter..."; return; fi

  CUR_BRANCH="$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || true)"
  [[ -z "${CUR_BRANCH// }" ]] && CUR_BRANCH="(unknown)"
  echo ""
  echo ">>> Will run: git add -A → commit → push to origin (current branch: $CUR_BRANCH)"
  read -r -p "Proceed? [Y/n]: " CP_GO
  if [[ "${CP_GO,,}" == "n" || "${CP_GO,,}" == "no" ]]; then echo "Cancelled."; read -r -p "Press Enter..."; return; fi

  TMP_LS_ERR="$(mktemp)"
  if ! git -C "$PROJECT_ROOT" ls-remote --heads origin >/dev/null 2>"$TMP_LS_ERR"; then
    echo ""
    echo ">>> Could not reach the remote (offline, firewall, DNS, or missing auth for ls-remote)."
    echo "    Fix credentials with option (11) or diagnosis (12)."
    read -r -p "Try push anyway? [Y/n]: " CP_TRY
    if [[ "${CP_TRY,,}" == "n" || "${CP_TRY,,}" == "no" ]]; then
      rm -f "$TMP_LS_ERR"
      read -r -p "Press Enter to continue..."
      return
    fi
  fi
  rm -f "$TMP_LS_ERR"

  COMMIT_MSG_FILE="$(mktemp)"
  printf '%s' "$MSG" >"$COMMIT_MSG_FILE"

  echo ""
  echo ">>> git add -A"
  git -C "$PROJECT_ROOT" add -A
  if git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null; then
    echo ">>> Nothing to commit (no changes)."
  else
    if ! git -C "$PROJECT_ROOT" commit -F "$COMMIT_MSG_FILE"; then
      rm -f "$COMMIT_MSG_FILE"
      echo ""
      echo ">>> Commit failed. Set user.name and user.email with option (7), or fix pre-commit hooks."
      read -r -p "Press Enter to continue..."
      return
    fi
  fi
  rm -f "$COMMIT_MSG_FILE"

  TMP_PUSH_ERR="$(mktemp)"
  echo ">>> git push"
  if ! git -C "$PROJECT_ROOT" push 2>"$TMP_PUSH_ERR"; then
    echo ""
    echo ">>> Push did not succeed. Tips:"
    echo "    • First push / no upstream:  git push -u origin main"
    echo "    • GitHub repo already has README/commits:  git pull --rebase origin main  then push again"
    echo "    • 'Unrelated histories':  git pull origin main --allow-unrelated-histories --no-edit"
    echo "    • HTTPS auth: use a token (option 11), not your password."
    echo "    • Diagnosis: option (12)."
    echo ""
    echo ">>> Last lines from Git:"
    tail -n 12 "$TMP_PUSH_ERR" 2>/dev/null || true
  fi
  rm -f "$TMP_PUSH_ERR"
  read -r -p "Press Enter to continue..."
}

cmd_force_push() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo."; read -r -p "Press Enter..."; return; fi
  echo ">>> Force push overwrites the remote branch with your local history."
  echo "    Use ONLY after a history rewrite (e.g. stripping target/) or if you know why."
  echo "    Collaborators must re-clone or reset after this."
  read -r -p "Type YES to run: git push --force-with-lease origin main : " CONF
  if [[ "$CONF" != "YES" ]]; then echo "Cancelled."; read -r -p "Press Enter..."; return; fi
  echo ">>> git push --force-with-lease origin main"
  git -C "$PROJECT_ROOT" push --force-with-lease origin main || echo ">>> Fix errors above (auth, branch name)."
  read -r -p "Press Enter to continue..."
}

cmd_first_time_push() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  echo "This wizard: init (if needed), optional remote, add all, commit, push -u origin main"
  echo ""
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    git -C "$PROJECT_ROOT" init
    git -C "$PROJECT_ROOT" branch -M main
  fi
  if ! git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo "Paste your GitHub repo URL (HTTPS or git@...)."
    echo "  • Brand-new empty repo: OK."
    echo "  • Repo with README/license: OK — we will pull remote commits before push."
    read -r -p "origin URL: " URL
    if [[ -n "${URL// }" ]]; then
      git -C "$PROJECT_ROOT" remote add origin "$URL"
    else
      echo "No URL — set remote later with option (3)."
    fi
  fi
  DEF_MSG="$(changelog_version)"
  if [[ -n "$DEF_MSG" ]]; then
    read -r -p "First commit message [$DEF_MSG] (Enter = use version): " MSG
    MSG=${MSG:-$DEF_MSG}
  else
    read -r -p "First commit message [Initial commit]: " MSG
    MSG=${MSG:-Initial commit}
  fi
  git -C "$PROJECT_ROOT" add -A
  if git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null && [[ -z "$(git -C "$PROJECT_ROOT" ls-files)" ]]; then
    echo ">>> No files tracked. Creating .gitkeep in project root so Git has something to commit."
    touch "$PROJECT_ROOT/.gitkeep"
    git -C "$PROJECT_ROOT" add -A
  fi
  if ! git -C "$PROJECT_ROOT" diff --cached --quiet 2>/dev/null; then
    git -C "$PROJECT_ROOT" commit -m "$MSG"
  else
    echo ">>> Nothing new to commit."
  fi
  if git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo ">>> Fetching origin (detect if GitHub already has commits)..."
    git -C "$PROJECT_ROOT" fetch origin 2>/dev/null || {
      echo ">>> fetch failed (network or auth). For HTTPS, set a token with option (11)."
      read -r -p "Press Enter to continue..."
      return
    }
    MAIN_REMOTE=""
    if git -C "$PROJECT_ROOT" rev-parse origin/main >/dev/null 2>&1; then
      MAIN_REMOTE=main
    elif git -C "$PROJECT_ROOT" rev-parse origin/master >/dev/null 2>&1; then
      MAIN_REMOTE=master
    fi
    if [[ -n "$MAIN_REMOTE" ]]; then
      RCOUNT=$(git -C "$PROJECT_ROOT" rev-list --count "origin/$MAIN_REMOTE" 2>/dev/null || echo 0)
      if [[ "$RCOUNT" -gt 0 ]]; then
        echo ""
        echo ">>> Remote already has $RCOUNT commit(s) on $MAIN_REMOTE (repo is NOT empty)."
        echo "    We merge (not rebase) so unrelated GitHub + local histories do not get stuck in conflicts."
        echo "    Overlapping files keep YOUR local versions (-X ours)."
        echo ""
        read -r -p "Merge origin/$MAIN_REMOTE into this branch now? [Y/n]: " DO
        if [[ -z "${DO// }" || "${DO,,}" == "y" || "${DO,,}" == "yes" ]]; then
          if ! git -C "$PROJECT_ROOT" merge "origin/$MAIN_REMOTE" -m "Merge origin/$MAIN_REMOTE" 2>/dev/null; then
            echo ">>> Trying merge with --allow-unrelated-histories -X ours ..."
            git -C "$PROJECT_ROOT" merge "origin/$MAIN_REMOTE" --allow-unrelated-histories -X ours -m "Merge origin/$MAIN_REMOTE; prefer local on overlaps" || {
              echo ">>> Merge still failed — resolve conflicts manually, then: git add -A && git commit"
            }
          fi
        fi
      fi
    fi
    echo ">>> git push -u origin main"
    if ! git -C "$PROJECT_ROOT" push -u origin main; then
      echo ""
      echo ">>> Push failed. Common fixes:"
      echo "    • HTTPS: use a Personal Access Token (option 11), not your GitHub password."
      echo "    • Remote has commits you lack:  git merge origin/main --allow-unrelated-histories -X ours"
      echo "    • Stuck mid-rebase:  git rebase --abort  then merge as above"
      echo "    • Wrong branch name:  git branch -M main   (or push your current branch name)"
    fi
  else
    echo ">>> No 'origin' remote. Add it with option (3), then use option (6) or push manually."
  fi
  read -r -p "Press Enter to continue..."
}

cmd_clone_help() {
  echo ""
  echo "----- Clone this repo on ANOTHER computer -----"
  echo "1. Install Git."
  echo "2. Copy the HTTPS or SSH clone URL from GitHub (green Code button)."
  echo "3. Run:"
  echo "     git clone <URL> <folder-name>"
  echo "4. Open that folder in Cursor. Before each session: Pull (option 4)."
  echo "5. When done: Commit + push (option 6)."
  echo ""
  read -r -p "Press Enter to continue..."
}

cmd_identity() {
  if [[ "$GIT_OK" -ne 1 ]]; then suggest_install_git; read -r -p "Press Enter..."; return; fi
  echo "Current Git user (global):"
  git config --global user.name 2>/dev/null || echo "  (not set)"
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
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo. Use option (2) first."; read -r -p "Press Enter..."; return; fi

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
  if [[ ! -d "$PROJECT_ROOT/.git" ]]; then echo ">>> Not a Git repo. Use option (2) first."; read -r -p "Press Enter..."; return; fi

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
    echo ">>> Remote access OK."
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
    print_header
    if [[ "$GIT_OK" -eq 1 ]]; then
      echo "  Git: $(git --version | head -n1)"
    else
      echo "  Git: NOT FOUND — use option 1"
    fi
    echo ""
    echo "  1) Check Git / install instructions"
    echo "  2) Init repository here (git init, branch main)"
    echo "  3) Set or change remote 'origin' (GitHub URL)"
    echo "  4) Pull from GitHub (git pull --rebase + status)"
    echo "  5) Status (full)"
    echo "  6) Save to GitHub (add all + commit + push)"
    echo "  7) Set my name and email (git config --global)"
    echo "  8) First-time wizard (init + remote + first push)"
    echo "  9) How to clone on another PC"
    echo " 10) Force push to GitHub (after history rewrite; --force-with-lease)"
    echo " 11) GitHub HTTPS token — how-to + save locally (fixes 401 / pull & push)"
    echo " 12) Diagnose push/auth/remote errors (401, repository not found)"
    echo "  0) Exit"
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
