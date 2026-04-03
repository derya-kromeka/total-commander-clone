"""
Total Commander Clone - File Panel Widget
A single file-browser pane with address bar, navigation buttons,
file table, sorting, filtering, in-place rename, and drag-and-drop.
"""

import os
import platform
import re
import stat
import string
import subprocess
import time
from datetime import datetime


# Pattern for splitting names into text vs digit runs (natural sort).
_NATURAL_SORT_SPLIT = re.compile(r"(\d+)")

# ------------------------------------------------------------
# Helper: natural_sort_key
# Purpose: Sort key so embedded numbers compare numerically
#          (e.g. KT-167 before KT-1665, file2 before file10).
#          Each segment is (0, int) or (1, str) so list compare
#          never mixes bare int with str (e.g. "33112_x" vs "a_1").
# ------------------------------------------------------------
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
    QFileIconProvider,
)
from PyQt5.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QVariant, QMimeData,
    QUrl, pyqtSignal, QSortFilterProxyModel, QPoint, QTimer, QEvent,
    QItemSelectionModel, QSize, QItemSelection, QItemSelectionRange,
    QFileInfo,
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
# ============================================================
class DrivePickerCombo(QComboBox):

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

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = ""
        self._entries = []
        self._show_hidden = False
        self._icon_provider = QFileIconProvider()

    # --------------------------------------------------------
    # Method: setShowHidden
    # Purpose: Toggles visibility of hidden files/dotfiles.
    # --------------------------------------------------------
    def setShowHidden(self, show):
        self._show_hidden = show
        if self._current_path:
            self.loadDirectory(self._current_path)

    # --------------------------------------------------------
    # Method: loadDirectory
    # Purpose: Scans the given directory and populates the model.
    # Input: path (str) - The directory to load.
    # --------------------------------------------------------
    def loadDirectory(self, path):
        self.beginResetModel()
        self._current_path = path
        self._entries = []

        try:
            items = os.listdir(path)
        except PermissionError:
            self.endResetModel()
            return
        except OSError:
            self.endResetModel()
            return

        for name in items:
            if not self._show_hidden and name.startswith("."):
                continue

            full_path = os.path.join(path, name)
            try:
                st = os.stat(full_path)
                is_dir = stat.S_ISDIR(st.st_mode)

                if not self._show_hidden and os.name == "nt":
                    attrs = st.st_file_attributes
                    if attrs & stat.FILE_ATTRIBUTE_HIDDEN:
                        continue

                size = st.st_size if not is_dir else -1
                mod_time = st.st_mtime
                file_type = getFileTypeDescription(full_path, is_dir)

                self._entries.append({
                    "name": name,
                    "size": size,
                    "type": file_type,
                    "mod_time": mod_time,
                    "is_dir": is_dir,
                    "full_path": full_path,
                })
            except (PermissionError, OSError):
                continue

        self._entries.sort(key=lambda e: (not e["is_dir"], natural_sort_key(e["name"])))
        self.endResetModel()

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
            new_path = os.path.join(self._current_path, new_name)
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
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
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
        self.setDynamicSortFilter(True)

    # --------------------------------------------------------
    # Method: setFilterText
    # --------------------------------------------------------
    def setFilterText(self, text):
        self._filter_text = text.lower()
        self.invalidateFilter()

    # --------------------------------------------------------
    # Method: filterAcceptsRow
    # --------------------------------------------------------
    def filterAcceptsRow(self, source_row, source_parent):
        if not self._filter_text:
            return True
        model = self.sourceModel()
        entry = model.entryAt(source_row)
        if entry is None:
            return False
        return self._filter_text in entry["name"].lower()

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

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
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
    fileDoubleClicked = pyqtSignal(dict)
    selectionChanged = pyqtSignal()
    filesDropped = pyqtSignal(list, str, bool)
    activated = pyqtSignal()

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, panel_side="left", parent=None):
        super().__init__(parent)
        self._panel_side = panel_side
        self._history = []
        self._history_index = -1
        self._is_active = False
        self._rename_edit = None

        self._initUI()
        self._connectSignals()
        self._path_edit.installEventFilter(self)
        self._filter_edit.installEventFilter(self)
        self._installActivationEventFilters()

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
        self._path_edit.setPlaceholderText("Enter or paste path, press Enter to go...")
        self._path_edit.setMinimumHeight(NAV_BAR_HEIGHT)

        self._btn_copy_path = QPushButton()
        self._btn_copy_path.setObjectName("navButton")
        self._btn_copy_path.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_copy_path.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._btn_copy_path.setToolTip("Copy current path to clipboard")
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
        self._btn_paste_path.setToolTip("Paste path from clipboard and go")
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
        self._btn_browse_folder.setToolTip("Open current folder in system file explorer")
        self._btn_browse_folder.setAutoDefault(False)
        self._btn_browse_folder.setDefault(False)
        self._btn_browse_folder.setIcon(style.standardIcon(QStyle.SP_DirOpenIcon))
        self._btn_browse_folder.clicked.connect(self._openCurrentFolderInSystemExplorer)

        path_layout.addWidget(self._path_edit, 1)
        path_layout.addWidget(self._btn_copy_path)
        path_layout.addWidget(self._btn_paste_path)
        path_layout.addWidget(self._btn_browse_folder)
        layout.addLayout(path_layout)

        # --- Navigation bar (back, forward, up, home, drive, filter) ---
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
        self._btn_back.setToolTip("Back (Alt+Left)")
        self._btn_back.setIcon(style.standardIcon(QStyle.SP_ArrowBack))
        self._btn_back.setEnabled(False)
        self._btn_forward.setToolTip("Forward (Alt+Right)")
        self._btn_forward.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        self._btn_forward.setEnabled(False)
        self._btn_up.setToolTip("Up one level (Backspace)")
        self._btn_up.setIcon(style.standardIcon(QStyle.SP_ArrowUp))
        self._btn_home.setToolTip("Home folder")
        self._btn_home.setText("\U0001F3E0")
        self._btn_home.clicked.connect(self._goHome)

        self._drive_combo = DrivePickerCombo()
        self._drive_combo.setObjectName("driveCombo")
        self._drive_combo.setToolTip("Switch drive")
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

        self._drive_container = QWidget()
        self._drive_container.setFixedSize(72, NAV_BAR_HEIGHT)
        drive_container_layout = QHBoxLayout(self._drive_container)
        drive_container_layout.setContentsMargins(0, 0, 0, 0)
        drive_container_layout.setSpacing(0)
        drive_container_layout.addWidget(self._drive_combo, 0, Qt.AlignVCenter)
        drive_container_layout.addWidget(self._drive_arrow, 0, Qt.AlignVCenter)

        self._btn_refresh_drives = QPushButton()
        self._btn_refresh_drives.setObjectName("navButton")
        self._btn_refresh_drives.setFixedSize(30, NAV_BAR_HEIGHT)
        self._btn_refresh_drives.setIconSize(QSize(NAV_ICON_SIZE - 2, NAV_ICON_SIZE - 2))
        self._btn_refresh_drives.setToolTip("Refresh drive list (detect USB, external disks)")
        self._btn_refresh_drives.setAutoDefault(False)
        self._btn_refresh_drives.setDefault(False)
        refresh_icon = QIcon.fromTheme("view-refresh")
        if refresh_icon.isNull():
            refresh_icon = style.standardIcon(QStyle.SP_BrowserReload)
        if refresh_icon.isNull():
            self._btn_refresh_drives.setText("\u27F3")
        else:
            self._btn_refresh_drives.setIcon(refresh_icon)
        self._btn_refresh_drives.clicked.connect(self._refreshDrives)
        self._btn_refresh_drives.setVisible(os.name == "nt")

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("\U0001F50D Filter...")
        self._filter_edit.setMinimumWidth(120)
        self._filter_edit.setMinimumHeight(NAV_BAR_HEIGHT)
        self._filter_edit.setClearButtonEnabled(True)

        nav_layout.addWidget(self._btn_back)
        nav_layout.addWidget(self._btn_forward)
        nav_layout.addWidget(self._btn_up)
        nav_layout.addWidget(self._btn_home)
        nav_layout.addWidget(self._drive_container)
        nav_layout.addWidget(self._btn_refresh_drives)
        nav_layout.addWidget(self._filter_edit, 1)

        layout.addLayout(nav_layout)

        # --- File table ---
        self._source_model = FileSystemModel(self)
        self._proxy_model = FileSortFilterProxy(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._table = FileTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.sortByColumn(0, Qt.AscendingOrder)

        layout.addWidget(self._table, 1)

        # --- Status label ---
        self._status_label = QLabel("0 items")
        self._status_label.setObjectName("panelLabel")
        layout.addWidget(self._status_label)

        self._frame = self
        self._updateFrameStyle()

    # --------------------------------------------------------
    # Column width persistence (key order matches settings.json)
    # --------------------------------------------------------
    COLUMN_KEYS = ("name", "size", "type", "date_modified")

    def applyColumnWidths(self, widths_dict):
        """Apply saved column widths. widths_dict: e.g. {'name': 300, 'size': 100, ...}"""
        if not widths_dict:
            return
        for col, key in enumerate(self.COLUMN_KEYS):
            if col >= self._source_model.columnCount():
                break
            w = widths_dict.get(key)
            if w is not None and isinstance(w, (int, float)) and w > 0:
                self._table.setColumnWidth(col, int(w))

    def getColumnWidths(self):
        """Return current column widths as a dict for saving to settings."""
        return {
            key: self._table.columnWidth(col)
            for col, key in enumerate(self.COLUMN_KEYS)
            if col < self._source_model.columnCount()
        }

    # --------------------------------------------------------
    # Method: _connectSignals
    # --------------------------------------------------------
    def _connectSignals(self):
        self._btn_back.clicked.connect(self.goBack)
        self._btn_forward.clicked.connect(self.goForward)
        self._btn_up.clicked.connect(self.goUp)
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
            self._drive_combo,
            self._drive_arrow,
            self._btn_refresh_drives,
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

        self._rename_edit = _RenameLineEdit(self._table.viewport())
        rect = self._table.visualRect(name_index)
        icon_offset = 28
        self._rename_edit.setGeometry(
            rect.x() + icon_offset, rect.y(),
            rect.width() - icon_offset, rect.height()
        )
        self._rename_edit.setText(entry["name"])

        name_part = entry["name"]
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
        old_path = os.path.join(current_dir, self._rename_old_name)
        new_path = os.path.join(current_dir, new_name)

        if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(old_path):
            new_name = self._resolveNameConflict(current_dir, new_name)
            new_path = os.path.join(current_dir, new_name)

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
        }

    def restoreHistoryData(self, data):
        self._history = data.get("history", [])
        current = data.get("current_path", "")
        if current and os.path.isdir(current):
            self._history_index = len(self._history) - 1
            self.navigateTo(current, add_to_history=False)
        column_widths = data.get("column_widths")
        if column_widths:
            self.applyColumnWidths(column_widths)

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
            self._drive_combo,
            self._drive_arrow,
            self._btn_refresh_drives,
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
        """Re-scan for drives (USB, external disks) and update the dropdown."""
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
            style.unpolish(self)
            style.polish(self)
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
