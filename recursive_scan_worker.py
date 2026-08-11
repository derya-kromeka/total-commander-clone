"""
Background recursive directory scan for FileSystemModel (Subfolders mode).
Runs on a QThread; supports cooperative cancel between directory iterations.

Uses os.scandir so Windows DirEntry.stat()/is_dir() come from FindNextFile
data (no extra syscall per entry). When kind is "dirs" or "files", only
matching entries are collected — still recursing as needed.
"""

import os
import stat
import time

from PyQt5.QtCore import QThread, pyqtSignal


# ------------------------------------------------------------
# Function: _skip_hidden_entry
# Purpose: True if DirEntry should be omitted when hidden are off.
#          Uses cached DirEntry.stat() on Windows (no extra syscall).
# ------------------------------------------------------------
def _skip_hidden_entry(entry, show_hidden):
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


# ============================================================
# Class: RecursiveScanThread
# Purpose: Walks root recursively building the same entry dicts
#          as FileSystemModel. Emits progress; checks cancel
#          between directories. kind prunes files or dirs.
# ============================================================
class RecursiveScanThread(QThread):
    """
    Walks root recursively building the same entry dicts as FileSystemModel.
    Emits progress periodically; checks cancel between directory iterations.
    kind: "all" | "dirs" | "files" — collect only matching entry types.
    """

    progress = pyqtSignal(int, str)
    finishedScan = pyqtSignal(int, list)
    scanCancelled = pyqtSignal(int)

    _PROGRESS_INTERVAL_SEC = 0.25
    _PROGRESS_EVERY_ITEMS = 4096

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, scan_id, root, show_hidden, kind="all", parent=None):
        super().__init__(parent)
        self._scan_id = scan_id
        self._root = os.path.normpath(root)
        self._show_hidden = bool(show_hidden)
        kind = kind if kind in ("all", "dirs", "files") else "all"
        self._kind = kind
        self._cancel = False

    # --------------------------------------------------------
    # Method: cancel
    # --------------------------------------------------------
    def cancel(self):
        self._cancel = True

    # --------------------------------------------------------
    # Method: run
    # Purpose: Explicit scandir stack walk; kind-aware collect.
    # --------------------------------------------------------
    def run(self):
        from file_panel import getFileTypeDescription

        root = self._root
        kind = self._kind
        collect_dirs = kind in ("all", "dirs")
        collect_files = kind in ("all", "files")
        entries = []
        item_count = 0
        last_emit = time.monotonic()

        def maybe_emit(current_dir):
            nonlocal last_emit, item_count
            now = time.monotonic()
            if (
                now - last_emit >= self._PROGRESS_INTERVAL_SEC
                or item_count % self._PROGRESS_EVERY_ITEMS == 0
            ):
                self.progress.emit(item_count, current_dir)
                last_emit = now

        # Stack of (dirpath, rel_dir) to visit.
        stack = [(root, "")]

        try:
            while stack:
                if self._cancel:
                    self.scanCancelled.emit(self._scan_id)
                    return

                dirpath, rel_dir = stack.pop()
                try:
                    with os.scandir(dirpath) as it:
                        child_dirs = []
                        for entry in it:
                            if self._cancel:
                                self.scanCancelled.emit(self._scan_id)
                                return

                            if _skip_hidden_entry(entry, self._show_hidden):
                                continue

                            try:
                                is_dir = entry.is_dir(follow_symlinks=False)
                            except OSError:
                                continue

                            if is_dir:
                                full_path = entry.path
                                display = (
                                    os.path.join(rel_dir, entry.name)
                                    if rel_dir
                                    else entry.name
                                )
                                child_dirs.append((full_path, display))
                                if collect_dirs:
                                    try:
                                        st = entry.stat(follow_symlinks=False)
                                        entries.append({
                                            "name": display,
                                            "size": -1,
                                            "type": getFileTypeDescription(
                                                full_path, True
                                            ),
                                            "mod_time": st.st_mtime,
                                            "is_dir": True,
                                            "full_path": full_path,
                                        })
                                        item_count += 1
                                    except OSError:
                                        pass
                            elif collect_files:
                                full_path = entry.path
                                try:
                                    st = entry.stat(follow_symlinks=False)
                                    if stat.S_ISDIR(st.st_mode):
                                        continue
                                    display = (
                                        os.path.join(rel_dir, entry.name)
                                        if rel_dir
                                        else entry.name
                                    )
                                    entries.append({
                                        "name": display,
                                        "size": st.st_size,
                                        "type": getFileTypeDescription(
                                            full_path, False
                                        ),
                                        "mod_time": st.st_mtime,
                                        "is_dir": False,
                                        "full_path": full_path,
                                    })
                                    item_count += 1
                                except OSError:
                                    continue

                        # Depth-first: push children so last is visited first;
                        # reverse for stable left-to-right order.
                        for full_path, display in reversed(child_dirs):
                            stack.append((full_path, display))

                except (OSError, PermissionError):
                    pass

                maybe_emit(dirpath)

        except (OSError, PermissionError):
            pass

        if self._cancel:
            self.scanCancelled.emit(self._scan_id)
            return

        self.finishedScan.emit(self._scan_id, entries)
