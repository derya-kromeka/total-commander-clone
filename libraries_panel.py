"""
Total Commander Clone - Libraries Panel
Sidebar UI for library roots, tags, and tagged folder results.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)


ROLE_ITEM_TYPE = Qt.UserRole
ROLE_LIBRARY_ID = Qt.UserRole + 1
ROLE_PATH = Qt.UserRole + 2
ROLE_TAGS = Qt.UserRole + 3


# ------------------------------------------------------------
# Class: LibrariesPanel
# Purpose: Present libraries, tag filters, and virtual results
#          without disturbing the main two-pane workflow.
# ------------------------------------------------------------
class LibrariesPanel(QWidget):

    navigateRequested = pyqtSignal(str)
    addLibraryRequested = pyqtSignal()
    scanLibrariesRequested = pyqtSignal()

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self._libraries = []
        self._tagged_folders = []
        self._selected_library_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Libraries")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._btn_add = QPushButton("Add root")
        self._btn_add.setObjectName("bookmarksToolButton")
        self._btn_add.setToolTip(
            "Add library root\n\n"
            "Register the active panel’s folder as a library root for tagging and search."
        )
        self._btn_add.clicked.connect(self.addLibraryRequested.emit)
        self._btn_scan = QPushButton("Scan")
        self._btn_scan.setObjectName("bookmarksToolButton")
        self._btn_scan.setToolTip(
            "Scan libraries\n\nRescan folders under all library roots."
        )
        self._btn_scan.clicked.connect(self.scanLibrariesRequested.emit)
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_scan)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemClicked.connect(self._onTreeItemClicked)
        self._tree.itemDoubleClicked.connect(self._onTreeItemDoubleClicked)
        layout.addWidget(self._tree, 1)

        self._tags_label = QLabel("Tags")
        layout.addWidget(self._tags_label)

        self._tags_list = QListWidget()
        self._tags_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._tags_list.itemSelectionChanged.connect(self._rebuildResults)
        layout.addWidget(self._tags_list, 1)

        self._results_label = QLabel("Matching folders")
        layout.addWidget(self._results_label)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._onResultDoubleClicked)
        layout.addWidget(self._results_list, 1)

    # --------------------------------------------------------
    # Method: setData
    # --------------------------------------------------------
    def setData(self, libraries, tagged_folders, selected_library_id=""):
        self._libraries = libraries or []
        self._tagged_folders = tagged_folders or []
        available_ids = {lib.get("id", "") for lib in self._libraries}
        self._selected_library_id = selected_library_id if selected_library_id in available_ids else ""
        self._rebuildTree()
        self._rebuildTags()
        self._rebuildResults()

    # --------------------------------------------------------
    # Method: selectedLibraryId
    # --------------------------------------------------------
    def selectedLibraryId(self):
        return self._selected_library_id

    # --------------------------------------------------------
    # Method: selectedTags
    # --------------------------------------------------------
    def selectedTags(self):
        return [item.text() for item in self._tags_list.selectedItems()]

    # --------------------------------------------------------
    # Method: _rebuildTree
    # --------------------------------------------------------
    def _rebuildTree(self):
        self._tree.clear()
        for library in self._libraries:
            root_count = len(library.get("roots", []))
            library_item = QTreeWidgetItem([f"{library.get('name', 'Library')} ({root_count})"])
            library_item.setData(0, ROLE_ITEM_TYPE, "library")
            library_item.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
            library_item.setExpanded(True)
            self._tree.addTopLevelItem(library_item)

            for root in library.get("roots", []):
                suffix = "" if root.get("is_available") else " [offline]"
                root_item = QTreeWidgetItem([f"{root.get('name', 'Root')}{suffix}"])
                root_item.setData(0, ROLE_ITEM_TYPE, "root")
                root_item.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
                root_item.setData(0, ROLE_PATH, root.get("path", ""))
                root_item.setToolTip(0, root.get("path", ""))
                library_item.addChild(root_item)

            library_tags = self._tagsForLibrary(library.get("id", ""))
            if library_tags:
                tags_group = QTreeWidgetItem(["Tags"])
                tags_group.setData(0, ROLE_ITEM_TYPE, "tag_group")
                tags_group.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
                library_item.addChild(tags_group)

                for tag in library_tags:
                    tag_item = QTreeWidgetItem([tag])
                    tag_item.setData(0, ROLE_ITEM_TYPE, "tag")
                    tag_item.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
                    tag_item.setData(0, ROLE_TAGS, [tag])
                    tags_group.addChild(tag_item)

        if not self._selected_library_id and self._libraries:
            self._selected_library_id = self._libraries[0].get("id", "")

    # --------------------------------------------------------
    # Method: _rebuildTags
    # --------------------------------------------------------
    def _rebuildTags(self):
        selected_before = set(self.selectedTags())
        self._tags_list.clear()
        for tag in self._tagsForLibrary(self._selected_library_id):
            item = QListWidgetItem(tag)
            self._tags_list.addItem(item)
            if tag in selected_before:
                item.setSelected(True)
        self._tags_label.setText(
            "Tags"
            if not self._selected_library_id
            else f"Tags ({self._libraryName(self._selected_library_id)})"
        )

    # --------------------------------------------------------
    # Method: _rebuildResults
    # --------------------------------------------------------
    def _rebuildResults(self):
        selected_tags = {tag.lower() for tag in self.selectedTags()}
        self._results_list.clear()

        visible_count = 0
        for item in self._tagged_folders:
            if self._selected_library_id and item.get("library_id") != self._selected_library_id:
                continue
            item_tags = {tag.lower() for tag in item.get("tags", [])}
            if selected_tags and not selected_tags.issubset(item_tags):
                continue

            label = item.get("display_name", "Folder")
            rel_path = item.get("relative_path", "")
            if rel_path:
                label = f"{label} - {rel_path}"
            if not item.get("is_available"):
                label = f"{label} [offline]"

            result_item = QListWidgetItem(label)
            result_item.setToolTip(item.get("resolved_path", ""))
            result_item.setData(ROLE_PATH, item.get("resolved_path", ""))
            self._results_list.addItem(result_item)
            visible_count += 1

        self._results_label.setText(f"Matching folders ({visible_count})")

    # --------------------------------------------------------
    # Method: _tagsForLibrary
    # --------------------------------------------------------
    def _tagsForLibrary(self, library_id):
        tags = set()
        for item in self._tagged_folders:
            if library_id and item.get("library_id") != library_id:
                continue
            for tag in item.get("tags", []):
                if tag:
                    tags.add(tag)
        return sorted(tags, key=lambda value: value.lower())

    # --------------------------------------------------------
    # Method: _libraryName
    # --------------------------------------------------------
    def _libraryName(self, library_id):
        for library in self._libraries:
            if library.get("id") == library_id:
                return library.get("name", "Library")
        return "Library"

    # --------------------------------------------------------
    # Method: _onTreeItemClicked
    # --------------------------------------------------------
    def _onTreeItemClicked(self, item, column):
        del column
        item_type = item.data(0, ROLE_ITEM_TYPE)
        library_id = item.data(0, ROLE_LIBRARY_ID) or ""

        if item_type in ("library", "root", "tag"):
            self._selected_library_id = library_id
            self._rebuildTags()
            if item_type == "tag":
                self._selectOnlyTag(item.text(0))
            self._rebuildResults()

    # --------------------------------------------------------
    # Method: _onTreeItemDoubleClicked
    # --------------------------------------------------------
    def _onTreeItemDoubleClicked(self, item, column):
        del column
        item_type = item.data(0, ROLE_ITEM_TYPE)
        if item_type != "root":
            return
        path = item.data(0, ROLE_PATH) or ""
        if path:
            self.navigateRequested.emit(path)

    # --------------------------------------------------------
    # Method: _onResultDoubleClicked
    # --------------------------------------------------------
    def _onResultDoubleClicked(self, item):
        path = item.data(ROLE_PATH) or ""
        if path:
            self.navigateRequested.emit(path)

    # --------------------------------------------------------
    # Method: _selectOnlyTag
    # --------------------------------------------------------
    def _selectOnlyTag(self, tag_name):
        self._tags_list.blockSignals(True)
        for index in range(self._tags_list.count()):
            item = self._tags_list.item(index)
            item.setSelected(item.text() == tag_name)
        self._tags_list.blockSignals(False)
