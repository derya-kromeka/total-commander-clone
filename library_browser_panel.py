"""
Total Commander Clone - Library Browser Panel
Full panel-sized library browser that can replace a file panel,
providing tag-based navigation with category grouping.
"""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from library_manager import parseTagCategory


ROLE_PATH = Qt.UserRole + 1
ROLE_TAGS = Qt.UserRole + 2


# ------------------------------------------------------------
# Class: LibraryBrowserPanel
# Purpose: A full panel-sized library browser with a library
#          selector, categorized tag tree, folder results list,
#          and action buttons for opening folders in file panels.
# ------------------------------------------------------------
class LibraryBrowserPanel(QWidget):

    navigateRequested = pyqtSignal(str)
    navigateInPanelRequested = pyqtSignal(str, str)
    switchToFilePanelRequested = pyqtSignal()
    addLibraryRequested = pyqtSignal()
    scanLibrariesRequested = pyqtSignal()
    assignTagsRequested = pyqtSignal()

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, side="left", parent=None):
        super().__init__(parent)
        self._side = side
        self._libraries = []
        self._tagged_folders = []
        self._selected_library_id = ""

        self._initUI()

    # --------------------------------------------------------
    # Method: _initUI
    # Purpose: Build the full panel layout with header, tag
    #          browser, results list, and action bar.
    # --------------------------------------------------------
    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = self._buildHeader()
        layout.addLayout(header)

        content_splitter = QSplitter(Qt.Vertical)

        self._tag_tree = QTreeWidget()
        self._tag_tree.setHeaderHidden(True)
        self._tag_tree.setSelectionMode(QAbstractItemView.MultiSelection)
        self._tag_tree.itemSelectionChanged.connect(self._onTagSelectionChanged)
        content_splitter.addWidget(self._tag_tree)

        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(2)

        self._results_label = QLabel("Matching folders (0)")
        self._results_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        results_layout.addWidget(self._results_label)

        self._results_list = QListWidget()
        self._results_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._results_list.itemDoubleClicked.connect(self._onResultDoubleClicked)
        results_layout.addWidget(self._results_list, 1)

        content_splitter.addWidget(results_container)
        content_splitter.setSizes([200, 300])

        layout.addWidget(content_splitter, 1)

        action_bar = self._buildActionBar()
        layout.addLayout(action_bar)

    # --------------------------------------------------------
    # Method: _buildHeader
    # Purpose: Library selector dropdown, action buttons, and
    #          a toggle to switch back to the file panel.
    # --------------------------------------------------------
    def _buildHeader(self):
        header = QVBoxLayout()
        header.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        title = QLabel("\U0001F4DA Library Browser")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        title_row.addWidget(title)

        title_row.addStretch()

        self._btn_switch = QPushButton("\U0001F4C2 File Panel")
        self._btn_switch.setObjectName("libraryToolButton")
        self._btn_switch.setToolTip(
            "File panel\n\nReturn this side to the normal folder browser."
        )
        self._btn_switch.clicked.connect(self.switchToFilePanelRequested.emit)
        title_row.addWidget(self._btn_switch)

        header.addLayout(title_row)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(4)

        selector_label = QLabel("Library:")
        selector_row.addWidget(selector_label)

        self._library_combo = QComboBox()
        self._library_combo.setMinimumWidth(120)
        self._library_combo.setToolTip(
            "Library\n\nChoose which library’s tags and folders to browse."
        )
        self._library_combo.currentIndexChanged.connect(self._onLibraryChanged)
        selector_row.addWidget(self._library_combo, 1)

        self._btn_add_root = QPushButton("Add Root")
        self._btn_add_root.setObjectName("libraryToolButton")
        self._btn_add_root.setToolTip(
            "Add root\n\n"
            "Register the active panel’s folder as a root for the selected library."
        )
        self._btn_add_root.clicked.connect(self.addLibraryRequested.emit)
        selector_row.addWidget(self._btn_add_root)

        self._btn_scan = QPushButton("Scan")
        self._btn_scan.setObjectName("libraryToolButton")
        self._btn_scan.setToolTip(
            "Scan\n\nRescan indexed folders for the selected library."
        )
        self._btn_scan.clicked.connect(self.scanLibrariesRequested.emit)
        selector_row.addWidget(self._btn_scan)

        self._btn_assign_tags = QPushButton("Assign Tags")
        self._btn_assign_tags.setObjectName("libraryToolButton")
        self._btn_assign_tags.setToolTip(
            "Assign tags\n\nSet tags on folders for the selected library."
        )
        self._btn_assign_tags.clicked.connect(self.assignTagsRequested.emit)
        selector_row.addWidget(self._btn_assign_tags)

        header.addLayout(selector_row)

        tag_label = QLabel("Tags (select to filter)")
        tag_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 4px;")
        header.addWidget(tag_label)

        return header

    # --------------------------------------------------------
    # Method: _buildActionBar
    # Purpose: Bottom row of buttons for opening selected
    #          folders in various panels.
    # --------------------------------------------------------
    def _buildActionBar(self):
        bar = QHBoxLayout()
        bar.setSpacing(4)

        self._btn_open_active = QPushButton("Open in Active Panel")
        self._btn_open_active.setObjectName("libraryToolButton")
        self._btn_open_active.setToolTip(
            "Open in active panel\n\nNavigate the focused file panel to the selected folder."
        )
        self._btn_open_active.clicked.connect(self._onOpenInActivePanel)
        bar.addWidget(self._btn_open_active, 1)

        self._btn_open_left = QPushButton("Open in Left")
        self._btn_open_left.setObjectName("libraryToolButton")
        self._btn_open_left.setToolTip(
            "Open in left\n\nOpen the selected folder in the left file panel."
        )
        self._btn_open_left.clicked.connect(lambda: self._onOpenInPanel("left"))
        bar.addWidget(self._btn_open_left)

        self._btn_open_right = QPushButton("Open in Right")
        self._btn_open_right.setObjectName("libraryToolButton")
        self._btn_open_right.setToolTip(
            "Open in right\n\nOpen the selected folder in the right file panel."
        )
        self._btn_open_right.clicked.connect(lambda: self._onOpenInPanel("right"))
        bar.addWidget(self._btn_open_right)

        return bar

    # --------------------------------------------------------
    # Method: setData
    # Purpose: Populate the panel with library and tag data.
    # --------------------------------------------------------
    def setData(self, libraries, tagged_folders, selected_library_id=""):
        self._libraries = libraries or []
        self._tagged_folders = tagged_folders or []

        available_ids = {lib.get("id", "") for lib in self._libraries}
        self._selected_library_id = (
            selected_library_id if selected_library_id in available_ids else ""
        )

        self._rebuildLibraryCombo()
        self._rebuildTagTree()
        self._rebuildResults()

    # --------------------------------------------------------
    # Method: selectedLibraryId
    # --------------------------------------------------------
    def selectedLibraryId(self):
        return self._selected_library_id

    # --------------------------------------------------------
    # Method: _rebuildLibraryCombo
    # Purpose: Populate the library dropdown with available
    #          libraries and an "(All Libraries)" option.
    # --------------------------------------------------------
    def _rebuildLibraryCombo(self):
        self._library_combo.blockSignals(True)
        self._library_combo.clear()

        self._library_combo.addItem("(All Libraries)", "")

        target_index = 0
        for i, lib in enumerate(self._libraries):
            lib_id = lib.get("id", "")
            root_count = len(lib.get("roots", []))
            self._library_combo.addItem(
                f"{lib.get('name', 'Library')} ({root_count} roots)", lib_id
            )
            if lib_id == self._selected_library_id:
                target_index = i + 1

        self._library_combo.setCurrentIndex(target_index)
        self._library_combo.blockSignals(False)

    # --------------------------------------------------------
    # Method: _rebuildTagTree
    # Purpose: Group all tags by category in a collapsible
    #          tree. Tags without a colon go under "(Other)".
    # --------------------------------------------------------
    def _rebuildTagTree(self):
        previously_selected = self._getSelectedTagStrings()
        self._tag_tree.blockSignals(True)
        self._tag_tree.clear()

        raw_tags = self._collectTagsForLibrary(self._selected_library_id)

        categories = {}
        for tag in raw_tags:
            category, value = parseTagCategory(tag)
            display_category = category if category else "(Other)"
            categories.setdefault(display_category, []).append((tag, value))

        for cat_name in sorted(categories.keys(), key=lambda s: (s == "(Other)", s.lower())):
            cat_item = QTreeWidgetItem([cat_name])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            cat_item.setExpanded(True)
            self._tag_tree.addTopLevelItem(cat_item)

            for full_tag, display_value in sorted(categories[cat_name], key=lambda t: t[1].lower()):
                tag_item = QTreeWidgetItem([display_value])
                tag_item.setData(0, ROLE_TAGS, full_tag)
                tag_item.setToolTip(0, full_tag)
                cat_item.addChild(tag_item)

                if full_tag in previously_selected:
                    tag_item.setSelected(True)

        self._tag_tree.blockSignals(False)

    # --------------------------------------------------------
    # Method: _rebuildResults
    # Purpose: Filter tagged folders by selected library and
    #          tags, then display in the results list.
    # --------------------------------------------------------
    def _rebuildResults(self):
        selected_tags = {t.lower() for t in self._getSelectedTagStrings()}
        self._results_list.clear()

        visible_count = 0
        for folder in self._tagged_folders:
            if self._selected_library_id and folder.get("library_id") != self._selected_library_id:
                continue

            folder_tags = {t.lower() for t in folder.get("tags", [])}
            if selected_tags and not selected_tags.issubset(folder_tags):
                continue

            display = folder.get("display_name", "Folder")
            rel = folder.get("relative_path", "")
            lib_name = folder.get("library_name", "")
            tags_str = ", ".join(folder.get("tags", []))

            label_parts = [display]
            if rel:
                label_parts.append(f"  [{rel}]")
            if lib_name and not self._selected_library_id:
                label_parts.append(f"  ({lib_name})")

            item = QListWidgetItem("".join(label_parts))
            item.setData(ROLE_PATH, folder.get("resolved_path", ""))
            item.setData(ROLE_TAGS, tags_str)

            tooltip = folder.get("resolved_path", "")
            if tags_str:
                tooltip += f"\nTags: {tags_str}"
            if not folder.get("is_available"):
                item.setText(item.text() + "  [offline]")
                tooltip += "\n(OFFLINE)"
            item.setToolTip(tooltip)

            self._results_list.addItem(item)
            visible_count += 1

        self._results_label.setText(f"Matching folders ({visible_count})")

    # --------------------------------------------------------
    # Method: _collectTagsForLibrary
    # Purpose: Gather unique tags from tagged folders that
    #          belong to the given library (or all if empty).
    # --------------------------------------------------------
    def _collectTagsForLibrary(self, library_id):
        tags = set()
        for folder in self._tagged_folders:
            if library_id and folder.get("library_id") != library_id:
                continue
            for tag in folder.get("tags", []):
                if tag:
                    tags.add(tag)
        return sorted(tags, key=lambda v: v.lower())

    # --------------------------------------------------------
    # Method: _getSelectedTagStrings
    # Purpose: Return full tag strings from selected tree items.
    # --------------------------------------------------------
    def _getSelectedTagStrings(self):
        tags = set()
        for item in self._tag_tree.selectedItems():
            full_tag = item.data(0, ROLE_TAGS)
            if full_tag:
                tags.add(full_tag)
        return tags

    # --------------------------------------------------------
    # Method: _selectedResultPath
    # --------------------------------------------------------
    def _selectedResultPath(self):
        items = self._results_list.selectedItems()
        if not items:
            return ""
        return items[0].data(ROLE_PATH) or ""

    # --------------------------------------------------------
    # Slots
    # --------------------------------------------------------
    def _onLibraryChanged(self, index):
        lib_id = self._library_combo.itemData(index) or ""
        self._selected_library_id = lib_id
        self._rebuildTagTree()
        self._rebuildResults()

    def _onTagSelectionChanged(self):
        self._rebuildResults()

    def _onResultDoubleClicked(self, item):
        path = item.data(ROLE_PATH) or ""
        if path and os.path.isdir(path):
            self.navigateRequested.emit(path)

    def _onOpenInActivePanel(self):
        path = self._selectedResultPath()
        if path and os.path.isdir(path):
            self.navigateRequested.emit(path)

    def _onOpenInPanel(self, side):
        path = self._selectedResultPath()
        if path and os.path.isdir(path):
            self.navigateInPanelRequested.emit(path, side)
