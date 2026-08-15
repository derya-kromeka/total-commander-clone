"""
Side-by-side path comparison dialog (active panel vs other panel).
Shows path, existence, type, modified time, and async folder tree stats.
"""

from __future__ import annotations

import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialogButtonBox,
    QApplication,
    QWidget,
)
from PyQt5.QtCore import Qt

from file_panel import formatFileSize
from folder_stats import FolderSizeWorker
from ui_helpers import (
    buildPathComparisonGrid,
    configureDialog,
    hintLabel,
    addScrollableBody,
)


def _format_dt(ts):
    if ts is None or ts <= 0:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return "—"


def _stat_summary(path):
    """Return dict with exists, is_dir, size, mod_time or None fields."""
    info = {
        "path": path or "",
        "exists": False,
        "is_dir": False,
        "size": -1,
        "mod_time": None,
        "label": "Missing",
    }
    if not path:
        info["label"] = "(no path)"
        return info
    if not os.path.lexists(path):
        return info
    info["exists"] = True
    try:
        st = os.stat(path)
        info["is_dir"] = os.path.isdir(path)
        info["mod_time"] = st.st_mtime
        info["size"] = -1 if info["is_dir"] else st.st_size
        info["label"] = "Folder" if info["is_dir"] else "File"
    except OSError:
        info["label"] = "Unreadable"
    return info


# ------------------------------------------------------------
# Class: ComparePathsDialog
# Purpose: Compare two filesystem paths side by side.
# ------------------------------------------------------------
class ComparePathsDialog(QDialog):
    def __init__(self, left_path, right_path, left_title="Active", right_title="Other", parent=None):
        super().__init__(parent)
        configureDialog(self, "Compare paths", wide=True, min_h=360)
        self.setModal(True)
        self._workers = []

        left = _stat_summary(left_path)
        right = _stat_summary(right_path)

        root = QVBoxLayout(self)
        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(hintLabel(
            "Side-by-side comparison. Folder sizes and counts are calculated in the background."
        ))

        built = buildPathComparisonGrid(
            left_title,
            right_title,
            [
                ("Path", "path"),
                ("Exists", "exists"),
                ("Type", "label"),
                ("Modified", "mod"),
                ("Size", "size"),
                ("Contents", "contents"),
            ],
            self,
        )
        self._left_labels = built["left_labels"]
        self._right_labels = built["right_labels"]
        body_layout.addLayout(built["grid"])

        self._diff_label = QLabel()
        self._diff_label.setWordWrap(True)
        self._diff_label.setObjectName("compareDiffSummary")
        body_layout.addWidget(self._diff_label)
        addScrollableBody(root, body)

        copy_row = QHBoxLayout()
        btn_copy_left = QPushButton("Copy left path")
        btn_copy_right = QPushButton("Copy right path")
        btn_copy_left.setToolTip("Copy the left path to the clipboard.")
        btn_copy_right.setToolTip("Copy the right path to the clipboard.")
        btn_copy_left.clicked.connect(
            lambda: QApplication.clipboard().setText(left.get("path") or "")
        )
        btn_copy_right.clicked.connect(
            lambda: QApplication.clipboard().setText(right.get("path") or "")
        )
        copy_row.addWidget(btn_copy_left)
        copy_row.addWidget(btn_copy_right)
        copy_row.addStretch()
        root.addLayout(copy_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        root.addWidget(buttons)

        self._fill_static(left, right)
        self._start_size_workers(left, right)

    def _header(self, text):
        lbl = QLabel(f"<b>{text}</b>")
        return lbl

    def _fill_static(self, left, right):
        self._left_labels["path"].setText(left["path"] or "—")
        self._right_labels["path"].setText(right["path"] or "—")
        self._left_labels["exists"].setText("Yes" if left["exists"] else "No")
        self._right_labels["exists"].setText("Yes" if right["exists"] else "No")
        self._left_labels["label"].setText(left["label"])
        self._right_labels["label"].setText(right["label"])
        self._left_labels["mod"].setText(_format_dt(left.get("mod_time")))
        self._right_labels["mod"].setText(_format_dt(right.get("mod_time")))

        if left["exists"] and not left["is_dir"]:
            self._left_labels["size"].setText(formatFileSize(left["size"]))
            self._left_labels["contents"].setText("—")
        elif left["exists"] and left["is_dir"]:
            self._left_labels["size"].setText("Calculating…")
            self._left_labels["contents"].setText("Calculating…")
        else:
            self._left_labels["size"].setText("—")
            self._left_labels["contents"].setText("—")

        if right["exists"] and not right["is_dir"]:
            self._right_labels["size"].setText(formatFileSize(right["size"]))
            self._right_labels["contents"].setText("—")
        elif right["exists"] and right["is_dir"]:
            self._right_labels["size"].setText("Calculating…")
            self._right_labels["contents"].setText("Calculating…")
        else:
            self._right_labels["size"].setText("—")
            self._right_labels["contents"].setText("—")

        diffs = []
        if left["exists"] != right["exists"]:
            diffs.append("One side is missing.")
        elif left["exists"] and right["exists"]:
            if left["is_dir"] != right["is_dir"]:
                diffs.append("Types differ (file vs folder).")
            if not left["is_dir"] and not right["is_dir"] and left["size"] != right["size"]:
                diffs.append(
                    f"File sizes differ: {formatFileSize(left['size'])} vs "
                    f"{formatFileSize(right['size'])}."
                )
            if left.get("mod_time") and right.get("mod_time"):
                if abs(left["mod_time"] - right["mod_time"]) >= 1.0:
                    diffs.append("Modified times differ.")
        self._pending_folder_compare = left["exists"] and right["exists"] and (
            left["is_dir"] or right["is_dir"]
        )
        self._left_stats = None
        self._right_stats = None
        if diffs:
            self._diff_label.setText("Differences: " + " ".join(diffs))
        elif not self._pending_folder_compare:
            self._diff_label.setText("No obvious differences in the fields above.")
        else:
            self._diff_label.setText("Comparing folder trees…")

    def _start_size_workers(self, left, right):
        if left["exists"] and left["is_dir"]:
            w = FolderSizeWorker(left["path"], self)
            w.finishedOk.connect(
                lambda b, f, d: self._on_stats("left", b, f, d)
            )
            w.failed.connect(lambda msg: self._on_stats_fail("left", msg))
            self._workers.append(w)
            w.start()
        if right["exists"] and right["is_dir"]:
            w = FolderSizeWorker(right["path"], self)
            w.finishedOk.connect(
                lambda b, f, d: self._on_stats("right", b, f, d)
            )
            w.failed.connect(lambda msg: self._on_stats_fail("right", msg))
            self._workers.append(w)
            w.start()

    def _on_stats(self, side, total_bytes, file_count, dir_count):
        labels = self._left_labels if side == "left" else self._right_labels
        labels["size"].setText(
            f"{formatFileSize(total_bytes)}  ({total_bytes:,} bytes)"
        )
        labels["contents"].setText(
            f"{file_count:,} file(s), {dir_count:,} subfolder(s)"
        )
        stats = (total_bytes, file_count, dir_count)
        if side == "left":
            self._left_stats = stats
        else:
            self._right_stats = stats
        self._update_folder_diff()

    def _on_stats_fail(self, side, msg):
        labels = self._left_labels if side == "left" else self._right_labels
        labels["size"].setText("—")
        labels["contents"].setText(msg or "Failed")
        if side == "left":
            self._left_stats = False
        else:
            self._right_stats = False
        self._update_folder_diff()

    def _update_folder_diff(self):
        if not self._pending_folder_compare:
            return
        if self._left_stats is None or self._right_stats is None:
            return
        if self._left_stats is False or self._right_stats is False:
            self._diff_label.setText("Could not compare folder tree sizes on one or both sides.")
            return
        lb, lf, ld = self._left_stats
        rb, rf, rd = self._right_stats
        parts = []
        if lb != rb:
            parts.append(
                f"Total size differs: {formatFileSize(lb)} vs {formatFileSize(rb)}."
            )
        if lf != rf:
            parts.append(f"File count differs: {lf:,} vs {rf:,}.")
        if ld != rd:
            parts.append(f"Subfolder count differs: {ld:,} vs {rd:,}.")
        if parts:
            self._diff_label.setText("Differences: " + " ".join(parts))
        else:
            self._diff_label.setText(
                "Folder trees match in total size, file count, and subfolder count."
            )

    def closeEvent(self, event):
        for w in self._workers:
            try:
                w.cancel()
                w.wait(2000)
            except Exception:
                pass
        super().closeEvent(event)
