"""
Shared os.scandir traversal used by Subfolders listing and library indexing.
Does not follow directory symlinks. Hidden-file rules match the file panel.
"""

import fnmatch
import os
import stat
import time


# ------------------------------------------------------------
# Function: skipHiddenEntry
# Purpose: True if a DirEntry should be omitted when hidden files
#          are turned off. Uses cached DirEntry.stat() on Windows.
# ------------------------------------------------------------
def skipHiddenEntry(entry, show_hidden):
    if show_hidden:
        return False
    if entry.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            st = entry.stat(follow_symlinks=False)
            attrs = getattr(st, "st_file_attributes", 0)
            hidden_bit = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2)
            if attrs & hidden_bit:
                return True
        except OSError:
            return True
    return False


# ------------------------------------------------------------
# Function: nativeFileId
# Purpose: Best-effort stable identity from os.stat result.
# ------------------------------------------------------------
def nativeFileId(st):
    try:
        dev = getattr(st, "st_dev", 0)
        ino = getattr(st, "st_ino", 0)
        if not ino:
            return ""
        return f"{int(dev)}:{int(ino)}"
    except (TypeError, ValueError, AttributeError):
        return ""


# ------------------------------------------------------------
# Function: canonicalRelativePath
# Purpose: Store library-relative paths with forward slashes.
# ------------------------------------------------------------
def canonicalRelativePath(path):
    text = (path or "").replace("\\", "/")
    parts = [part for part in text.split("/") if part and part != "."]
    return "/".join(parts)


# ------------------------------------------------------------
# Function: relativeToRoot
# Purpose: Convert an absolute path to a canonical relative path.
# ------------------------------------------------------------
def relativeToRoot(full_path, root_path):
    try:
        rel = os.path.relpath(full_path, root_path)
    except ValueError:
        return None
    if rel == ".":
        return ""
    if rel.startswith(".."):
        return None
    return canonicalRelativePath(rel)


# ------------------------------------------------------------
# Function: parseGlobList
# Purpose: Accept JSON lists or newline/comma separated text.
# ------------------------------------------------------------
def parseGlobList(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("["):
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (TypeError, ValueError):
            pass
    parts = []
    for raw in text.replace(",", "\n").splitlines():
        item = raw.strip()
        if item:
            parts.append(item)
    return parts


# ------------------------------------------------------------
# Function: matchesGlobList
# Purpose: Match a relative path or basename against glob patterns.
# ------------------------------------------------------------
def matchesGlobList(rel_path, name, patterns):
    if not patterns:
        return False
    rel = canonicalRelativePath(rel_path)
    base = name or os.path.basename(rel)
    for pattern in patterns:
        if fnmatch.fnmatch(base, pattern) or fnmatch.fnmatch(rel, pattern):
            return True
        if rel and fnmatch.fnmatch(rel, "*/" + pattern):
            return True
    return False


# ------------------------------------------------------------
# Function: shouldIncludePath
# Purpose: Include/exclude glob policy. Empty include list means all.
# ------------------------------------------------------------
def shouldIncludePath(rel_path, name, include_globs, exclude_globs):
    if matchesGlobList(rel_path, name, exclude_globs):
        return False
    if not include_globs:
        return True
    return matchesGlobList(rel_path, name, include_globs)


# ------------------------------------------------------------
# Function: isSkippedDirectoryName
# Purpose: Ignore recycle-bin / system volume folders during walks.
# ------------------------------------------------------------
def isSkippedDirectoryName(name):
    if not name:
        return False
    lowered = name.lower()
    return lowered.startswith("$recycle") or lowered in (
        "system volume information",
        "$recycle.bin",
    )


# ------------------------------------------------------------
# Function: statEntry
# Purpose: Collect size, mtime_ns, native id from a DirEntry/path.
# ------------------------------------------------------------
def statEntry(entry=None, path="", follow_symlinks=False):
    st = None
    try:
        if entry is not None:
            st = entry.stat(follow_symlinks=follow_symlinks)
        elif path:
            st = os.stat(path, follow_symlinks=follow_symlinks)
    except OSError:
        return {
            "size": 0,
            "mtime": 0.0,
            "mtime_ns": 0,
            "native_id": "",
        }
    mtime = float(getattr(st, "st_mtime", 0.0) or 0.0)
    mtime_ns = int(getattr(st, "st_mtime_ns", int(mtime * 1_000_000_000)))
    return {
        "size": int(getattr(st, "st_size", 0) or 0),
        "mtime": mtime,
        "mtime_ns": mtime_ns,
        "native_id": nativeFileId(st),
    }


# ------------------------------------------------------------
# Function: walkFilesystem
# Purpose: Iterative scandir walk. Yields dicts with name,
#          relative_path (forward slashes), display_path (OS
#          separators), full_path, is_dir, and stat fields.
# ------------------------------------------------------------
def walkFilesystem(
    root,
    show_hidden=False,
    collect_dirs=True,
    collect_files=True,
    include_globs=None,
    exclude_globs=None,
    include_root=False,
    skip_names=None,
    cancel_check=None,
    progress_cb=None,
    progress_interval_sec=0.25,
    progress_every_items=4096,
):
    root = os.path.normpath(root or "")
    if not root or not os.path.isdir(root):
        return

    include_globs = parseGlobList(include_globs)
    exclude_globs = parseGlobList(exclude_globs)
    skip_names = set(skip_names or ())
    skip_names.add(".tcc_library_root.json")

    item_count = 0
    last_emit = time.monotonic()

    def maybeProgress(current_dir):
        nonlocal last_emit
        if progress_cb is None:
            return
        now = time.monotonic()
        if (
            now - last_emit >= progress_interval_sec
            or item_count % progress_every_items == 0
        ):
            progress_cb(item_count, current_dir)
            last_emit = now

    def yieldItem(name, relative_path, full_path, is_dir, stats):
        nonlocal item_count
        if relative_path and not shouldIncludePath(
            relative_path, name, include_globs, exclude_globs
        ):
            return False
        display = relative_path.replace("/", os.sep) if relative_path else name
        item_count += 1
        yield_payload = {
            "name": name,
            "relative_path": relative_path,
            "display_path": display,
            "full_path": full_path,
            "is_dir": bool(is_dir),
            "size": -1 if is_dir else int(stats.get("size", 0) or 0),
            "mtime": float(stats.get("mtime", 0.0) or 0.0),
            "mtime_ns": int(stats.get("mtime_ns", 0) or 0),
            "native_id": stats.get("native_id", "") or "",
        }
        return yield_payload

    if include_root:
        stats = statEntry(path=root)
        payload = yieldItem(os.path.basename(root) or root, "", root, True, stats)
        if payload:
            yield payload

    stack = [(root, "")]
    while stack:
        if cancel_check and cancel_check():
            return
        dirpath, rel_dir = stack.pop()
        try:
            with os.scandir(dirpath) as iterator:
                child_dirs = []
                for entry in iterator:
                    if cancel_check and cancel_check():
                        return
                    name = entry.name
                    if name in skip_names or isSkippedDirectoryName(name):
                        continue
                    if skipHiddenEntry(entry, show_hidden):
                        continue
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        continue
                    if is_dir:
                        try:
                            if entry.is_symlink():
                                continue
                        except OSError:
                            continue
                    rel = canonicalRelativePath(
                        os.path.join(rel_dir, name) if rel_dir else name
                    )
                    full_path = entry.path
                    if is_dir:
                        if matchesGlobList(rel, name, exclude_globs):
                            continue
                        child_dirs.append((full_path, rel))
                        if collect_dirs:
                            stats = statEntry(entry=entry)
                            payload = yieldItem(name, rel, full_path, True, stats)
                            if payload:
                                yield payload
                    elif collect_files:
                        stats = statEntry(entry=entry)
                        payload = yieldItem(name, rel, full_path, False, stats)
                        if payload:
                            yield payload
                for full_path, rel in reversed(child_dirs):
                    stack.append((full_path, rel))
        except (OSError, PermissionError):
            pass
        maybeProgress(dirpath)
