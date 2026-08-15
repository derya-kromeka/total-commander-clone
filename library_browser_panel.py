"""
Total Commander Clone - Library Browser Panel
Full panel-sized catalog search with multi-library filters and
paged results from the local SQLite index.
"""

import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QSplitter, QTableView, QVBoxLayout, QWidget,
)

from library_catalog import FIELD_TAGS, FIELD_TYPE_BOOLEAN, FIELD_TYPE_NUMBER, FIELD_TYPE_DATE
from library_search_model import ROLE_ITEM, LibrarySearchModel
from ui_layout_policy import LayoutTier, tierAtMost


# ------------------------------------------------------------
# Class: LibraryBrowserPanel
# ------------------------------------------------------------
class LibraryBrowserPanel(QWidget):

    navigateRequested = pyqtSignal(str)
    navigateInPanelRequested = pyqtSignal(str, str)
    switchToFilePanelRequested = pyqtSignal()
    addLibraryRequested = pyqtSignal()
    scanLibrariesRequested = pyqtSignal()
    assignTagsRequested = pyqtSignal()
    manageLibrariesRequested = pyqtSignal()
    locateRootRequested = pyqtSignal(str)
    activated = pyqtSignal()

    def __init__(self, side="left", library_manager=None, parent=None):
        super().__init__(parent)
        self._side = side
        self._manager = library_manager
        self._libraries = []
        self._selected_library_id = ""
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._applySearch)
        self._initUI()

    def setLibraryManager(self, library_manager):
        self._manager = library_manager
        if library_manager is not None:
            self._model = LibrarySearchModel(library_manager, self)
            self._results.setModel(self._model)
            self._results.setSortingEnabled(True)

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Library Browser")
        title.setObjectName("sidebarPanelTitle")
        header.addWidget(title)
        header.addStretch()
        self._btn_switch = QPushButton("File Panel")
        self._btn_switch.setObjectName("libraryToolButton")
        self._btn_switch.clicked.connect(self.switchToFilePanelRequested.emit)
        header.addWidget(self._btn_switch)
        layout.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search names and paths…")
        self._search.textChanged.connect(lambda: self._search_timer.start())
        layout.addWidget(self._search)

        content = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        left_layout.addWidget(QLabel("Libraries"))
        self._library_list = QListWidget()
        self._library_list.itemChanged.connect(lambda _item: self._applySearch())
        left_layout.addWidget(self._library_list, 1)

        left_layout.addWidget(QLabel("Tags"))
        mode_row = QHBoxLayout()
        self._tags_all = QRadioButton("All")
        self._tags_any = QRadioButton("Any")
        self._tags_all.setChecked(True)
        self._tags_all.toggled.connect(self._applySearch)
        mode_row.addWidget(self._tags_all)
        mode_row.addWidget(self._tags_any)
        mode_row.addStretch()
        left_layout.addLayout(mode_row)
        self._tag_list = QListWidget()
        self._tag_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._tag_list.itemSelectionChanged.connect(self._applySearch)
        left_layout.addWidget(self._tag_list, 1)

        filter_row = QHBoxLayout()
        self._field_combo = QComboBox()
        self._op_combo = QComboBox()
        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("Value")
        self._btn_add_filter = QPushButton("Add")
        self._btn_add_filter.clicked.connect(self._onAddFieldFilter)
        filter_row.addWidget(self._field_combo, 1)
        filter_row.addWidget(self._op_combo)
        filter_row.addWidget(self._value_edit, 1)
        filter_row.addWidget(self._btn_add_filter)
        left_layout.addLayout(filter_row)
        self._active_filters = QListWidget()
        self._active_filters.itemDoubleClicked.connect(self._onRemoveFilter)
        left_layout.addWidget(self._active_filters)
        content.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._results_label = QLabel("Results (0)")
        self._results_label.setObjectName("sidebarSectionTitle")
        right_layout.addWidget(self._results_label)
        self._results = QTableView()
        self._results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._results.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._results.setAlternatingRowColors(True)
        self._results.verticalHeader().setVisible(False)
        self._results.doubleClicked.connect(self._onDoubleClicked)
        header_view = self._results.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        right_layout.addWidget(self._results, 1)
        content.addWidget(right)
        content.setSizes([240, 480])
        self._content_splitter = content
        layout.addWidget(content, 1)

        tools = QHBoxLayout()
        self._btn_manage = QPushButton("Manage")
        self._btn_add_root = QPushButton("Add Root")
        self._btn_scan = QPushButton("Check")
        self._btn_assign = QPushButton("Properties")
        self._btn_manage.setObjectName("libraryToolButton")
        self._btn_add_root.setObjectName("libraryToolButton")
        self._btn_scan.setObjectName("libraryToolButton")
        self._btn_assign.setObjectName("libraryToolButton")
        self._btn_manage.clicked.connect(self.manageLibrariesRequested.emit)
        self._btn_add_root.clicked.connect(self.addLibraryRequested.emit)
        self._btn_scan.clicked.connect(self.scanLibrariesRequested.emit)
        self._btn_assign.clicked.connect(self.assignTagsRequested.emit)
        tools.addWidget(self._btn_manage)
        tools.addWidget(self._btn_add_root)
        tools.addWidget(self._btn_scan)
        tools.addWidget(self._btn_assign)
        tools.addStretch()
        layout.addLayout(tools)

        actions = QHBoxLayout()
        self._btn_open_active = QPushButton("Open in Active Panel")
        self._btn_open_left = QPushButton("Open in Left")
        self._btn_open_right = QPushButton("Open in Right")
        self._btn_open_active.setObjectName("libraryToolButton")
        self._btn_open_left.setObjectName("libraryToolButton")
        self._btn_open_right.setObjectName("libraryToolButton")
        self._btn_open_active.clicked.connect(self._onOpenInActivePanel)
        self._btn_open_left.clicked.connect(lambda: self._onOpenInPanel("left"))
        self._btn_open_right.clicked.connect(lambda: self._onOpenInPanel("right"))
        actions.addWidget(self._btn_open_active, 1)
        actions.addWidget(self._btn_open_left)
        actions.addWidget(self._btn_open_right)
        layout.addLayout(actions)
        self.setObjectName("libraryPanel")
        self._model = None
        self._field_filters = []

    def mousePressEvent(self, event):
        self.activated.emit()
        super().mousePressEvent(event)

    def splitterSizes(self):
        return self._content_splitter.sizes()

    def applySplitterSizes(self, sizes):
        if isinstance(sizes, (list, tuple)) and len(sizes) >= 2:
            self._content_splitter.setSizes([int(s) for s in sizes[:2]])

    def applyLayoutTier(self, tier):
        compact = tierAtMost(tier, LayoutTier.NARROW)
        self._btn_add_root.setText("Add" if compact else "Add Root")
        self._btn_scan.setText("Check")
        self._btn_assign.setText("Props" if compact else "Properties")
        self._btn_manage.setText("Manage")
        self._btn_switch.setText("Files" if compact else "File Panel")
        self._btn_open_active.setText("Open" if compact else "Open in Active Panel")
        self._btn_open_left.setText("Left" if compact else "Open in Left")
        self._btn_open_right.setText("Right" if compact else "Open in Right")

    def setData(self, libraries, tagged_folders=None, selected_library_id=""):
        del tagged_folders
        self._libraries = libraries or []
        available_ids = {lib.get("id", "") for lib in self._libraries}
        self._selected_library_id = (
            selected_library_id if selected_library_id in available_ids else self._selected_library_id
        )
        self._rebuildLibraries()
        self._rebuildTags()
        self._rebuildFields()
        self._applySearch()

    def selectedLibraryId(self):
        ids = self._checkedLibraryIds()
        if len(ids) == 1:
            return ids[0]
        return self._selected_library_id

    def selectedItems(self):
        if self._model is None:
            return []
        items = []
        for index in self._results.selectionModel().selectedRows() if self._results.selectionModel() else []:
            item = self._model.itemAt(index.row())
            if item:
                items.append(item)
        return items

    def _rebuildLibraries(self):
        selected = set(self._checkedLibraryIds())
        if self._selected_library_id:
            selected.add(self._selected_library_id)
        self._library_list.blockSignals(True)
        self._library_list.clear()
        for library in self._libraries:
            item = QListWidgetItem(library.get("name", "Library"))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            lib_id = library.get("id", "")
            item.setData(Qt.UserRole, lib_id)
            checked = (not selected) or (lib_id in selected)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            roots = library.get("roots") or []
            offline = sum(1 for root in roots if not root.get("is_available"))
            if offline:
                item.setText(f"{library.get('name', 'Library')} ({offline} offline)")
            self._library_list.addItem(item)
        self._library_list.blockSignals(False)

    def _rebuildTags(self):
        if self._manager is None:
            return
        previously = {item.text() for item in self._tag_list.selectedItems()}
        self._tag_list.blockSignals(True)
        self._tag_list.clear()
        for tag in self._manager.getAvailableTags():
            item = QListWidgetItem(tag)
            self._tag_list.addItem(item)
            if tag in previously:
                item.setSelected(True)
        self._tag_list.blockSignals(False)

    def _rebuildFields(self):
        if self._manager is None:
            return
        current = self._field_combo.currentData()
        self._field_combo.blockSignals(True)
        self._field_combo.clear()
        for field in self._manager.listFields():
            self._field_combo.addItem(field.get("name", "Field"), field.get("id"))
        self._field_combo.blockSignals(False)
        if current:
            index = self._field_combo.findData(current)
            if index >= 0:
                self._field_combo.setCurrentIndex(index)
        self._op_combo.clear()
        self._op_combo.addItems(["contains", "equals", "exists", "gt", "gte", "lt", "lte"])

    def _checkedLibraryIds(self):
        ids = []
        for index in range(self._library_list.count()):
            item = self._library_list.item(index)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _selectedTags(self):
        return [item.text() for item in self._tag_list.selectedItems()]

    def _onAddFieldFilter(self):
        field_id = self._field_combo.currentData()
        if not field_id:
            return
        op = self._op_combo.currentText()
        value = self._value_edit.text().strip()
        self._field_filters.append({"field_id": field_id, "op": op, "value": value})
        label = f"{self._field_combo.currentText()} {op} {value}".strip()
        self._active_filters.addItem(label)
        self._applySearch()

    def _onRemoveFilter(self, item):
        row = self._active_filters.row(item)
        if 0 <= row < len(self._field_filters):
            self._field_filters.pop(row)
        self._active_filters.takeItem(row)
        self._applySearch()

    def _applySearch(self):
        if self._model is None or self._manager is None:
            return
        tags = self._selectedTags()
        spec = {
            "library_ids": self._checkedLibraryIds(),
            "text": self._search.text().strip(),
            "field_filters": list(self._field_filters),
            "include_missing": True,
        }
        if self._tags_all.isChecked():
            spec["tags_all"] = tags
            spec["tags_any"] = []
        else:
            spec["tags_all"] = []
            spec["tags_any"] = tags
        self._model.setSpec(**spec)
        self._results_label.setText(f"Results ({self._model.totalCount()})")

    def _selectedPath(self):
        items = self.selectedItems()
        if not items:
            return ""
        item = items[0]
        if not item.get("is_available"):
            self.locateRootRequested.emit(item.get("root_id") or "")
            return ""
        path = item.get("resolved_path") or ""
        if item.get("is_dir") and os.path.isdir(path):
            return path
        if os.path.isfile(path):
            return os.path.dirname(path)
        return path if os.path.isdir(path) else ""

    def _onDoubleClicked(self, index):
        if self._model is None:
            return
        item = self._model.itemAt(index.row())
        if item is None:
            return
        if not item.get("is_available"):
            self.locateRootRequested.emit(item.get("root_id") or "")
            return
        path = item.get("resolved_path") or ""
        if item.get("is_dir") and os.path.isdir(path):
            self.navigateRequested.emit(path)
        elif os.path.isfile(path):
            self.navigateRequested.emit(os.path.dirname(path))

    def _onOpenInActivePanel(self):
        path = self._selectedPath()
        if path:
            self.navigateRequested.emit(path)

    def _onOpenInPanel(self, side):
        path = self._selectedPath()
        if path:
            self.navigateInPanelRequested.emit(path, side)
