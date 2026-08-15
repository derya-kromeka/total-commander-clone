"""
Background recursive directory scan for FileSystemModel (Subfolders mode).
Runs on a QThread; supports cooperative cancel between directory iterations.

Walks via filesystem_scanner.os.scandir so Windows DirEntry.stat()/is_dir()
come from FindNextFile data (no extra syscall per entry). When kind is
"dirs" or "files", only matching entries are collected — still recursing.
"""

from PyQt5.QtCore import QThread, pyqtSignal

from filesystem_scanner import walkFilesystem


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

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, scan_id, root, show_hidden, kind="all", parent=None):
        super().__init__(parent)
        self._scan_id = scan_id
        self._root = root
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
    # Purpose: Shared scandir walk; kind-aware collect.
    # --------------------------------------------------------
    def run(self):
        from file_panel import getFileTypeDescription

        collect_dirs = self._kind in ("all", "dirs")
        collect_files = self._kind in ("all", "files")
        entries = []

        def on_progress(count, current_dir):
            self.progress.emit(count, current_dir)

        for item in walkFilesystem(
            self._root,
            show_hidden=self._show_hidden,
            collect_dirs=collect_dirs,
            collect_files=collect_files,
            include_root=False,
            cancel_check=lambda: self._cancel,
            progress_cb=on_progress,
        ):
            if self._cancel:
                self.scanCancelled.emit(self._scan_id)
                return
            full_path = item["full_path"]
            is_dir = item["is_dir"]
            entries.append({
                "name": item["display_path"],
                "size": item["size"],
                "type": getFileTypeDescription(full_path, is_dir),
                "mod_time": item["mtime"],
                "is_dir": is_dir,
                "full_path": full_path,
            })

        if self._cancel:
            self.scanCancelled.emit(self._scan_id)
            return
        self.finishedScan.emit(self._scan_id, entries)
