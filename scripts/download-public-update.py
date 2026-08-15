#!/usr/bin/env python3
"""
Download a GitHub branch zip and merge it into the project folder.
Used when Git is not installed (Linux/macOS update path).

Usage:
  python download-public-update.py PROJECT_ROOT [branch] [owner] [repo]
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

DEFAULT_OWNER = "derya-kromeka"
DEFAULT_REPO = "total-commander-clone"
DEFAULT_BRANCH = "main"

EXCLUDE_DIRS = {
    ".git",
    "dist",
    "dist_build",
    ".venv",
    "venv",
    "__pycache__",
    ".cursor",
    "backup",
    ".idea",
    ".vscode",
}
EXCLUDE_FILES = {".git-account.json", ".git-account.pat"}


def merge_tree(src_root: str, dest_root: str) -> None:
    for dirpath, dirnames, filenames in os.walk(src_root):
        rel = os.path.relpath(dirpath, src_root)
        dirnames[:] = [name for name in dirnames if name not in EXCLUDE_DIRS]
        if rel == ".":
            dest_dir = dest_root
        else:
            parts = rel.replace("\\", "/").split("/")
            if any(part in EXCLUDE_DIRS for part in parts):
                continue
            dest_dir = os.path.join(dest_root, rel)
        os.makedirs(dest_dir, exist_ok=True)
        for name in filenames:
            if name in EXCLUDE_FILES:
                continue
            src = os.path.join(dirpath, name)
            dst = os.path.join(dest_dir, name)
            shutil.copy2(src, dst)


def main(argv: list) -> int:
    if len(argv) < 2:
        print("Usage: download-public-update.py PROJECT_ROOT [branch] [owner] [repo]", file=sys.stderr)
        return 2
    project_root = os.path.abspath(argv[1])
    branch = argv[2] if len(argv) > 2 and argv[2] else DEFAULT_BRANCH
    owner = argv[3] if len(argv) > 3 and argv[3] else DEFAULT_OWNER
    repo = argv[4] if len(argv) > 4 and argv[4] else DEFAULT_REPO
    if not os.path.isdir(project_root):
        print(f"Project root not found: {project_root}", file=sys.stderr)
        return 1

    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    print(f"==> Downloading public zip (no Git / no login)")
    print(f"    {zip_url}")

    tmp = tempfile.mkdtemp(prefix="tcc-update-")
    try:
        zip_path = os.path.join(tmp, "source.zip")
        req = urllib.request.Request(
            zip_url,
            headers={"User-Agent": "TotalCommanderClone-Updater"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as out:
            shutil.copyfileobj(resp, out)

        extract_dir = os.path.join(tmp, "extract")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        entries = [
            os.path.join(extract_dir, name)
            for name in os.listdir(extract_dir)
            if os.path.isdir(os.path.join(extract_dir, name))
        ]
        if not entries:
            print("Zip archive had no top-level folder.", file=sys.stderr)
            return 1
        src_root = entries[0]
        print("==> Merging into project (preserving dist, .venv, local git data)...")
        merge_tree(src_root, project_root)
        print("    Source files updated from GitHub zip.")
        return 0
    except Exception as exc:
        print(f"Download/merge failed: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
