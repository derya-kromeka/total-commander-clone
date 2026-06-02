#!/usr/bin/env bash
#
# Create an annotated Git tag vX.Y.Z from Cargo.toml [package].version and push it to origin.
#
# This is meant for releases — NOT for every `cargo build`. See scripts/README-DEV.txt.
#
# Usage:
#   bash scripts/git-subscripts/push-version-tag.sh
#   bash scripts/git-subscripts/push-version-tag.sh /path/to/repo
#   bash scripts/git-subscripts/push-version-tag.sh --dry-run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
PROJECT_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    *)
      if [[ -z "$PROJECT_ROOT" && -d "$1" ]]; then
        PROJECT_ROOT="$(cd "$1" && pwd)"
      fi
      shift
      ;;
  esac
done
if [[ -z "$PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi
cd "$PROJECT_ROOT" || exit 1

if ! command -v git >/dev/null 2>&1; then
  echo "git is not installed or not in PATH." >&2
  exit 1
fi

VERSION="$(bash "$SCRIPT_DIR/../subscripts/version-from-cargo.sh")"
TAG="v${VERSION}"

echo ">>> Cargo.toml version: $VERSION"
echo ">>> Git tag to create:  $TAG"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo ">>> Tag $TAG already exists locally."
  echo "    To push it:  git push origin $TAG"
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ">>> Dry run: would run: git tag -a $TAG -m \"Release $TAG\""
  echo ">>> Dry run: would run: git push origin $TAG"
  exit 0
fi

git tag -a "$TAG" -m "Release $TAG"
echo ">>> Created tag $TAG"
echo ">>> Pushing tag to origin..."
git push origin "$TAG"
echo ">>> Done."
