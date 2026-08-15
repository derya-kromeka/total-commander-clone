"""
Path, marker, and identity helpers for library roots.
Shared by the catalog, manager, and discovery scans.
"""

import ctypes
import json
import os
import string

from filesystem_scanner import canonicalRelativePath


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
LIBRARY_MARKER_FILENAME = ".tcc_library_root.json"
LIBRARY_MARKER_VERSION = 1


# ------------------------------------------------------------
# Helper: parse a tag into (category, value) pair.
# ------------------------------------------------------------
def parseTagCategory(tag):
    if ":" in tag:
        category, _, value = tag.partition(":")
        return (category.strip(), value.strip())
    return ("", tag.strip())


# ------------------------------------------------------------
# Helper: normalize a filesystem path for comparisons
# ------------------------------------------------------------
def normalizePath(path):
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


# ------------------------------------------------------------
# Helper: safe common-path containment check
# ------------------------------------------------------------
def isPathInsideRoot(path, root_path):
    norm_path = normalizePath(path)
    norm_root = normalizePath(root_path)
    if not norm_path or not norm_root:
        return False
    try:
        return os.path.commonpath([norm_path, norm_root]) == norm_root
    except ValueError:
        return False


# ------------------------------------------------------------
# Helper: stable folder key inside a library root
# ------------------------------------------------------------
def buildFolderKey(library_id, root_id, relative_path):
    rel = canonicalRelativePath(relative_path)
    return f"{library_id}:{root_id}:{rel}"


# ------------------------------------------------------------
# Helper: set hidden attribute on Windows marker files
# ------------------------------------------------------------
def setHiddenFile(path):
    if os.name != "nt" or not path:
        return
    try:
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)
    except Exception:
        pass


# ------------------------------------------------------------
# Helper: read a marker file from a candidate root folder
# ------------------------------------------------------------
def readLibraryMarker(root_path):
    marker_path = os.path.join(root_path, LIBRARY_MARKER_FILENAME)
    if not os.path.isfile(marker_path):
        return None
    try:
        with open(marker_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ------------------------------------------------------------
# Helper: write a portable root marker
# ------------------------------------------------------------
def writeLibraryMarker(root_path, library, root):
    marker_path = os.path.join(root_path, LIBRARY_MARKER_FILENAME)
    data = {
        "version": LIBRARY_MARKER_VERSION,
        "library_id": (library or {}).get("id", ""),
        "library_name": (library or {}).get("name", ""),
        "root_id": (root or {}).get("id", ""),
        "root_name": (root or {}).get("name", ""),
    }
    try:
        with open(marker_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
        setHiddenFile(marker_path)
        return True
    except IOError:
        return False


# ------------------------------------------------------------
# Helper: remove a marker file if present
# ------------------------------------------------------------
def removeLibraryMarker(root_path):
    marker_path = os.path.join(root_path, LIBRARY_MARKER_FILENAME)
    try:
        if os.path.isfile(marker_path):
            os.remove(marker_path)
            return True
    except OSError:
        return False
    return False


# ------------------------------------------------------------
# Helper: breadth-first directory scan for marker files
# ------------------------------------------------------------
def findMarkerDirectories(base_path, max_depth=2, max_directories=250):
    if not base_path or not os.path.isdir(base_path):
        return []

    results = []
    queue = [(base_path, 0)]
    seen = set()

    while queue and len(seen) < max_directories:
        current_path, depth = queue.pop(0)
        norm_current = normalizePath(current_path)
        if norm_current in seen:
            continue
        seen.add(norm_current)

        marker = readLibraryMarker(current_path)
        if marker:
            results.append((current_path, marker))

        if depth >= max_depth:
            continue

        try:
            with os.scandir(current_path) as entries:
                for entry in entries:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    name = entry.name
                    if name.startswith("$RECYCLE") or name in ("System Volume Information",):
                        continue
                    queue.append((entry.path, depth + 1))
        except OSError:
            continue

    return results


# ------------------------------------------------------------
# Helper: candidate roots for removable-drive scans
# ------------------------------------------------------------
def candidateScanBases():
    bases = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.isdir(drive):
                bases.append(drive)
    else:
        for candidate in ("/Volumes", "/media", "/mnt", "/"):
            if os.path.isdir(candidate):
                bases.append(candidate)
    return bases
