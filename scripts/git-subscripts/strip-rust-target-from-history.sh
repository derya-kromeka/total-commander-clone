#!/usr/bin/env bash
# One-time: remove `target/` from ALL commits so Git stops storing/uploading build artifacts.
# Requires: a clean working tree (commit or stash first). Then run from repo root:
#   bash scripts/git-subscripts/strip-rust-target-from-history.sh
# After this, push with: git push --force-with-lease origin main
# (or git-menu option 10)

set -euo pipefail
root="$(git rev-parse --show-toplevel)"
cd "$root"

if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
  echo "Working tree not clean. Commit or stash, then try again."
  exit 1
fi

echo "Removing path 'target/' from entire history (this rewrites commits)..."
git filter-branch --force --index-filter 'git rm -rf --cached --ignore-unmatch target' --prune-empty HEAD

rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "Done. .git size should be small now. Push with: git push --force-with-lease origin main"
echo "Note: collaborators may need to re-clone."
