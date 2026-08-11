"""
Session + disk cache for recursive (Subfolders) directory scans.

Avoids full os.walk when returning to the same root with an unchanged
root mtime. Disk cache lives under the app config dir and is pruned on startup.

Cache keys include scan kind ("all" | "dirs" | "files") so a folders-only
listing is never served for an all-items request.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
CACHE_SCHEMA_VERSION = 2
MAX_DISK_ENTRIES = 50_000
MAX_DISK_AGE_DAYS = 7
DISK_SUBDIR = "scan_cache"
_VALID_KINDS = ("all", "dirs", "files")


# ------------------------------------------------------------
# Module state
# ------------------------------------------------------------
_session: Dict[Tuple[str, bool, str], Dict[str, Any]] = {}
_enabled = True
_config_dir: Optional[str] = None


# ------------------------------------------------------------
# Function: _normalizeKind
# ------------------------------------------------------------
def _normalizeKind(kind: Optional[str]) -> str:
    if kind in _VALID_KINDS:
        return kind
    return "all"


# ------------------------------------------------------------
# Function: configureScanCache
# Purpose: Set config directory and enabled flag (from settings).
# ------------------------------------------------------------
def configureScanCache(config_dir: Optional[str], enabled: bool = True) -> None:
    global _config_dir, _enabled
    _config_dir = config_dir
    _enabled = bool(enabled)


# ------------------------------------------------------------
# Function: isScanCacheEnabled
# ------------------------------------------------------------
def isScanCacheEnabled() -> bool:
    return bool(_enabled)


# ------------------------------------------------------------
# Function: setScanCacheEnabled
# ------------------------------------------------------------
def setScanCacheEnabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)


# ------------------------------------------------------------
# Function: _cacheKey
# ------------------------------------------------------------
def _cacheKey(root: str, show_hidden: bool, kind: str = "all") -> Tuple[str, bool, str]:
    return (
        os.path.normcase(os.path.normpath(root)),
        bool(show_hidden),
        _normalizeKind(kind),
    )


# ------------------------------------------------------------
# Function: _rootMtime
# ------------------------------------------------------------
def _rootMtime(root: str) -> Optional[float]:
    try:
        return float(os.path.getmtime(root))
    except OSError:
        return None


# ------------------------------------------------------------
# Function: _diskDir
# ------------------------------------------------------------
def _diskDir() -> Optional[str]:
    if not _config_dir:
        return None
    path = os.path.join(_config_dir, DISK_SUBDIR)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return path


# ------------------------------------------------------------
# Function: _diskFileName
# ------------------------------------------------------------
def _diskFileName(root: str, show_hidden: bool, kind: str = "all") -> str:
    k = _normalizeKind(kind)
    raw = f"{os.path.normcase(os.path.normpath(root))}|{int(bool(show_hidden))}|{k}"
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:40]
    return f"{digest}.json"


# ------------------------------------------------------------
# Function: getScanCache
# Purpose: Return cached entry list if valid for root+show_hidden+kind.
# ------------------------------------------------------------
def getScanCache(
    root: str,
    show_hidden: bool,
    kind: str = "all",
) -> Optional[List[dict]]:
    if not _enabled or not root:
        return None
    kind = _normalizeKind(kind)
    mtime = _rootMtime(root)
    if mtime is None:
        return None
    key = _cacheKey(root, show_hidden, kind)
    hit = _session.get(key)
    if hit is not None and abs(float(hit.get("root_mtime", -1)) - mtime) < 1e-6:
        entries = hit.get("entries")
        if isinstance(entries, list):
            return list(entries)

    disk = _loadDiskCache(root, show_hidden, mtime, kind)
    if disk is not None:
        _session[key] = {
            "entries": disk,
            "root_mtime": mtime,
            "captured_at": time.time(),
            "entry_count": len(disk),
        }
        return list(disk)
    return None


# ------------------------------------------------------------
# Function: putScanCache
# Purpose: Store entries in session (and disk when under size cap).
# ------------------------------------------------------------
def putScanCache(
    root: str,
    show_hidden: bool,
    entries: List[dict],
    kind: str = "all",
) -> None:
    if not _enabled or not root:
        return
    kind = _normalizeKind(kind)
    mtime = _rootMtime(root)
    if mtime is None:
        return
    key = _cacheKey(root, show_hidden, kind)
    payload = {
        "entries": list(entries),
        "root_mtime": mtime,
        "captured_at": time.time(),
        "entry_count": len(entries),
    }
    _session[key] = payload
    _saveDiskCache(root, show_hidden, mtime, entries, kind)


# ------------------------------------------------------------
# Function: invalidateScanCache
# Purpose: Drop session (+ disk) entry for a root, or all if root None.
#          When kind is None, clear all kinds for the root.
# ------------------------------------------------------------
def invalidateScanCache(
    root: Optional[str] = None,
    show_hidden: Optional[bool] = None,
    kind: Optional[str] = None,
) -> None:
    global _session
    if root is None:
        _session.clear()
        return

    kinds = (_normalizeKind(kind),) if kind is not None else _VALID_KINDS
    hiddens = (bool(show_hidden),) if show_hidden is not None else (True, False)

    for hidden in hiddens:
        for k in kinds:
            key = _cacheKey(root, hidden, k)
            _session.pop(key, None)
            _removeDiskFile(root, hidden, k)


# ------------------------------------------------------------
# Function: updateScanCacheFromEntries
# Purpose: After surgical edits, refresh session/disk for current root.
# ------------------------------------------------------------
def updateScanCacheFromEntries(
    root: str,
    show_hidden: bool,
    entries: List[dict],
    kind: str = "all",
) -> None:
    putScanCache(root, show_hidden, entries, kind=_normalizeKind(kind))


# ------------------------------------------------------------
# Disk helpers
# ------------------------------------------------------------
def _loadDiskCache(
    root: str,
    show_hidden: bool,
    expected_mtime: float,
    kind: str = "all",
) -> Optional[List[dict]]:
    kind = _normalizeKind(kind)
    folder = _diskDir()
    if not folder:
        return None
    path = os.path.join(folder, _diskFileName(root, show_hidden, kind))
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("schema", 0)) != CACHE_SCHEMA_VERSION:
        return None
    if os.path.normcase(os.path.normpath(data.get("root") or "")) != os.path.normcase(
        os.path.normpath(root)
    ):
        return None
    if bool(data.get("show_hidden")) != bool(show_hidden):
        return None
    if _normalizeKind(data.get("kind")) != kind:
        return None
    try:
        stored_mtime = float(data.get("root_mtime"))
    except (TypeError, ValueError):
        return None
    if abs(stored_mtime - expected_mtime) >= 1e-6:
        return None
    try:
        age = time.time() - float(data.get("captured_at", 0))
        if age > MAX_DISK_AGE_DAYS * 86400:
            return None
    except (TypeError, ValueError):
        return None
    entries = data.get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_DISK_ENTRIES:
        return None
    return entries


def _saveDiskCache(
    root: str,
    show_hidden: bool,
    mtime: float,
    entries: List[dict],
    kind: str = "all",
) -> None:
    if len(entries) > MAX_DISK_ENTRIES:
        return
    kind = _normalizeKind(kind)
    folder = _diskDir()
    if not folder:
        return
    path = os.path.join(folder, _diskFileName(root, show_hidden, kind))
    # Strip non-JSON-serializable noise; entries are plain dicts already.
    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "root": os.path.normpath(root),
        "show_hidden": bool(show_hidden),
        "kind": kind,
        "root_mtime": mtime,
        "captured_at": time.time(),
        "entry_count": len(entries),
        "entries": entries,
    }
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except OSError:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _removeDiskFile(root: str, show_hidden: bool, kind: str = "all") -> None:
    folder = _diskDir()
    if not folder:
        return
    path = os.path.join(folder, _diskFileName(root, show_hidden, kind))
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


# ------------------------------------------------------------
# Function: pruneScanCacheOnStartup
# Purpose: Delete expired / invalid disk cache files.
# ------------------------------------------------------------
def pruneScanCacheOnStartup() -> int:
    folder = _diskDir()
    if not folder or not os.path.isdir(folder):
        return 0
    removed = 0
    now = time.time()
    max_age = MAX_DISK_AGE_DAYS * 86400
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                os.remove(path)
                removed += 1
                continue
            if int(data.get("schema", 0)) != CACHE_SCHEMA_VERSION:
                os.remove(path)
                removed += 1
                continue
            age = now - float(data.get("captured_at", 0))
            if age > max_age:
                os.remove(path)
                removed += 1
                continue
            count = int(data.get("entry_count", 0))
            if count > MAX_DISK_ENTRIES:
                os.remove(path)
                removed += 1
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed
