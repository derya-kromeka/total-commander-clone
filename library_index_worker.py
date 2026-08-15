"""
Background QThread queue for library root indexing.
"""

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from library_indexer import indexRoot


# ------------------------------------------------------------
# Class: LibraryIndexWorker
# Purpose: Index a single root off the GUI thread.
# ------------------------------------------------------------
class LibraryIndexWorker(QThread):

    progress = pyqtSignal(str, int, str)
    finishedRoot = pyqtSignal(str, dict)
    failedRoot = pyqtSignal(str, str)

    def __init__(self, db_path, root_id, mode="incremental", parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._root_id = root_id
        self._mode = mode if mode in ("incremental", "rebuild") else "incremental"
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        def on_progress(count, current_dir):
            self.progress.emit(self._root_id, count, current_dir or "")

        try:
            summary = indexRoot(
                self._db_path,
                self._root_id,
                mode=self._mode,
                cancel_check=lambda: self._cancel,
                progress_cb=on_progress,
            )
        except Exception as exc:
            self.failedRoot.emit(self._root_id, str(exc))
            return

        if summary.get("cancelled"):
            self.failedRoot.emit(self._root_id, "Indexing cancelled.")
            return
        if not summary.get("ok"):
            self.failedRoot.emit(self._root_id, summary.get("error") or "Indexing failed.")
            return
        self.finishedRoot.emit(self._root_id, summary)


# ------------------------------------------------------------
# Class: LibraryIndexQueue
# Purpose: Index one root at a time so disks are not thrashed.
# ------------------------------------------------------------
class LibraryIndexQueue(QObject):

    progress = pyqtSignal(str, int, str)
    rootFinished = pyqtSignal(str, dict)
    rootFailed = pyqtSignal(str, str)
    queueIdle = pyqtSignal()

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._pending = []
        self._worker = None
        self._current = None

    def enqueue(self, root_id, mode="incremental"):
        if not root_id:
            return
        for pending_id, pending_mode in self._pending:
            if pending_id == root_id:
                return
        if self._current and self._current[0] == root_id:
            return
        self._pending.append((root_id, mode))
        self._startNext()

    def isBusy(self):
        return self._worker is not None or bool(self._pending)

    def currentRootId(self):
        return self._current[0] if self._current else ""

    def cancelAll(self):
        self._pending = []
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(8000)

    def _startNext(self):
        if self._worker is not None:
            return
        if not self._pending:
            self.queueIdle.emit()
            return
        root_id, mode = self._pending.pop(0)
        self._current = (root_id, mode)
        worker = LibraryIndexWorker(self._db_path, root_id, mode, self)
        worker.progress.connect(self.progress.emit)
        worker.finishedRoot.connect(self._onFinished)
        worker.failedRoot.connect(self._onFailed)
        self._worker = worker
        worker.start()

    def _onFinished(self, root_id, summary):
        self._cleanupWorker()
        self.rootFinished.emit(root_id, summary)
        self._startNext()

    def _onFailed(self, root_id, message):
        self._cleanupWorker()
        self.rootFailed.emit(root_id, message)
        self._startNext()

    def _cleanupWorker(self):
        worker = self._worker
        self._worker = None
        self._current = None
        if worker is None:
            return
        try:
            worker.progress.disconnect(self.progress.emit)
        except TypeError:
            pass
        try:
            worker.finishedRoot.disconnect(self._onFinished)
        except TypeError:
            pass
        try:
            worker.failedRoot.disconnect(self._onFailed)
        except TypeError:
            pass
        worker.wait(1000)
        worker.deleteLater()
