"""
Total Commander Clone - Libraries Panel
Sidebar for library roots, online/offline status, and locate/check actions.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)
from ui_layout_policy import LayoutTier, tierAtMost


ROLE_ITEM_TYPE = Qt.UserRole
ROLE_LIBRARY_ID = Qt.UserRole + 1
ROLE_PATH = Qt.UserRole + 2
ROLE_ROOT_ID = Qt.UserRole + 3


# ------------------------------------------------------------
# Class: LibrariesPanel
# Purpose: Present libraries and roots without duplicating search.
# ------------------------------------------------------------
class LibrariesPanel(QWidget):

    navigateRequested = pyqtSignal(str)
    addLibraryRequested = pyqtSignal()
    scanLibrariesRequested = pyqtSignal()
    manageLibrariesRequested = pyqtSignal()
    locateRootRequested = pyqtSignal(str)
    checkRootRequested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._libraries = []
        self._selected_library_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Libraries")
        title.setObjectName("sidebarPanelTitle")
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._btn_manage = QPushButton("Manage")
        self._btn_manage.setObjectName("bookmarksToolButton")
        self._btn_manage.clicked.connect(self.manageLibrariesRequested.emit)
        self._btn_add = QPushButton("Add root")
        self._btn_add.setObjectName("bookmarksToolButton")
        self._btn_add.setToolTip("Register the active panel’s folder as a library root.")
        self._btn_add.clicked.connect(self.addLibraryRequested.emit)
        self._btn_scan = QPushButton("Check")
        self._btn_scan.setObjectName("bookmarksToolButton")
        self._btn_scan.setToolTip("Check online roots for filesystem changes.")
        self._btn_scan.clicked.connect(self.scanLibrariesRequested.emit)
        btn_row.addWidget(self._btn_manage)
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_scan)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setChildrenCollapsible(False)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemClicked.connect(self._onTreeItemClicked)
        self._tree.itemDoubleClicked.connect(self._onTreeItemDoubleClicked)
        self._splitter.addWidget(self._tree)

        self._status = QLabel("Select a root to locate or check it.")
        self._status.setWordWrap(True)
        self._status.setObjectName("sidebarSectionTitle")
        self._splitter.addWidget(self._status)

        locate_row = QHBoxLayout()
        self._btn_locate = QPushButton("Locate")
        self._btn_locate.setObjectName("bookmarksToolButton")
        self._btn_locate.clicked.connect(self._onLocate)
        self._btn_check = QPushButton("Check this")
        self._btn_check.setObjectName("bookmarksToolButton")
        self._btn_check.clicked.connect(self._onCheckThis)
        locate_row.addWidget(self._btn_locate)
        locate_row.addWidget(self._btn_check)
        wrap = QWidget()
        wrap.setLayout(locate_row)
        self._splitter.addWidget(wrap)

        self._splitter.setSizes([260, 80, 40])
        layout.addWidget(self._splitter, 1)
        self._selected_root_id = ""

    def splitterSizes(self):
        return self._splitter.sizes()

    def applySplitterSizes(self, sizes):
        if isinstance(sizes, (list, tuple)) and len(sizes) >= 3:
            self._splitter.setSizes([int(s) for s in sizes[:3]])

    def applyLayoutTier(self, tier):
        compact = tierAtMost(tier, LayoutTier.NARROW)
        self._btn_add.setText("Add" if compact else "Add root")

    def setData(self, libraries, tagged_folders=None, selected_library_id=""):
        del tagged_folders
        self._libraries = libraries or []
        available_ids = {lib.get("id", "") for lib in self._libraries}
        self._selected_library_id = selected_library_id if selected_library_id in available_ids else ""
        self._rebuildTree()

    def selectedLibraryId(self):
        return self._selected_library_id

    def selectedRootId(self):
        return self._selected_root_id

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
                suffix = self._statusSuffix(root)
                root_item = QTreeWidgetItem([f"{root.get('name', 'Root')}{suffix}"])
                root_item.setData(0, ROLE_ITEM_TYPE, "root")
                root_item.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
                root_item.setData(0, ROLE_PATH, root.get("path", ""))
                root_item.setData(0, ROLE_ROOT_ID, root.get("id", ""))
                root_item.setToolTip(0, root.get("path", "") or "Offline — use Locate")
                library_item.addChild(root_item)
        if not self._selected_library_id and self._libraries:
            self._selected_library_id = self._libraries[0].get("id", "")

    def _statusSuffix(self, root):
        status = root.get("status") or ""
        if not root.get("is_available"):
            return " [offline]"
        if status == "verification_needed":
            return " [verify]"
        if status == "indexing":
            return " [indexing]"
        count = int(root.get("item_count") or 0)
        return f" ({count})" if count else ""

    def _onTreeItemClicked(self, item, column):
        del column
        self._selected_library_id = item.data(0, ROLE_LIBRARY_ID) or ""
        if item.data(0, ROLE_ITEM_TYPE) == "root":
            self._selected_root_id = item.data(0, ROLE_ROOT_ID) or ""
            path = item.data(0, ROLE_PATH) or ""
            self._status.setText(path or "This root is offline. Use Locate to point it at the folder.")
        else:
            self._selected_root_id = ""
            self._status.setText("Select a root to locate or check it.")

    def _onTreeItemDoubleClicked(self, item, column):
        del column
        if item.data(0, ROLE_ITEM_TYPE) != "root":
            return
        path = item.data(0, ROLE_PATH) or ""
        if path:
            self.navigateRequested.emit(path)
        else:
            root_id = item.data(0, ROLE_ROOT_ID) or ""
            if root_id:
                self.locateRootRequested.emit(root_id)

    def _onLocate(self):
        if self._selected_root_id:
            self.locateRootRequested.emit(self._selected_root_id)

    def _onCheckThis(self):
        if self._selected_root_id:
            self.checkRootRequested.emit(self._selected_root_id)
        else:
            self.scanLibrariesRequested.emit()
