"""
Total Commander Clone - Library Dialogs
Small dialogs for registering library roots and assigning tags.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox, QCompleter, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

from library_manager import parseTagCategory


# ------------------------------------------------------------
# Class: LibraryRootDialog
# Purpose: Create a new library root or attach a folder to an
#          existing library using a small, focused dialog.
# ------------------------------------------------------------
class LibraryRootDialog(QDialog):

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, existing_libraries, initial_root_path="", initial_library_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add To Library")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._library_name = QComboBox()
        self._library_name.setEditable(True)
        self._library_name.addItems(existing_libraries)
        if initial_library_name:
            self._library_name.setEditText(initial_library_name)
        form.addRow("Library:", self._library_name)

        self._root_name = QLineEdit()
        form.addRow("Root name:", self._root_name)

        root_row = QHBoxLayout()
        self._root_path = QLineEdit(initial_root_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browseForRoot)
        root_row.addWidget(self._root_path, 1)
        root_row.addWidget(browse_btn)
        form.addRow("Root folder:", root_row)

        hint = QLabel("Choose the folder that should act as the portable library root.")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    # --------------------------------------------------------
    # Method: values
    # --------------------------------------------------------
    def values(self):
        return {
            "library_name": self._library_name.currentText().strip(),
            "root_name": self._root_name.text().strip(),
            "root_path": self._root_path.text().strip(),
        }

    # --------------------------------------------------------
    # Method: _browseForRoot
    # --------------------------------------------------------
    def _browseForRoot(self):
        start_dir = self._root_path.text().strip() or ""
        chosen = QFileDialog.getExistingDirectory(self, "Select library root", start_dir)
        if chosen:
            self._root_path.setText(chosen)


# ------------------------------------------------------------
# Class: TagAssignmentDialog
# Purpose: Capture folder tags and an optional note using a
#          lightweight metadata editor. Shows known categories
#          and existing tags as autocomplete suggestions.
# ------------------------------------------------------------
class TagAssignmentDialog(QDialog):

    # --------------------------------------------------------
    # Method: __init__
    # Input: folder_path (str), existing_tags (list), existing_note (str),
    #        known_tags (list) - all tags already used across libraries
    # --------------------------------------------------------
    def __init__(self, folder_path, existing_tags=None, existing_note="",
                 known_tags=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign Tags")
        self.setMinimumWidth(520)

        existing_tags = existing_tags or []
        known_tags = known_tags or []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        path_label = QLabel(folder_path)
        path_label.setWordWrap(True)
        form.addRow("Folder:", path_label)

        self._tags_edit = QLineEdit(", ".join(existing_tags))
        self._tags_edit.setPlaceholderText("Example: customer:Acme, industry:Hatchery")

        if known_tags:
            completer = QCompleter(known_tags, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self._tags_edit.setCompleter(completer)

        form.addRow("Tags:", self._tags_edit)

        self._note_edit = QLineEdit(existing_note or "")
        self._note_edit.setPlaceholderText("Optional note")
        form.addRow("Note:", self._note_edit)

        categories = set()
        for tag in known_tags:
            cat, _ = parseTagCategory(tag)
            if cat:
                categories.add(cat)

        if categories:
            cat_list = ", ".join(sorted(categories))
            hint_text = (
                f"Comma-separated tags. Known categories: {cat_list}\n"
                "Format: category:value (e.g. customer:Acme) or plain tags."
            )
        else:
            hint_text = (
                "Use comma-separated tags. "
                "Example groups: customer:Name, industry:Hatchery, status:Open"
            )
        hint = QLabel(hint_text)
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    # --------------------------------------------------------
    # Method: values
    # --------------------------------------------------------
    def values(self):
        raw_tags = self._tags_edit.text().split(",")
        tags = [tag.strip() for tag in raw_tags if tag.strip()]
        return {
            "tags": tags,
            "note": self._note_edit.text().strip(),
        }
