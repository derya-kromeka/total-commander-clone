"""
Total Commander Clone - File Panel Widget
A single file-browser pane with address bar, navigation buttons,
file table, sorting, filtering, in-place rename, and drag-and-drop.
"""

import fnmatch
import html
import os
import platform
import re
import stat
import string
import subprocess
import time
from datetime import datetime

from filter_spec import FilterSpec


# Pattern for splitting names into text vs digit runs (natural sort).
_NATURAL_SORT_SPLIT = re.compile(r"(\d+)")

# ------------------------------------------------------------
# Helper: natural_sort_key
# Purpose: Sort key so embedded numbers compare numerically
#          (e.g. KT-167 before KT-1665, file2 before file10).
#          Each segment is (0, int) or (1, str) so list compare
#          never mixes bare int with str (e.g. "33112_x" vs "a_1").
# ------------------------------------------------------------
def path_under_root(root, rel):
    """Build an absolute path under root from a relative display path (may contain subdirs)."""
    if not rel:
        return root
    rel = rel.replace("/", os.sep).strip()
    parts = [p for p in rel.split(os.sep) if p and p != "."]
    if not parts:
        return root
    return os.path.normpath(os.path.join(root, *parts))


def natural_sort_key(name):
    parts = []
    for part in _NATURAL_SORT_SPLIT.split(name):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.lower()))
    return parts


# ------------------------------------------------------------
# Helper: list Windows drive letters (e.g. ["C:\\", "D:\\"])
# ------------------------------------------------------------
def getWindowsDrives():
    if os.name != "nt":
        return []
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QLineEdit,
    QPushButton, QAbstractItemView, QHeaderView, QFrame, QLabel,
    QStyledItemDelegate, QStyle, QApplication, QComboBox,
    QFileIconProvider, QInputDialog, QMessageBox,
    QMenu, QAction, QActionGroup, QToolButton, QCheckBox,
)
from PyQt5.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QVariant, QMimeData,
    QUrl, pyqtSignal, QSortFilterProxyModel, QPoint, QTimer, QEvent,
    QItemSelectionModel, QSize, QItemSelection, QItemSelectionRange,
    QFileInfo, QMimeDatabase,
)
from PyQt5.QtGui import (
    QDrag, QDesktopServices, QIcon, QPixmap, QPainter, QColor, QKeySequence,
    QFontMetrics,
)


# ------------------------------------------------------------
# Helper: human-readable file size
# ------------------------------------------------------------
def formatFileSize(size_bytes):
    if size_bytes < 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            if unit == "B":
                return f"{size_bytes} B"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# ------------------------------------------------------------
# Helper: normalize path from user input (handles quotes, file:// URLs)
# ------------------------------------------------------------
def normalizePathInput(text):
    """Convert user input (paste/type) to a valid local path for navigation."""
    if not text or not isinstance(text, str):
        return ""
    path = text.strip().strip('"\'')
    if path.lower().startswith("file:///"):
        path = path[8:].replace("/", os.sep)
    elif path.lower().startswith("file://"):
        path = path[7:].replace("/", os.sep)
    return os.path.normpath(path) if path else ""


# ------------------------------------------------------------
# Helper: file type description from extension
# ------------------------------------------------------------
def getFileTypeDescription(file_path, is_dir):
    if is_dir:
        return "Folder"
    _, ext = os.path.splitext(file_path)
    if ext:
        return f"{ext[1:].upper()} File"
    return "File"


# ------------------------------------------------------------
# Helper: Windows associated application friendly name (optional)
# ------------------------------------------------------------
def _windows_associated_app_name(path):
    if os.name != "nt" or not path or not os.path.isfile(path):
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        ASSOCF_INIT_DEFAULTTOSTAR = 0x00000004
        ASSOCSTR_FRIENDLYAPPNAME = 8
        shell32 = ctypes.windll.shell32
        buf = ctypes.create_unicode_buffer(1024)
        pcch = wintypes.DWORD(len(buf))
        p = os.path.normpath(path)
        hr = shell32.AssocQueryStringW(
            ASSOCF_INIT_DEFAULTTOSTAR,
            ASSOCSTR_FRIENDLYAPPNAME,
            p,
            None,
            buf,
            ctypes.byref(pcch),
        )
        if hr == 0 and buf.value:
            return buf.value.strip()
    except Exception:
        pass
    return ""


# ------------------------------------------------------------
# Helper: byte size of files directly in a folder (non-recursive)
# ------------------------------------------------------------
def _folder_immediate_files_size_bytes(path):
    """
    Sum st_size for entries that are regular files in `path` only.
    Does not descend into subfolders (keeps tooltips fast). Symlinks are not followed.
    Returns None if the path is unusable or listing fails.
    """
    if not path or not os.path.isdir(path):
        return None
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        return None
    return total


# ------------------------------------------------------------
# Helper: Rich HTML tooltip for file list rows (summary card)
# ------------------------------------------------------------
def build_entry_tooltip_html(entry):
    name = entry["name"]
    full = entry["full_path"]
    is_dir = entry["is_dir"]
    dt = datetime.fromtimestamp(entry["mod_time"])
    date_s = dt.strftime("%Y-%m-%d %H:%M:%S")

    esc_name = html.escape(name)
    esc_full = html.escape(full)

    rows_html = []
    rows_html.append(
        f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Location</td>"
        f"<td style='padding:2px 0;'>{esc_full}</td></tr>"
    )
    rows_html.append(
        f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Modified</td>"
        f"<td style='padding:2px 0;'>{html.escape(date_s)}</td></tr>"
    )
    rows_html.append(
        f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Listed type</td>"
        f"<td style='padding:2px 0;'>{html.escape(entry['type'])}</td></tr>"
    )

    title = "Folder" if is_dir else "File"
    icon = "&#128193;" if is_dir else "&#128196;"

    if is_dir:
        qb = _folder_immediate_files_size_bytes(full)
        if qb is not None:
            sz = formatFileSize(qb)
            rows_html.insert(
                1,
                f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Size</td>"
                f"<td style='padding:2px 0;'>{html.escape(sz)} "
                f"<span style='color:#888;font-size:11px;'>(files here only)</span></td></tr>",
            )
        foot = ["Double-click to open this folder in the panel."]
        if qb is not None:
            foot.append("Size includes only files in this folder, not subfolders.")
        body_extra = (
            "<p style='margin:8px 0 0 0;color:#888;font-size:11px;'>"
            + "<br/>".join(foot)
            + "</p>"
        )
    else:
        sz = formatFileSize(entry["size"])
        rows_html.insert(
            1,
            f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Size</td>"
            f"<td style='padding:2px 0;'>{html.escape(sz)}</td></tr>",
        )
        db = QMimeDatabase()
        mt = db.mimeTypeForFile(full)
        raw_name = mt.name()
        raw_comment = mt.comment() or ""
        rows_html.append(
            f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>MIME</td>"
            f"<td style='padding:2px 0;'>{html.escape(raw_name)}</td></tr>"
        )
        if raw_comment and raw_comment != raw_name:
            rows_html.append(
                f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Kind</td>"
                f"<td style='padding:2px 0;'>{html.escape(raw_comment)}</td></tr>"
            )
        opens = _windows_associated_app_name(full)
        if opens:
            rows_html.append(
                f"<tr><td style='color:#aaa;padding:2px 10px 2px 0;'>Opens with</td>"
                f"<td style='padding:2px 0;'>{html.escape(opens)}</td></tr>"
            )
        body_extra = (
            "<p style='margin:8px 0 0 0;color:#888;font-size:11px;'>"
            "Double-click to open with the default application.</p>"
        )

    table = (
        "<table cellspacing='0' cellpadding='0' style='border-collapse:collapse;'>"
        + "".join(rows_html)
        + "</table>"
    )

    return (
        "<html><head/><body style='color:#dce0ee;'>"
        f"<div style='min-width:280px;max-width:480px;'>"
        f"<div style='font-size:13px;font-weight:600;margin-bottom:6px;'>"
        f"{icon} {esc_name} <span style='color:#888;font-weight:normal;'>"
        f"({title})</span></div>"
        f"<div style='height:1px;background:#555;margin:4px 0 8px 0;'></div>"
        f"{table}"
        f"{body_extra}"
        "</div></body></html>"
    )


# ============================================================
# Class: DriveLineEdit
# Purpose: Embedded editor for the drive QComboBox; clicking the
#          letter/field opens the dropdown (default Qt only opens
#          from the combo's arrow sub-control).
# ============================================================
class DriveLineEdit(QLineEdit):

    def __init__(self, combo, parent=None):
        super().__init__(parent)
        self._drive_combo = combo

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.LeftButton
            and self._drive_combo is not None
            and self._drive_combo.isVisible()
        ):
            self._drive_combo.showPopup()
        super().mousePressEvent(event)


# ============================================================
# Class: DrivePickerCombo
# Purpose: Drive QComboBox that opens the list on any left-click on
#          the widget (e.g. drop-down button area inside the control).
#          Optional on_before_popup runs when the list is about to open
#          (e.g. re-scan drive letters on Windows).
# ============================================================
class DrivePickerCombo(QComboBox):

    def __init__(self, parent=None, on_before_popup=None):
        super().__init__(parent)
        self._on_before_popup = on_before_popup

    def showPopup(self):
        if self._on_before_popup is not None:
            self._on_before_popup()
        super().showPopup()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isVisible():
            self.showPopup()
        super().mousePressEvent(event)


# ============================================================
# Class: FileSystemModel
# Purpose: Custom QAbstractTableModel that reads a directory
#          and presents its contents as table rows with columns
#          for Name, Size, Type, and Date Modified.
# ============================================================
class FileSystemModel(QAbstractTableModel):

    COLUMNS = ["Name", "Size", "Type", "Date Modified"]
    COLUMN_TOOLTIPS = [
        "Name — File or folder as listed (includes subpaths when Subfolders search is on).",
        "Size — File size on disk; folders show &lt;DIR&gt;.",
        "Type — Extension or category (e.g. PY File, Folder).",
        "Date Modified — Last time the item was modified.",
    ]

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = ""
        self._entries = []
        self._show_hidden = False
        self._recursive = False
        self._icon_provider = QFileIconProvider()

    # --------------------------------------------------------
    # Method: setRecursive
    # Purpose: When True, list all files/folders under current path (tree walk).
    # --------------------------------------------------------
    def setRecursive(self, recursive):
        recursive = bool(recursive)
        if self._recursive == recursive:
            return
        self._recursive = recursive
        if self._current_path:
            self.loadDirectory(self._current_path)

    def isRecursive(self):
        return self._recursive

    # --------------------------------------------------------
    # Method: setShowHidden
    # Purpose: Toggles visibility of hidden files/dotfiles.
    # --------------------------------------------------------
    def setShowHidden(self, show):
        self._show_hidden = show
        if self._current_path:
            self.loadDirectory(self._current_path)

    def _skip_hidden_stat(self, full_path, name):
        if self._show_hidden:
            return False
        if name.startswith("."):
            return True
        if os.name == "nt":
            try:
                st = os.stat(full_path)
                attrs = getattr(st, "st_file_attributes", 0)
                if attrs & stat.FILE_ATTRIBUTE_HIDDEN:
                    return True
            except OSError:
                return True
        return False

    def _append_entry(self, full_path, display_name, is_dir, size, mod_time):
        file_type = getFileTypeDescription(full_path, is_dir)
        self._entries.append({
            "name": display_name,
            "size": size,
            "type": file_type,
            "mod_time": mod_time,
            "is_dir": is_dir,
            "full_path": full_path,
        })

    # --------------------------------------------------------
    # Method: loadDirectory
    # Purpose: Scans the given directory and populates the model.
    # Input: path (str) - The directory to load.
    # --------------------------------------------------------
    def loadDirectory(self, path):
        self.beginResetModel()
        self._current_path = path
        self._entries = []

        if self._recursive:
            self._loadDirectoryRecursive(path)
        else:
            self._loadDirectoryFlat(path)

        self._entries.sort(key=lambda e: (not e["is_dir"], natural_sort_key(e["name"])))
        self.endResetModel()

    def _loadDirectoryFlat(self, path):
        try:
            items = os.listdir(path)
        except (PermissionError, OSError):
            return

        for name in items:
            if self._skip_hidden_stat(os.path.join(path, name), name):
                continue

            full_path = os.path.join(path, name)
            try:
                st = os.stat(full_path)
                is_dir = stat.S_ISDIR(st.st_mode)
                size = st.st_size if not is_dir else -1
                mod_time = st.st_mtime
                self._append_entry(full_path, name, is_dir, size, mod_time)
            except (PermissionError, OSError):
                continue

    def _loadDirectoryRecursive(self, root):
        root = os.path.normpath(root)
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                if not self._show_hidden:
                    dirnames[:] = [
                        d for d in dirnames
                        if not self._skip_hidden_stat(os.path.join(dirpath, d), d)
                    ]

                rel_dir = os.path.relpath(dirpath, root)
                if rel_dir == os.curdir:
                    rel_dir = ""

                for d in dirnames:
                    full_path = os.path.join(dirpath, d)
                    if self._skip_hidden_stat(full_path, d):
                        continue
                    try:
                        st = os.stat(full_path)
                        if not stat.S_ISDIR(st.st_mode):
                            continue
                        display = os.path.join(rel_dir, d) if rel_dir else d
                        self._append_entry(full_path, display, True, -1, st.st_mtime)
                    except (PermissionError, OSError):
                        continue

                for f in filenames:
                    if self._skip_hidden_stat(os.path.join(dirpath, f), f):
                        continue
                    full_path = os.path.join(dirpath, f)
                    try:
                        st = os.stat(full_path)
                        if stat.S_ISDIR(st.st_mode):
                            continue
                        display = os.path.join(rel_dir, f) if rel_dir else f
                        self._append_entry(
                            full_path, display, False, st.st_size, st.st_mtime
                        )
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            return

    # --------------------------------------------------------
    # Method: currentPath
    # --------------------------------------------------------
    def currentPath(self):
        return self._current_path

    # --------------------------------------------------------
    # Method: entryAt
    # Purpose: Returns the entry dict for a given row index.
    # --------------------------------------------------------
    def entryAt(self, row):
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    # --------------------------------------------------------
    # Method: getEntryByName
    # Purpose: Finds an entry by file name and returns its row.
    # --------------------------------------------------------
    def getEntryByName(self, name):
        for i, entry in enumerate(self._entries):
            if entry["name"] == name:
                return i
        return -1

    # --------------------------------------------------------
    # Method: renameEntry
    # Purpose: Updates the name of an entry after a rename.
    # --------------------------------------------------------
    def renameEntry(self, row, new_name):
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            new_path = path_under_root(self._current_path, new_name)
            entry["name"] = new_name
            entry["full_path"] = new_path
            entry["type"] = getFileTypeDescription(new_path, entry["is_dir"])
            idx_start = self.index(row, 0)
            idx_end = self.index(row, len(self.COLUMNS) - 1)
            self.dataChanged.emit(idx_start, idx_end)

    # --------------------------------------------------------
    # Qt Model Interface
    # --------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        entry = self._entries[index.row()]
        col = index.column()

        if role == Qt.ToolTipRole:
            return build_entry_tooltip_html(entry)

        if role == Qt.DisplayRole:
            if col == 0:
                return entry["name"]
            elif col == 1:
                if entry["is_dir"]:
                    return "<DIR>"
                return formatFileSize(entry["size"])
            elif col == 2:
                return entry["type"]
            elif col == 3:
                dt = datetime.fromtimestamp(entry["mod_time"])
                return dt.strftime("%Y-%m-%d %H:%M")

        if role == Qt.DecorationRole and col == 0:
            file_info = QFileInfo(entry["full_path"])
            return self._icon_provider.icon(file_info)

        if role == Qt.UserRole:
            return entry

        if role == Qt.TextAlignmentRole:
            if col == 1:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ToolTipRole:
                if 0 <= section < len(self.COLUMN_TOOLTIPS):
                    return self.COLUMN_TOOLTIPS[section]
        return QVariant()

    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return default_flags | Qt.ItemIsDropEnabled

    # --------------------------------------------------------
    # Drag and Drop MIME support
    # --------------------------------------------------------
    def mimeTypes(self):
        return ["text/uri-list"]

    def mimeData(self, indexes):
        mime_data = QMimeData()
        urls = []
        seen_rows = set()
        for index in indexes:
            if index.row() not in seen_rows:
                seen_rows.add(index.row())
                entry = self._entries[index.row()]
                urls.append(QUrl.fromLocalFile(entry["full_path"]))
        mime_data.setUrls(urls)
        return mime_data

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction


# ============================================================
# Class: FileSortFilterProxy
# Purpose: QSortFilterProxyModel that allows real-time text
#          filtering by file name and custom sort behavior
#          (folders always on top).
# ============================================================
class FileSortFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self._filter_mode = "contains"
        self._entry_kind = "all"
        self._regex_obj = None
        self._regex_invalid = False
        self._filter_spec = FilterSpec()
        self.setDynamicSortFilter(True)

    # --------------------------------------------------------
    # Method: setFilterText
    # --------------------------------------------------------
    def setFilterText(self, text):
        self._filter_text = text
        self._regex_obj = None
        self._regex_invalid = False
        if self._filter_mode == "regex" and text.strip():
            try:
                self._regex_obj = re.compile(text, re.IGNORECASE | re.UNICODE)
            except re.error:
                self._regex_invalid = True
        self.invalidateFilter()

    # --------------------------------------------------------
    # Method: setFilterMode
    # Purpose: "contains" | "wildcard" | "regex" — how name is matched.
    # --------------------------------------------------------
    def setFilterMode(self, mode):
        if mode not in ("contains", "wildcard", "regex"):
            return
        self._filter_mode = mode
        self.setFilterText(self._filter_text)

    def filterMode(self):
        return self._filter_mode

    # --------------------------------------------------------
    # Method: setEntryKindFilter
    # Purpose: "all" | "dirs" | "files" — limit rows before name match.
    # --------------------------------------------------------
    def setEntryKindFilter(self, kind):
        if kind not in ("all", "dirs", "files"):
            return
        self._entry_kind = kind
        self.invalidateFilter()

    def entryKindFilter(self):
        return self._entry_kind

    # --------------------------------------------------------
    # Method: setFilterSpec / filterSpec
    # Purpose: Optional size/date rules (FilterSpec); AND with name + kind.
    # --------------------------------------------------------
    def setFilterSpec(self, spec):
        self._filter_spec = spec if spec is not None else FilterSpec()
        self.invalidateFilter()

    def filterSpec(self):
        return self._filter_spec

    # --------------------------------------------------------
    # Method: filterAcceptsRow
    # --------------------------------------------------------
    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        entry = model.entryAt(source_row)
        if entry is None:
            return False

        if self._entry_kind == "dirs" and not entry["is_dir"]:
            return False
        if self._entry_kind == "files" and entry["is_dir"]:
            return False

        if (self._filter_text or "").strip():
            name = entry["name"]
            ok = False
            if self._filter_mode == "contains":
                ok = self._filter_text.lower() in name.lower()
            elif self._filter_mode == "wildcard":
                pat = self._filter_text.strip()
                ok = fnmatch.fnmatch(name.lower(), pat.lower())
            elif self._filter_mode == "regex":
                if self._regex_invalid or self._regex_obj is None:
                    ok = False
                else:
                    ok = self._regex_obj.search(name) is not None
            if not ok:
                return False

        if self._filter_spec is not None and not self._filter_spec.is_empty():
            if not self._filter_spec.matches(entry):
                return False
        return True

    # --------------------------------------------------------
    # Method: lessThan
    # Purpose: Custom sort keeping folders before files.
    # --------------------------------------------------------
    def lessThan(self, left, right):
        model = self.sourceModel()
        left_entry = model.entryAt(left.row())
        right_entry = model.entryAt(right.row())

        if left_entry is None or right_entry is None:
            return False

        if left_entry["is_dir"] != right_entry["is_dir"]:
            return left_entry["is_dir"]

        col = left.column()
        if col == 0:
            return natural_sort_key(left_entry["name"]) < natural_sort_key(right_entry["name"])
        elif col == 1:
            return left_entry["size"] < right_entry["size"]
        elif col == 2:
            return left_entry["type"].lower() < right_entry["type"].lower()
        elif col == 3:
            return left_entry["mod_time"] < right_entry["mod_time"]
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        src = self.sourceModel()
        if (
            src is not None
            and orientation == Qt.Horizontal
            and role == Qt.ToolTipRole
        ):
            return src.headerData(section, orientation, role)
        return super().headerData(section, orientation, role)


# ============================================================
# Class: FileTableView
# Purpose: QTableView subclass with drag-and-drop initiation,
#          drop target visual feedback, and slow-click-to-rename
#          (clicking an already-selected file starts rename
#          after a short delay, like Windows Explorer).
# ============================================================
class FileTableView(QTableView):

    filesDropped = pyqtSignal(list, str, bool)
    slowClickRenameRequested = pyqtSignal()
    emptyAreaPressed = pyqtSignal()
    panelPressed = pyqtSignal()

    RENAME_CLICK_DELAY_MS = 600

    # --------------------------------------------------------
    # Pixels from top/bottom of viewport that trigger auto-scroll when dragging selection.
    EDGE_SCROLL_ZONE = 24
    SCROLL_STEP_PX = 12
    SCROLL_TIMER_MS = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._selection_anchor_row = -1
        self._press_was_on_selected_row = False  # True only when file-drag is intended
        self._scroll_direction = 0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(self.SCROLL_TIMER_MS)
        self._scroll_timer.timeout.connect(self._onScrollTimeout)

        self._slow_click_row = -1
        self._rename_timer = QTimer(self)
        self._rename_timer.setSingleShot(True)
        self._rename_timer.timeout.connect(self._onRenameTimerFired)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(False)
        header.setHighlightSections(False)

    # --------------------------------------------------------
    # Slow-click-to-rename logic:
    # First click selects the row. A second single-click on the
    # same already-selected row (not a double-click) starts a
    # short timer. If the timer fires, rename begins.
    # Double-clicking cancels the timer so it navigates instead.
    # --------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            clicked_index = self.indexAt(event.pos())
            if clicked_index.isValid():
                self._selection_anchor_row = clicked_index.row()
                selected_rows = self.selectionModel().selectedRows()
                self._press_was_on_selected_row = any(
                    sr.row() == clicked_index.row() for sr in selected_rows
                )
            else:
                self._selection_anchor_row = -1
                self._press_was_on_selected_row = False

            selected_rows = self.selectionModel().selectedRows()
            is_single_selected = (
                len(selected_rows) == 1
                and clicked_index.isValid()
                and selected_rows[0].row() == clicked_index.row()
            )

            if is_single_selected and not self._rename_timer.isActive():
                self._slow_click_row = clicked_index.row()
                self._rename_timer.start(self.RENAME_CLICK_DELAY_MS)
            else:
                self._rename_timer.stop()
                self._slow_click_row = -1

        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.panelPressed.emit()
            if not self.indexAt(event.pos()).isValid():
                self.emptyAreaPressed.emit()

    def mouseDoubleClickEvent(self, event):
        self._rename_timer.stop()
        self._slow_click_row = -1
        super().mouseDoubleClickEvent(event)

    def _onRenameTimerFired(self):
        selected_rows = self.selectionModel().selectedRows()
        if (
            len(selected_rows) == 1
            and selected_rows[0].row() == self._slow_click_row
        ):
            self.slowClickRenameRequested.emit()
        self._slow_click_row = -1

    # --------------------------------------------------------
    # Cancel any pending rename timer (called externally when
    # the panel loses active state or navigation occurs).
    # --------------------------------------------------------
    def cancelPendingRename(self):
        self._rename_timer.stop()
        self._slow_click_row = -1

    # --------------------------------------------------------
    # Edge auto-scroll during drag-to-select
    # --------------------------------------------------------
    def _updateEdgeScroll(self, active, direction):
        if active and direction != 0:
            self._scroll_direction = direction
            if not self._scroll_timer.isActive():
                self._scroll_timer.start()
        else:
            self._scroll_direction = 0
            self._scroll_timer.stop()

    def _onScrollTimeout(self):
        if self._scroll_direction == 0:
            self._scroll_timer.stop()
            return
        sb = self.verticalScrollBar()
        sb.setValue(sb.value() + self._scroll_direction * self.SCROLL_STEP_PX)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._selection_anchor_row = -1
            self._updateEdgeScroll(False, 0)
        super().mouseReleaseEvent(event)

    # --------------------------------------------------------
    # Drag initiation
    # --------------------------------------------------------
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            self._updateEdgeScroll(False, 0)
            super().mouseMoveEvent(event)
            return

        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        # Drag-to-select: when user did not press on an already-selected row, always
        # extend selection by drag. Only start file-drag when they pressed on a selected row.
        doing_select_drag = not self._press_was_on_selected_row

        if doing_select_drag or distance < QApplication.startDragDistance():
            # Extend selection from anchor to current row (and optionally auto-scroll)
            if self._selection_anchor_row >= 0:
                current_index = self.indexAt(event.pos())
                if current_index.isValid():
                    model = self.model()
                    r1 = min(self._selection_anchor_row, current_index.row())
                    r2 = max(self._selection_anchor_row, current_index.row())
                    col_count = model.columnCount()
                    if col_count > 0:
                        top_left = model.index(r1, 0)
                        bottom_right = model.index(r2, col_count - 1)
                        sel = QItemSelection(top_left, bottom_right)
                        self.selectionModel().select(
                            sel,
                            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                        )
                y = event.pos().y()
                vh = self.viewport().height()
                if y < self.EDGE_SCROLL_ZONE:
                    self._updateEdgeScroll(True, -1)
                elif y > vh - self.EDGE_SCROLL_ZONE:
                    self._updateEdgeScroll(True, 1)
                else:
                    self._updateEdgeScroll(False, 0)
            if doing_select_drag:
                event.accept()
                return
            super().mouseMoveEvent(event)
            return

        # File-drag: user pressed on a selected row and moved past threshold
        self._selection_anchor_row = -1
        self._updateEdgeScroll(False, 0)
        self._rename_timer.stop()
        self._slow_click_row = -1

        selected_indexes = self.selectionModel().selectedRows()
        if not selected_indexes:
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime_data = self.model().mimeData(selected_indexes)
        drag.setMimeData(mime_data)

        drag.exec_(Qt.CopyAction | Qt.MoveAction, Qt.MoveAction)

    # --------------------------------------------------------
    # Drop handling
    # --------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    # --------------------------------------------------------
    # Method: _resolveDropIsCopy
    # Purpose: Normalize copy/move semantics for both internal
    #          panel drags and external Explorer drags.
    # --------------------------------------------------------
    def _resolveDropIsCopy(self, event):
        if event.dropAction() == Qt.CopyAction:
            return True
        if event.dropAction() == Qt.MoveAction:
            return False
        if event.proposedAction() == Qt.CopyAction:
            return True
        if event.proposedAction() == Qt.MoveAction:
            return False

        modifiers = event.keyboardModifiers()
        if modifiers & Qt.ControlModifier:
            return True
        if modifiers & Qt.ShiftModifier:
            return False

        # External drags default to copy, internal panel drags keep move.
        return event.source() is None

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if not file_paths:
            event.ignore()
            return

        is_copy = self._resolveDropIsCopy(event)

        proxy = self.model()
        drop_index = self.indexAt(event.pos())
        drop_target = ""
        if drop_index.isValid():
            source_index = proxy.mapToSource(drop_index)
            entry = proxy.sourceModel().entryAt(source_index.row())
            if entry and entry["is_dir"]:
                drop_target = entry["full_path"]

        if not drop_target:
            drop_target = proxy.sourceModel().currentPath()

        self.panelPressed.emit()
        self.filesDropped.emit(file_paths, drop_target, is_copy)
        event.acceptProposedAction()


# ============================================================
# Class: _RenameLineEdit
# Purpose: Inline editor for file renaming. Emits distinct
#          signals for Enter (commit), Escape (cancel), and
#          focus-lost (cancel), so the caller can handle each
#          case independently.
# ============================================================
class _RenameLineEdit(QLineEdit):

    enterPressed = pyqtSignal()
    escapePressed = pyqtSignal()
    focusLostSignal = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.enterPressed.emit()
            return
        if event.key() == Qt.Key_Escape:
            self.escapePressed.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focusLostSignal.emit()


# ============================================================
# Class: FilePanel
# Purpose: Complete file browser panel widget combining the
#          address bar, navigation buttons, filter input,
#          file table, and status summary.
# ============================================================
class FilePanel(QWidget):

    pathChanged = pyqtSignal(str)
    pathCopied = pyqtSignal(str)
    folderCreated = pyqtSignal(str)
    fileDoubleClicked = pyqtSignal(dict)
    selectionChanged = pyqtSignal()
    filesDropped = pyqtSignal(list, str, bool)
    activated = pyqtSignal()

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, panel_side="left", parent=None, settings_manager=None):
        super().__init__(parent)
        self._panel_side = panel_side
        self._settings_manager = settings_manager
        self._history = []
        self._history_index = -1
        self._is_active = False
        self._rename_edit = None

        self._initUI()
        self._connectSignals()
        self._path_edit.installEventFilter(self)
        self._filter_edit.installEventFilter(self)
        self._installActivationEventFilters()
        self._updateFrameStyle()

    # --------------------------------------------------------
    # Method: _initUI
    # Purpose: Builds and lays out all child widgets.
    # --------------------------------------------------------
    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        NAV_BAR_HEIGHT = 28
        NAV_ICON_SIZE = 18
        style = QApplication.instance().style()

        # --- Path bar (full width: path input + copy + paste) ---
        path_layout = QHBoxLayout()
        path_layout.setSpacing(4)

        self._path_edit = QLineEdit()
        self._path_edit.setObjectName("panelPathEdit")
        self._path_edit.setPlaceholderText("Enter or paste path, press Enter to go...")
        self._path_edit.setMinimumHeight(NAV_BAR_HEIGHT)
        self._path_edit.setToolTip(
            "Address bar\n\n"
            "Shows the folder open in this panel. Type or paste a path and press Enter "
            "to navigate. Use the copy/paste buttons to work with the clipboard."
        )

        self._btn_copy_path = QPushButton()
        self._btn_copy_path.setObjectName("navButton")
        self._btn_copy_path.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_copy_path.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._btn_copy_path.setToolTip(
            "Copy path\n\nCopy the current folder path to the clipboard."
        )
        self._btn_copy_path.setAutoDefault(False)
        self._btn_copy_path.setDefault(False)
        copy_icon = QIcon.fromTheme("edit-copy")
        if copy_icon.isNull():
            copy_icon = QIcon.fromTheme("document-copy")
        if copy_icon.isNull():
            self._btn_copy_path.setText("\U0001F4CB")
        else:
            self._btn_copy_path.setIcon(copy_icon)
        self._btn_copy_path.clicked.connect(self._copyPathToClipboard)

        self._btn_paste_path = QPushButton()
        self._btn_paste_path.setObjectName("navButton")
        self._btn_paste_path.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_paste_path.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._btn_paste_path.setToolTip(
            "Paste path\n\nPaste a path from the clipboard and navigate to that folder if it exists."
        )
        self._btn_paste_path.setAutoDefault(False)
        self._btn_paste_path.setDefault(False)
        paste_icon = QIcon.fromTheme("edit-paste")
        if paste_icon.isNull():
            paste_icon = QIcon.fromTheme("document-paste")
        if paste_icon.isNull():
            self._btn_paste_path.setText("\U0001F4E5")
        else:
            self._btn_paste_path.setIcon(paste_icon)
        self._btn_paste_path.clicked.connect(self._pastePathAndNavigate)

        self._btn_browse_folder = QPushButton()
        self._btn_browse_folder.setObjectName("navButton")
        self._btn_browse_folder.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_browse_folder.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._btn_browse_folder.setToolTip(
            "Open in Explorer\n\nOpen this folder in the operating system's file manager "
            "(Windows Explorer, Finder, etc.)."
        )
        self._btn_browse_folder.setAutoDefault(False)
        self._btn_browse_folder.setDefault(False)
        self._btn_browse_folder.setIcon(style.standardIcon(QStyle.SP_DirOpenIcon))
        self._btn_browse_folder.clicked.connect(self._openCurrentFolderInSystemExplorer)

        path_layout.addWidget(self._path_edit, 1)
        path_layout.addWidget(self._btn_copy_path)
        path_layout.addWidget(self._btn_paste_path)
        path_layout.addWidget(self._btn_browse_folder)
        layout.addLayout(path_layout)

        # --- Models (needed before filter options menu) ---
        self._source_model = FileSystemModel(self)
        self._proxy_model = FileSortFilterProxy(self)
        self._proxy_model.setSourceModel(self._source_model)

        # --- Navigation bar (back, forward, up, home, new folder, drive, filter…) ---
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)

        for btn_attr in ("_btn_back", "_btn_forward", "_btn_up", "_btn_home"):
            btn = QPushButton()
            btn.setObjectName("navButton")
            btn.setFixedSize(30, NAV_BAR_HEIGHT)
            btn.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
            btn.setAutoDefault(False)
            btn.setDefault(False)
            setattr(self, btn_attr, btn)
        self._btn_back.setToolTip(
            "Back\n\nGo to the previous folder in this panel's history. Shortcut: Alt+Left."
        )
        self._btn_back.setIcon(style.standardIcon(QStyle.SP_ArrowBack))
        self._btn_back.setEnabled(False)
        self._btn_forward.setToolTip(
            "Forward\n\nGo to the next folder in this panel's history. Shortcut: Alt+Right."
        )
        self._btn_forward.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        self._btn_forward.setEnabled(False)
        self._btn_up.setToolTip(
            "Up\n\nOpen the parent folder. Shortcut: Backspace."
        )
        self._btn_up.setIcon(style.standardIcon(QStyle.SP_ArrowUp))
        self._btn_home.setToolTip(
            "Home\n\nJump to your user home directory."
        )
        self._btn_home.setText("\U0001F3E0")
        self._btn_home.clicked.connect(self._goHome)

        self._drive_combo = DrivePickerCombo(
            on_before_popup=self._refreshDrives if os.name == "nt" else None,
        )
        self._drive_combo.setObjectName("driveCombo")
        self._drive_combo.setToolTip(
            "Drive\n\nChoose a drive letter to jump to its root. "
            "On Windows the list refreshes when you open the menu."
        )
        self._drive_combo.setFixedSize(58, NAV_BAR_HEIGHT)
        self._drive_combo.setMinimumContentsLength(2)
        self._drive_combo.setEditable(True)
        drive_line_edit = DriveLineEdit(self._drive_combo, self._drive_combo)
        drive_line_edit.setReadOnly(True)
        drive_line_edit.setAlignment(Qt.AlignCenter)
        drive_line_edit.setFrame(False)
        self._drive_combo.setLineEdit(drive_line_edit)
        drives = getWindowsDrives()
        if drives:
            self._drive_combo.addItems(drives)
            self._drive_combo.currentIndexChanged.connect(self._onDriveChanged)
        else:
            self._drive_combo.setVisible(False)

        self._drive_arrow = QLabel("\u25BC")
        self._drive_arrow.setObjectName("driveArrow")
        self._drive_arrow.setFixedSize(14, NAV_BAR_HEIGHT)
        self._drive_arrow.setCursor(Qt.PointingHandCursor)
        self._drive_arrow.mousePressEvent = self._onDriveArrowClicked
        self._drive_arrow.setVisible(bool(drives))
        self._drive_arrow.setToolTip(
            "Open drive list\n\nClick to show the same drive menu as the field beside it."
        )

        self._drive_container = QWidget()
        self._drive_container.setFixedSize(72, NAV_BAR_HEIGHT)
        drive_container_layout = QHBoxLayout(self._drive_container)
        drive_container_layout.setContentsMargins(0, 0, 0, 0)
        drive_container_layout.setSpacing(0)
        drive_container_layout.addWidget(self._drive_combo, 0, Qt.AlignVCenter)
        drive_container_layout.addWidget(self._drive_arrow, 0, Qt.AlignVCenter)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("\U0001F50D Filter...")
        self._filter_edit.setMinimumWidth(120)
        self._filter_edit.setMinimumHeight(NAV_BAR_HEIGHT)
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setToolTip(
            "Filter\n\n"
            "Narrow the file list by name. Use the gear for full options "
            "(match mode, files/folders, size, date, saved presets). "
            "Use Subfolders to search below the current folder."
        )

        self._btn_filter_clear = QPushButton("Clear")
        self._btn_filter_clear.setObjectName("navButton")
        self._btn_filter_clear.setFixedHeight(NAV_BAR_HEIGHT)
        self._btn_filter_clear.setMaximumWidth(72)
        self._btn_filter_clear.setToolTip(
            "Clear filter\n\n"
            "Remove name filter, match mode, size/date rules, and subfolder search."
        )
        self._btn_filter_clear.setAutoDefault(False)
        self._btn_filter_clear.setDefault(False)
        self._btn_filter_clear.clicked.connect(self.clearFilter)

        self._btn_filter_options = QToolButton()
        self._btn_filter_options.setObjectName("navButton")
        self._btn_filter_options.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_filter_options.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._btn_filter_options.setToolTip(
            "Filter options\n\n"
            "Open the filter dialog: match mode, files or folders only, subfolders, "
            "size and modified date (with AND/OR), saved presets."
        )
        self._btn_filter_options.setAutoRaise(True)
        self._btn_filter_options.clicked.connect(self._onOpenFilterOptions)
        filter_opts_icon = QIcon.fromTheme("view-filter")
        if filter_opts_icon.isNull():
            filter_opts_icon = style.standardIcon(QStyle.SP_FileDialogContentsView)
        if filter_opts_icon.isNull():
            self._btn_filter_options.setText("\u2699")
        else:
            self._btn_filter_options.setIcon(filter_opts_icon)

        self._btn_new_folder = QPushButton()
        self._btn_new_folder.setObjectName("navButton")
        self._btn_new_folder.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_new_folder.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._btn_new_folder.setToolTip(
            "New folder\n\n"
            "Create a new subfolder in the folder shown in this panel. "
            "Shortcut: F8 when this panel is active."
        )
        self._btn_new_folder.setAutoDefault(False)
        self._btn_new_folder.setDefault(False)
        new_folder_icon = QIcon.fromTheme("folder-new")
        if new_folder_icon.isNull():
            new_folder_icon = style.standardIcon(QStyle.SP_FileDialogNewFolder)
        if new_folder_icon.isNull():
            self._btn_new_folder.setText("\U0001F4C1+")
        else:
            self._btn_new_folder.setIcon(new_folder_icon)

        nav_layout.addWidget(self._btn_back)
        nav_layout.addWidget(self._btn_forward)
        nav_layout.addWidget(self._btn_up)
        nav_layout.addWidget(self._btn_home)
        nav_layout.addWidget(self._btn_new_folder)
        nav_layout.addWidget(self._drive_container)
        nav_layout.addWidget(self._filter_edit, 1)
        self._chk_filter_subfolders = QCheckBox("Subfolders")
        self._chk_filter_subfolders.setObjectName("filterSubfoldersCheck")
        self._chk_filter_subfolders.setToolTip(
            "Search subfolders\n\n"
            "When checked, the list includes items in all subdirectories under the current "
            "path. This can be slow in very large folder trees."
        )
        self._chk_filter_subfolders.stateChanged.connect(self._onSubfoldersFilterToggled)
        nav_layout.addWidget(self._chk_filter_subfolders, 0, Qt.AlignVCenter)
        nav_layout.addWidget(self._btn_filter_clear, 0, Qt.AlignVCenter)
        nav_layout.addWidget(self._btn_filter_options)

        layout.addLayout(nav_layout)

        # --- File table ---
        self._table = FileTableView(self)
        self._table.setObjectName("panelFileTable")
        self._table.setModel(self._proxy_model)
        self._table.sortByColumn(0, Qt.AscendingOrder)
        hdr = self._table.horizontalHeader()
        hdr.setContextMenuPolicy(Qt.CustomContextMenu)
        hdr.customContextMenuRequested.connect(self._onTableHeaderContextMenu)

        layout.addWidget(self._table, 1)

        # --- Status label ---
        self._status_label = QLabel("0 items")
        self._status_label.setObjectName("panelLabel")
        layout.addWidget(self._status_label)

        self._frame = self
        self._updateFrameStyle()
        self._updateFilterPlaceholder()

    # --------------------------------------------------------
    # Column width persistence (first three columns; settings.json)
    # Last column ("Date Modified") stretches to the pane edge — not persisted.
    # --------------------------------------------------------
    COLUMN_WIDTH_KEYS = ("name", "size", "type")
    COLUMN_VISIBILITY_KEYS = ("name", "size", "type", "date_modified")

    def applyColumnVisibility(self, vis_dict):
        """Show/hide columns from saved state (keys: name, size, type, date_modified)."""
        if not vis_dict:
            return
        for col, key in enumerate(self.COLUMN_VISIBILITY_KEYS):
            if col >= self._source_model.columnCount():
                break
            v = vis_dict.get(key)
            if v is not None:
                self._table.setColumnHidden(col, not bool(v))

    def getColumnVisibility(self):
        """Return visibility flags for each column."""
        return {
            key: not self._table.isColumnHidden(col)
            for col, key in enumerate(self.COLUMN_VISIBILITY_KEYS)
            if col < self._source_model.columnCount()
        }

    def applyColumnWidths(self, widths_dict):
        """Apply saved widths for name/size/type. Date column fills remaining width."""
        if not widths_dict:
            return
        for col, key in enumerate(self.COLUMN_WIDTH_KEYS):
            if col >= self._source_model.columnCount():
                break
            w = widths_dict.get(key)
            if w is not None and isinstance(w, (int, float)) and w > 0:
                self._table.setColumnWidth(col, int(w))

    def getColumnWidths(self):
        """Return fixed column widths for saving (last column stretches; omitted)."""
        return {
            key: self._table.columnWidth(col)
            for col, key in enumerate(self.COLUMN_WIDTH_KEYS)
            if col < self._source_model.columnCount()
        }

    # --------------------------------------------------------
    # Method: _connectSignals
    # --------------------------------------------------------
    def _connectSignals(self):
        self._btn_back.clicked.connect(self.goBack)
        self._btn_forward.clicked.connect(self.goForward)
        self._btn_up.clicked.connect(self.goUp)
        self._btn_new_folder.clicked.connect(self.createNewFolder)
        self._path_edit.returnPressed.connect(self._onPathEdited)
        self._filter_edit.textChanged.connect(self._onFilterChanged)
        self._table.doubleClicked.connect(self._onItemDoubleClicked)
        self._table.filesDropped.connect(self._onFilesDropped)
        self._table.panelPressed.connect(self.activated.emit)
        self._table.slowClickRenameRequested.connect(self.startRename)
        self._table.emptyAreaPressed.connect(self.activated.emit)

        selection_model = self._table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._onSelectionChanged)

        self._source_model.modelReset.connect(self._updateStatusLabel)

    # --------------------------------------------------------
    # Method: _installActivationEventFilters
    # Purpose: Makes clicks and focus on panel chrome activate
    #          the panel even when no file is selected.
    # --------------------------------------------------------
    def _installActivationEventFilters(self):
        activation_widgets = [
            self._path_edit,
            self._filter_edit,
            self._btn_copy_path,
            self._btn_paste_path,
            self._btn_browse_folder,
            self._btn_back,
            self._btn_forward,
            self._btn_up,
            self._btn_home,
            self._chk_filter_subfolders,
            self._btn_filter_clear,
            self._btn_filter_options,
            self._btn_new_folder,
            self._drive_combo,
            self._drive_arrow,
            self._table.horizontalHeader(),
        ]

        combo_line_edit = self._drive_combo.lineEdit()
        if combo_line_edit is not None:
            activation_widgets.append(combo_line_edit)

        for widget in activation_widgets:
            widget.installEventFilter(self)

    # --------------------------------------------------------
    # Method: _scrollFileTableToTop
    # Purpose: Resets vertical (and horizontal) scroll after
    #          opening a folder so the list starts at the top.
    # --------------------------------------------------------
    def _scrollFileTableToTop(self):
        self._table.scrollToTop()
        hbar = self._table.horizontalScrollBar()
        if hbar is not None:
            hbar.setValue(0)

    # --------------------------------------------------------
    # Method: navigateTo
    # Purpose: Loads a directory and pushes it to the history.
    # --------------------------------------------------------
    def navigateTo(self, path, add_to_history=True):
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            return

        if self.isRenaming():
            self._commitRename()
        self._table.cancelPendingRename()

        if add_to_history:
            if self._history_index >= 0 and self._history_index < len(self._history) - 1:
                self._history = self._history[:self._history_index + 1]
            self._history.append(path)
            self._history_index = len(self._history) - 1

        self._source_model.loadDirectory(path)
        self._path_edit.setText(path)
        self._updateNavButtons()
        self._updateStatusLabel()
        self._syncDriveCombo(path)
        self.pathChanged.emit(path)
        QTimer.singleShot(0, self._scrollFileTableToTop)

    # --------------------------------------------------------
    # Method: refresh
    # Purpose: Reloads the current directory.
    # --------------------------------------------------------
    def refresh(self):
        current = self._source_model.currentPath()
        if current:
            self._source_model.loadDirectory(current)
            self._updateStatusLabel()

    # --------------------------------------------------------
    # Method: createNewFolder
    # Purpose: Prompts for a name and creates a subfolder in this
    #          panel's current directory (same behavior as F8 for
    #          the active panel).
    # --------------------------------------------------------
    def createNewFolder(self):
        current_path = self.currentPath()
        if not current_path:
            return
        dlg_parent = self.window()
        name, ok = QInputDialog.getText(
            dlg_parent, "New Folder", "Folder name:",
        )
        if not ok or not name.strip():
            return
        folder_name = name.strip()
        new_path = os.path.join(current_path, folder_name)
        try:
            os.makedirs(new_path, exist_ok=True)
            self.refresh()
            self.folderCreated.emit(folder_name)
        except OSError as e:
            QMessageBox.warning(
                dlg_parent, "Error", f"Could not create folder:\n{e}"
            )

    # --------------------------------------------------------
    # Method: currentPath
    # --------------------------------------------------------
    def currentPath(self):
        return self._source_model.currentPath()

    # --------------------------------------------------------
    # Method: selectedEntries
    # Purpose: Returns a list of entry dicts for selected rows.
    # --------------------------------------------------------
    def selectedEntries(self):
        entries = []
        for index in self._table.selectionModel().selectedRows():
            source_index = self._proxy_model.mapToSource(index)
            entry = self._source_model.entryAt(source_index.row())
            if entry:
                entries.append(entry)
        return entries

    # --------------------------------------------------------
    # Method: selectedPaths
    # Purpose: Returns a list of full paths for selected items.
    # --------------------------------------------------------
    def selectedPaths(self):
        return [e["full_path"] for e in self.selectedEntries()]

    # --------------------------------------------------------
    # Navigation Methods
    # --------------------------------------------------------
    def goBack(self):
        if self._history_index > 0:
            self._history_index -= 1
            self.navigateTo(self._history[self._history_index], add_to_history=False)

    def goForward(self):
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.navigateTo(self._history[self._history_index], add_to_history=False)

    def goUp(self):
        current = self._source_model.currentPath()
        if current:
            parent = os.path.dirname(current)
            if parent and parent != current:
                self.navigateTo(parent)

    # --------------------------------------------------------
    # Active State
    # --------------------------------------------------------
    def setActive(self, active):
        self._is_active = active
        self._updateFrameStyle()
        if not active:
            self._table.cancelPendingRename()
            if self.isRenaming():
                self._commitRename()

    def isActive(self):
        return self._is_active

    def panelSide(self):
        return self._panel_side

    # --------------------------------------------------------
    # Show / Hide Hidden Files
    # --------------------------------------------------------
    def setShowHidden(self, show):
        self._source_model.setShowHidden(show)

    # --------------------------------------------------------
    # In-Place Rename
    #
    # Triggered by:
    #   - F2 key or toolbar/menu "Rename"
    #   - Slow-click (click on already-selected file after delay)
    #
    # Behavior:
    #   - Enter  → commits the rename
    #   - Escape → cancels the rename
    #   - Click outside (focus lost) → cancels the rename
    #   - Selects just the filename stem (not the extension)
    # --------------------------------------------------------
    def isRenaming(self):
        return self._rename_edit is not None and self._rename_edit.isVisible()

    def startRename(self):
        if self._rename_edit is not None:
            self._dismissRenameEditor()

        indexes = self._table.selectionModel().selectedRows()
        if len(indexes) != 1:
            return
        proxy_index = indexes[0]
        name_index = self._proxy_model.index(proxy_index.row(), 0)
        source_index = self._proxy_model.mapToSource(proxy_index)
        entry = self._source_model.entryAt(source_index.row())
        if entry is None:
            return

        self._rename_committed = False
        self._rename_source_row = source_index.row()
        self._rename_old_name = entry["name"]
        self._rename_old_full_path = entry["full_path"]

        self._rename_edit = _RenameLineEdit(self._table.viewport())
        rect = self._table.visualRect(name_index)
        icon_offset = 28
        self._rename_edit.setGeometry(
            rect.x() + icon_offset, rect.y(),
            rect.width() - icon_offset, rect.height()
        )
        self._rename_edit.setText(entry["name"])

        name_part = os.path.basename(entry["name"])
        dot_pos = name_part.rfind(".")
        if dot_pos > 0 and not entry["is_dir"]:
            self._rename_edit.setSelection(0, dot_pos)
        else:
            self._rename_edit.selectAll()

        self._rename_edit.enterPressed.connect(self._commitRename)
        self._rename_edit.escapePressed.connect(self._cancelRename)
        self._rename_edit.focusLostSignal.connect(self._commitRename)

        self._rename_edit.setFocus()
        self._rename_edit.show()

    # --------------------------------------------------------
    # Method: commitRename  (public so the main window can
    #         call it when Enter is pressed at window level)
    # Purpose: Applies the new name. If a file with the same
    #          name already exists, auto-increments the name
    #          (e.g. "file (1).txt", "file (2).txt").
    # --------------------------------------------------------
    def commitRename(self):
        self._commitRename()

    def _commitRename(self):
        if self._rename_edit is None or self._rename_committed:
            return
        self._rename_committed = True
        new_name = self._rename_edit.text().strip()
        self._dismissRenameEditor()

        if not new_name or new_name == self._rename_old_name:
            return

        current_dir = self._source_model.currentPath()
        old_path = getattr(self, "_rename_old_full_path", None) or path_under_root(
            current_dir, self._rename_old_name
        )
        new_path = path_under_root(current_dir, new_name)

        if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(old_path):
            parent = os.path.dirname(new_path)
            base = os.path.basename(new_path)
            new_base = self._resolveNameConflict(parent, base)
            new_path = os.path.join(parent, new_base)
            try:
                new_name = os.path.relpath(new_path, current_dir)
            except ValueError:
                new_name = new_base

        try:
            os.rename(old_path, new_path)
            self._source_model.renameEntry(self._rename_source_row, new_name)
        except OSError as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Rename Failed", str(e))

    # --------------------------------------------------------
    # Method: _resolveNameConflict
    # Purpose: If new_name already exists in the directory,
    #          appends an incrementing number until unique.
    #          e.g. "report.txt" → "report (1).txt"
    # --------------------------------------------------------
    def _resolveNameConflict(self, directory, name):
        base, ext = os.path.splitext(name)
        counter = 1
        candidate = name
        while os.path.exists(os.path.join(directory, candidate)):
            candidate = f"{base} ({counter}){ext}"
            counter += 1
        return candidate

    # --------------------------------------------------------
    # Method: _cancelRename
    # Purpose: Called only on Escape. Discards edits.
    # --------------------------------------------------------
    def _cancelRename(self):
        if self._rename_committed:
            return
        self._rename_committed = True
        self._dismissRenameEditor()

    # --------------------------------------------------------
    # Method: _dismissRenameEditor
    # Purpose: Safely hides and destroys the inline editor.
    # --------------------------------------------------------
    def _dismissRenameEditor(self):
        if self._rename_edit is not None:
            self._rename_edit.hide()
            self._rename_edit.deleteLater()
            self._rename_edit = None

    # --------------------------------------------------------
    # History / State for Persistence
    # --------------------------------------------------------
    def getHistoryData(self):
        return {
            "current_path": self._source_model.currentPath(),
            "history": self._history,
            "column_widths": self.getColumnWidths(),
            "column_visibility": self.getColumnVisibility(),
            "filter_mode": self._proxy_model.filterMode(),
            "filter_kind": self._proxy_model.entryKindFilter(),
            "filter_text": self._filter_edit.text(),
            "filter_include_subfolders": self._chk_filter_subfolders.isChecked(),
            "filter_advanced": self._proxy_model.filterSpec().to_dict(),
        }

    def restoreHistoryData(self, data):
        self._history = data.get("history", [])
        self._chk_filter_subfolders.blockSignals(True)
        self._chk_filter_subfolders.setChecked(data.get("filter_include_subfolders", False))
        self._chk_filter_subfolders.blockSignals(False)
        self._source_model.setRecursive(self._chk_filter_subfolders.isChecked())

        current = data.get("current_path", "")
        if current and os.path.isdir(current):
            self._history_index = len(self._history) - 1
            self.navigateTo(current, add_to_history=False)
        column_widths = data.get("column_widths")
        if column_widths:
            self.applyColumnWidths(column_widths)
        column_visibility = data.get("column_visibility")
        if column_visibility:
            self.applyColumnVisibility(column_visibility)
        fm = data.get("filter_mode")
        if fm in ("contains", "wildcard", "regex"):
            self._proxy_model.setFilterMode(fm)
        fk = data.get("filter_kind")
        if fk in ("all", "dirs", "files"):
            self._proxy_model.setEntryKindFilter(fk)
        self._filter_edit.blockSignals(True)
        self._filter_edit.setText(data.get("filter_text") or "")
        self._filter_edit.blockSignals(False)
        self._proxy_model.setFilterText(self._filter_edit.text())
        self._proxy_model.setFilterSpec(
            FilterSpec.from_dict(data.get("filter_advanced"))
        )
        self._updateFilterPlaceholder()

    # --------------------------------------------------------
    # Focus handling for active panel detection
    # --------------------------------------------------------
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.activated.emit()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.activated.emit()

    # --------------------------------------------------------
    # Event filter: Up/Down in path or filter moves file selection
    # --------------------------------------------------------
    def eventFilter(self, obj, event):
        activation_events = (QEvent.MouseButtonPress, QEvent.FocusIn)
        if event.type() in activation_events and obj in (
            self._path_edit,
            self._filter_edit,
            self._btn_copy_path,
            self._btn_paste_path,
            self._btn_browse_folder,
            self._btn_back,
            self._btn_forward,
            self._btn_up,
            self._btn_home,
            self._chk_filter_subfolders,
            self._btn_filter_clear,
            self._btn_filter_options,
            self._btn_new_folder,
            self._drive_combo,
            self._drive_arrow,
            self._table.horizontalHeader(),
            self._drive_combo.lineEdit(),
        ):
            self.activated.emit()

        if event.type() == QEvent.KeyPress and obj in (self._path_edit, self._filter_edit):
            if event.key() == Qt.Key_Up:
                self._table.setFocus()
                self._moveFileSelection(-1)
                return True
            if event.key() == Qt.Key_Down:
                self._table.setFocus()
                self._moveFileSelection(1)
                return True
        return super().eventFilter(obj, event)

    # --------------------------------------------------------
    # Method: _moveFileSelection
    # Purpose: Moves the current selection up or down by one row.
    #          direction: -1 = up, 1 = down.
    # --------------------------------------------------------
    def _moveFileSelection(self, direction):
        model = self._table.model()
        row_count = model.rowCount()
        if row_count == 0:
            return
        current = self._table.currentIndex()
        row = current.row() if current.isValid() else 0
        new_row = max(0, min(row_count - 1, row + direction))
        new_index = model.index(new_row, 0)
        self._table.setCurrentIndex(new_index)
        self._table.selectionModel().select(
            new_index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
        )
        self._table.scrollTo(new_index, QAbstractItemView.PositionAtCenter)

    # --------------------------------------------------------
    # Internal Slots
    # --------------------------------------------------------
    def _onPathEdited(self):
        path = normalizePathInput(self._path_edit.text())
        if path and os.path.isdir(path):
            self.navigateTo(path)

    def _copyPathToClipboard(self):
        """Copy current folder path to clipboard."""
        path = self._source_model.currentPath()
        if path:
            clipboard = QApplication.clipboard()
            clipboard.setText(path)
            self.pathCopied.emit(path)

    def _pastePathAndNavigate(self):
        """Paste path from clipboard and navigate to that folder."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        path = normalizePathInput(text)
        if not path:
            return
        if os.path.isdir(path):
            self._path_edit.setText(path)
            self.navigateTo(path)
        elif os.path.isfile(path):
            parent = os.path.dirname(path)
            if parent and os.path.isdir(parent):
                self._path_edit.setText(parent)
                self.navigateTo(parent)

    def _openCurrentFolderInSystemExplorer(self):
        """Open this panel's current folder in the OS file manager (no dialog)."""
        path = self._source_model.currentPath()
        if not path or not os.path.isdir(path):
            return
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", os.path.normpath(path)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except OSError:
            pass

    def _onDriveChanged(self, index):
        if index < 0 or not self._drive_combo.isVisible():
            return
        drive = self._drive_combo.currentText()
        if drive and os.path.isdir(drive):
            self.navigateTo(drive)

    def _onDriveArrowClicked(self, event):
        if self._drive_combo.isVisible():
            self._drive_combo.showPopup()

    def _refreshDrives(self):
        """Re-scan for drives (USB, external disks) and update the dropdown.

        On Windows, called automatically when the drive menu is opened.
        """
        if not self._drive_combo.isVisible() and os.name != "nt":
            return
        drives = getWindowsDrives()
        self._drive_combo.blockSignals(True)
        self._drive_combo.clear()
        if drives:
            self._drive_combo.addItems(drives)
            self._drive_combo.setVisible(True)
            self._drive_arrow.setVisible(True)
            self._syncDriveCombo(self._source_model.currentPath())
        self._drive_combo.blockSignals(False)

    def _syncDriveCombo(self, path):
        """Keep drive dropdown in sync with current path (Windows)."""
        if not self._drive_combo.isVisible():
            return
        path = os.path.normpath(path)
        root, _ = os.path.splitdrive(path)
        if not root:
            return
        drive = (root + "\\") if not root.endswith("\\") else root
        drive_upper = drive.upper()
        for i in range(self._drive_combo.count()):
            if self._drive_combo.itemText(i).upper() == drive_upper:
                self._drive_combo.blockSignals(True)
                self._drive_combo.setCurrentIndex(i)
                self._drive_combo.blockSignals(False)
                break

    def _goHome(self):
        """Navigate to the user's home directory (OS-dependent)."""
        home = os.path.expanduser("~")
        if home and os.path.isdir(home):
            self.navigateTo(home)

    # --------------------------------------------------------
    # Column header context menu (show/hide columns)
    # --------------------------------------------------------
    def _onTableHeaderContextMenu(self, pos):
        menu = QMenu(self)
        n = self._source_model.columnCount()
        for col in range(n):
            label = FileSystemModel.COLUMNS[col]
            act = QAction(label, menu)
            act.setCheckable(True)
            act.setChecked(not self._table.isColumnHidden(col))
            act.toggled.connect(
                lambda checked, c=col, a=act: self._applyColumnVisibilityToggle(c, checked, a)
            )
            menu.addAction(act)
        menu.addSeparator()
        act_even = QAction("Distribute columns evenly", menu)
        act_even.setToolTip(
            "Distribute columns evenly\n\n"
            "Resize all visible columns to the same width so together they fill the panel."
        )
        act_even.triggered.connect(self._distributeColumnsEvenly)
        menu.addAction(act_even)
        hdr = self._table.horizontalHeader()
        menu.exec_(hdr.mapToGlobal(pos))

    def _applyColumnVisibilityToggle(self, col, visible, action):
        if not visible:
            others = sum(
                1
                for c in range(self._source_model.columnCount())
                if c != col and not self._table.isColumnHidden(c)
            )
            if others == 0:
                QMessageBox.information(
                    self,
                    "Columns",
                    "At least one column must stay visible.",
                )
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
                return
        self._table.setColumnHidden(col, not visible)

    def _distributeColumnsEvenly(self):
        """Give each visible column an equal share of the table viewport width."""
        hdr = self._table.horizontalHeader()
        n = self._source_model.columnCount()
        visible = [c for c in range(n) if not self._table.isColumnHidden(c)]
        m = len(visible)
        if m == 0:
            return
        vw = max(1, self._table.viewport().width())
        min_w = max(hdr.minimumSectionSize(), 24)
        hdr.setStretchLastSection(False)
        base = vw // m
        rem = vw % m
        for i, col in enumerate(visible):
            wcol = base + (1 if i < rem else 0)
            wcol = max(min_w, wcol)
            self._table.setColumnWidth(col, wcol)

    # --------------------------------------------------------
    # Filter options dialog and state
    # --------------------------------------------------------
    def getFilterState(self):
        return {
            "filter_text": self._filter_edit.text(),
            "filter_mode": self._proxy_model.filterMode(),
            "filter_kind": self._proxy_model.entryKindFilter(),
            "filter_include_subfolders": self._chk_filter_subfolders.isChecked(),
            "filter_advanced": self._proxy_model.filterSpec().to_dict(),
        }

    def applyFilterState(self, data):
        if not data:
            return
        ft = data.get("filter_text") or ""
        self._filter_edit.blockSignals(True)
        self._filter_edit.setText(ft)
        self._filter_edit.blockSignals(False)
        self._proxy_model.setFilterText(ft)
        fm = data.get("filter_mode")
        if fm in ("contains", "wildcard", "regex"):
            self._proxy_model.setFilterMode(fm)
        fk = data.get("filter_kind")
        if fk in ("all", "dirs", "files"):
            self._proxy_model.setEntryKindFilter(fk)
        self._proxy_model.setFilterSpec(
            FilterSpec.from_dict(data.get("filter_advanced"))
        )
        sub = bool(data.get("filter_include_subfolders", False))
        self._chk_filter_subfolders.blockSignals(True)
        self._chk_filter_subfolders.setChecked(sub)
        self._chk_filter_subfolders.blockSignals(False)
        self._source_model.setRecursive(sub)
        self._updateFilterPlaceholder()

    def clearFilter(self):
        self.applyFilterState({
            "filter_text": "",
            "filter_mode": "contains",
            "filter_kind": "all",
            "filter_include_subfolders": False,
            "filter_advanced": {},
        })

    def _onOpenFilterOptions(self):
        from filter_options_dialog import FilterOptionsDialog

        dlg = FilterOptionsDialog(self, self._settings_manager, self)
        dlg.exec_()

    def _onSubfoldersFilterToggled(self, *_args):
        self._source_model.setRecursive(self._chk_filter_subfolders.isChecked())
        self._updateFilterPlaceholder()

    def _updateFilterPlaceholder(self):
        hint = []
        mode = self._proxy_model.filterMode()
        kind = self._proxy_model.entryKindFilter()
        if mode == "wildcard":
            hint.append("* ?")
        elif mode == "regex":
            hint.append("regex")
        if kind == "dirs":
            hint.append("folders")
        elif kind == "files":
            hint.append("files")
        if self._chk_filter_subfolders.isChecked():
            hint.append("subfolders")
        spec = self._proxy_model.filterSpec()
        if spec is not None and not spec.is_empty():
            hint.append("size/date")
        extra = (" · " + ", ".join(hint)) if hint else ""
        self._filter_edit.setPlaceholderText(f"\U0001F50D Filter{extra}…")

    def _onFilterChanged(self, text):
        self._proxy_model.setFilterText(text)

    def _onItemDoubleClicked(self, proxy_index):
        source_index = self._proxy_model.mapToSource(proxy_index)
        entry = self._source_model.entryAt(source_index.row())
        if entry is None:
            return
        if entry["is_dir"]:
            self.navigateTo(entry["full_path"])
        else:
            self.fileDoubleClicked.emit(entry)

    def _onFilesDropped(self, file_paths, drop_target, is_copy):
        self.activated.emit()
        self.filesDropped.emit(file_paths, drop_target, is_copy)

    def _onSelectionChanged(self):
        self.selectionChanged.emit()

    def _updateNavButtons(self):
        self._btn_back.setEnabled(self._history_index > 0)
        self._btn_forward.setEnabled(
            self._history_index < len(self._history) - 1
        )
        current = self._source_model.currentPath()
        parent = os.path.dirname(current) if current else ""
        self._btn_up.setEnabled(bool(parent) and parent != current)

    def _updateStatusLabel(self):
        total = self._source_model.rowCount()
        dirs = sum(
            1 for i in range(total)
            if self._source_model.entryAt(i) and self._source_model.entryAt(i)["is_dir"]
        )
        files = total - dirs
        self._status_label.setText(f"{files} file(s), {dirs} folder(s)")

    def _updateFrameStyle(self):
        if self._is_active:
            self.setObjectName("filePanelActive")
        else:
            self.setObjectName("filePanel")
        style = self.style()
        if style is not None:
            for w in (self, self._path_edit, self._table):
                style.unpolish(w)
                style.polish(w)
        self.update()

    # --------------------------------------------------------
    # Public accessors for child widgets (used by main window)
    # --------------------------------------------------------
    def tableView(self):
        return self._table

    def sourceModel(self):
        return self._source_model

    def proxyModel(self):
        return self._proxy_model

    def pathEdit(self):
        return self._path_edit

    def filterEdit(self):
        return self._filter_edit
