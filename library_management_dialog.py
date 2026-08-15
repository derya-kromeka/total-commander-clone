"""
Library Manager dialog: create/rename/delete libraries, configure
roots, locate offline volumes, and start incremental or rebuild scans.
"""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from library_catalog import ROOT_STATUS_VERIFY
from ui_helpers import configureDialog, hintLabel, setAccessible


ROLE_KIND = Qt.UserRole
ROLE_LIBRARY_ID = Qt.UserRole + 1
ROLE_ROOT_ID = Qt.UserRole + 2


# ------------------------------------------------------------
# Class: RootSettingsDialog
# ------------------------------------------------------------
class RootSettingsDialog(QDialog):

    def __init__(self, root, parent=None):
        super().__init__(parent)
        configureDialog(self, "Root indexing rules", min_w=480)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name = QLineEdit(root.get("name", ""))
        form.addRow("Name:", self._name)

        self._files = QCheckBox("Index files")
        self._files.setChecked(root.get("include_files", True))
        self._folders = QCheckBox("Index folders")
        self._folders.setChecked(root.get("include_folders", True))
        self._hidden = QCheckBox("Include hidden items")
        self._hidden.setChecked(root.get("include_hidden", False))
        form.addRow("Contents:", self._files)
        form.addRow("", self._folders)
        form.addRow("", self._hidden)

        self._include = QPlainTextEdit("\n".join(root.get("include_globs") or []))
        self._include.setPlaceholderText("Optional include globs, one per line. Empty = all.")
        form.addRow("Include:", self._include)
        self._exclude = QPlainTextEdit("\n".join(root.get("exclude_globs") or []))
        self._exclude.setPlaceholderText("Exclude globs, one per line. Example: *.tmp")
        form.addRow("Exclude:", self._exclude)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addLayout(form)
        layout.addWidget(hintLabel("Include/exclude use filename glob patterns such as *.pdf or drafts/*."))
        layout.addWidget(buttons)

    def values(self):
        def lines(widget):
            return [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]
        return {
            "name": self._name.text().strip(),
            "include_files": self._files.isChecked(),
            "include_folders": self._folders.isChecked(),
            "include_hidden": self._hidden.isChecked(),
            "include_globs": lines(self._include),
            "exclude_globs": lines(self._exclude),
        }


# ------------------------------------------------------------
# Class: LibraryManagementDialog
# ------------------------------------------------------------
class LibraryManagementDialog(QDialog):

    checkRequested = pyqtSignal(str)
    rebuildRequested = pyqtSignal(str)
    locateRequested = pyqtSignal(str)
    addRootRequested = pyqtSignal(str)

    def __init__(self, library_manager, parent=None):
        super().__init__(parent)
        self._manager = library_manager
        configureDialog(self, "Library Manager", min_w=720, min_h=480, wide=True)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemSelectionChanged.connect(self._onSelectionChanged)
        left_layout.addWidget(self._tree, 1)
        lib_btns = QHBoxLayout()
        self._btn_new = QPushButton("New library")
        self._btn_rename = QPushButton("Rename")
        self._btn_delete = QPushButton("Delete")
        self._btn_new.clicked.connect(self._onNewLibrary)
        self._btn_rename.clicked.connect(self._onRename)
        self._btn_delete.clicked.connect(self._onDelete)
        lib_btns.addWidget(self._btn_new)
        lib_btns.addWidget(self._btn_rename)
        lib_btns.addWidget(self._btn_delete)
        left_layout.addLayout(lib_btns)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._detail = QLabel("Select a library or root.")
        self._detail.setWordWrap(True)
        right_layout.addWidget(self._detail)
        root_btns = QHBoxLayout()
        self._btn_add_root = QPushButton("Add root")
        self._btn_locate = QPushButton("Locate...")
        self._btn_check = QPushButton("Check changes")
        self._btn_rebuild = QPushButton("Rebuild index")
        self._btn_configure = QPushButton("Indexing rules...")
        self._btn_remove_root = QPushButton("Remove root")
        self._btn_add_root.clicked.connect(self._onAddRoot)
        self._btn_locate.clicked.connect(self._onLocate)
        self._btn_check.clicked.connect(self._onCheck)
        self._btn_rebuild.clicked.connect(self._onRebuild)
        self._btn_configure.clicked.connect(self._onConfigure)
        self._btn_remove_root.clicked.connect(self._onRemoveRoot)
        for btn in (
            self._btn_add_root, self._btn_locate, self._btn_check,
            self._btn_rebuild, self._btn_configure, self._btn_remove_root,
        ):
            root_btns.addWidget(btn)
        right_layout.addLayout(root_btns)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setSizes([280, 440])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

        self.reload()

    def reload(self):
        selected = self._selectedIds()
        self._tree.clear()
        for library in self._manager.getLibraries():
            item = QTreeWidgetItem([library.get("name", "Library")])
            item.setData(0, ROLE_KIND, "library")
            item.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
            item.setExpanded(True)
            self._tree.addTopLevelItem(item)
            for root in library.get("roots", []):
                suffix = self._rootSuffix(root)
                child = QTreeWidgetItem([f"{root.get('name', 'Root')}{suffix}"])
                child.setData(0, ROLE_KIND, "root")
                child.setData(0, ROLE_LIBRARY_ID, library.get("id", ""))
                child.setData(0, ROLE_ROOT_ID, root.get("id", ""))
                child.setToolTip(0, root.get("path", "") or "(no path)")
                item.addChild(child)
                if selected.get("root_id") == root.get("id"):
                    self._tree.setCurrentItem(child)
            if selected.get("library_id") == library.get("id") and not selected.get("root_id"):
                self._tree.setCurrentItem(item)
        self._onSelectionChanged()

    def _rootSuffix(self, root):
        status = root.get("status") or ""
        if not root.get("is_available"):
            return " [offline]"
        if status == ROOT_STATUS_VERIFY:
            return " [verify]"
        if status == "indexing":
            return " [indexing]"
        return ""

    def _selectedIds(self):
        items = self._tree.selectedItems()
        if not items:
            return {}
        item = items[0]
        return {
            "kind": item.data(0, ROLE_KIND),
            "library_id": item.data(0, ROLE_LIBRARY_ID) or "",
            "root_id": item.data(0, ROLE_ROOT_ID) or "",
        }

    def _selectedRoot(self):
        ids = self._selectedIds()
        if not ids.get("root_id"):
            return None
        library = self._manager.getLibrary(ids["library_id"])
        if library is None:
            return None
        for root in library.get("roots", []):
            if root.get("id") == ids["root_id"]:
                return root
        return None

    def _onSelectionChanged(self):
        ids = self._selectedIds()
        root = self._selectedRoot()
        has_root = root is not None
        has_library = bool(ids.get("library_id"))
        self._btn_add_root.setEnabled(has_library)
        self._btn_locate.setEnabled(has_root)
        self._btn_check.setEnabled(has_root)
        self._btn_rebuild.setEnabled(has_root)
        self._btn_configure.setEnabled(has_root)
        self._btn_remove_root.setEnabled(has_root)
        if root is not None:
            path = root.get("path") or root.get("last_seen_path") or "(unknown)"
            self._detail.setText(
                f"Root: {root.get('name')}\n"
                f"Path: {path}\n"
                f"Status: {root.get('status')}\n"
                f"Items: {root.get('item_count', 0)}  "
                f"Added: {root.get('added_count', 0)}  "
                f"Changed: {root.get('changed_count', 0)}  "
                f"Missing: {root.get('missing_count', 0)}\n"
                f"Last scan: {root.get('last_scan_at') or 'never'}\n"
                f"{root.get('last_error') or ''}"
            )
        elif has_library:
            library = self._manager.getLibrary(ids["library_id"])
            count = len((library or {}).get("roots") or [])
            self._detail.setText(
                f"Library: {(library or {}).get('name', '')}\n{count} root(s)."
            )
        else:
            self._detail.setText("Select a library or root.")

    def _onNewLibrary(self):
        name, ok = QInputDialog.getText(self, "New library", "Library name:")
        if not ok or not name.strip():
            return
        self._manager.createLibrary(name.strip())
        self.reload()

    def _onRename(self):
        ids = self._selectedIds()
        if ids.get("kind") == "root":
            root = self._selectedRoot()
            if root is None:
                return
            name, ok = QInputDialog.getText(self, "Rename root", "Root name:", text=root.get("name", ""))
            if ok and name.strip():
                self._manager.updateRootSettings(root["id"], name=name.strip())
                self.reload()
            return
        if not ids.get("library_id"):
            return
        library = self._manager.getLibrary(ids["library_id"])
        name, ok = QInputDialog.getText(
            self, "Rename library", "Library name:", text=(library or {}).get("name", "")
        )
        if ok and name.strip():
            self._manager.renameLibrary(ids["library_id"], name.strip())
            self.reload()

    def _onDelete(self):
        ids = self._selectedIds()
        if ids.get("kind") == "root":
            self._onRemoveRoot()
            return
        if not ids.get("library_id"):
            return
        if QMessageBox.question(
            self, "Delete library",
            "Delete this library, its roots, and indexed metadata?",
        ) != QMessageBox.Yes:
            return
        self._manager.deleteLibrary(ids["library_id"])
        self.reload()

    def _onAddRoot(self):
        ids = self._selectedIds()
        if ids.get("library_id"):
            self.addRootRequested.emit(ids["library_id"])

    def _onRemoveRoot(self):
        root = self._selectedRoot()
        if root is None:
            return
        if QMessageBox.question(
            self, "Remove root",
            "Remove this root from the library? Indexed files for this root are deleted from the catalog.",
        ) != QMessageBox.Yes:
            return
        self._manager.deleteRoot(root["id"])
        self.reload()

    def _onLocate(self):
        root = self._selectedRoot()
        if root is None:
            return
        self.locateRequested.emit(root["id"])

    def _onCheck(self):
        root = self._selectedRoot()
        if root is None:
            return
        self.checkRequested.emit(root["id"])

    def _onRebuild(self):
        root = self._selectedRoot()
        if root is None:
            return
        self.rebuildRequested.emit(root["id"])

    def _onConfigure(self):
        root = self._selectedRoot()
        if root is None:
            return
        dialog = RootSettingsDialog(root, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        self._manager.updateRootSettings(root["id"], **dialog.values())
        self.reload()
