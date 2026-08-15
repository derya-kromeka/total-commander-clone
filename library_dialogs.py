"""
Total Commander Clone - Library Dialogs
Register library roots and assign typed catalog properties.
"""

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from library_catalog import (
    ALL_FIELD_TYPES,
    FIELD_NOTES,
    FIELD_TAGS,
    FIELD_TYPE_BOOLEAN,
    FIELD_TYPE_CHOICE,
    FIELD_TYPE_DATE,
    FIELD_TYPE_MULTI,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_TEXT,
)
from library_manager import parseTagCategory
from ui_helpers import configureDialog, hintLabel, selectablePathLabel, setAccessible


SCOPE_SELECTED = "selected"
SCOPE_FOLDER = "folder"
SCOPE_FOLDER_FILES = "folder_files"
SCOPE_DESCENDANTS = "descendants"


# ------------------------------------------------------------
# Class: LibraryRootDialog
# Purpose: Create a new library root or attach a folder to an
#          existing library using a small, focused dialog.
# ------------------------------------------------------------
class LibraryRootDialog(QDialog):

    def __init__(self, existing_libraries, initial_root_path="", initial_library_name="", parent=None):
        super().__init__(parent)
        configureDialog(self, "Add To Library", min_w=480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._library_name = QComboBox()
        self._library_name.setEditable(True)
        self._library_name.addItems(existing_libraries)
        if initial_library_name:
            self._library_name.setEditText(initial_library_name)
        form.addRow("Library:", self._library_name)
        setAccessible(self._library_name, "Library name", "Existing library or a new name.")

        self._root_name = QLineEdit()
        form.addRow("Root name:", self._root_name)

        root_row = QHBoxLayout()
        self._root_path = QLineEdit(initial_root_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.setToolTip("Choose the folder that should become a library root.")
        browse_btn.clicked.connect(self._browseForRoot)
        root_row.addWidget(self._root_path, 1)
        root_row.addWidget(browse_btn)
        form.addRow("Root folder:", root_row)

        hint = hintLabel("This folder becomes the portable library root. Indexing starts after you add it.")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def values(self):
        return {
            "library_name": self._library_name.currentText().strip(),
            "root_name": self._root_name.text().strip(),
            "root_path": self._root_path.text().strip(),
        }

    def _browseForRoot(self):
        start_dir = self._root_path.text().strip() or ""
        chosen = QFileDialog.getExistingDirectory(self, "Select library root", start_dir)
        if chosen:
            self._root_path.setText(chosen)


# ------------------------------------------------------------
# Class: FieldDefinitionDialog
# Purpose: Create a reusable typed property.
# ------------------------------------------------------------
class FieldDefinitionDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        configureDialog(self, "New Property", min_w=420, min_h=280)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name = QLineEdit()
        form.addRow("Name:", self._name)

        self._type = QComboBox()
        labels = {
            FIELD_TYPE_TEXT: "Text",
            FIELD_TYPE_NUMBER: "Number",
            FIELD_TYPE_DATE: "Date",
            FIELD_TYPE_BOOLEAN: "Yes / No",
            FIELD_TYPE_CHOICE: "Single choice",
            FIELD_TYPE_MULTI: "Multiple choice",
        }
        for key in (FIELD_TYPE_TEXT, FIELD_TYPE_NUMBER, FIELD_TYPE_DATE, FIELD_TYPE_BOOLEAN, FIELD_TYPE_CHOICE, FIELD_TYPE_MULTI):
            self._type.addItem(labels[key], key)
        form.addRow("Type:", self._type)

        self._options = QPlainTextEdit()
        self._options.setPlaceholderText("One option per line (choice fields)")
        form.addRow("Options:", self._options)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self):
        options = [line.strip() for line in self._options.toPlainText().splitlines() if line.strip()]
        return {
            "name": self._name.text().strip(),
            "type": self._type.currentData(),
            "options": options,
        }


# ------------------------------------------------------------
# Class: PropertyAssignmentDialog
# Purpose: Edit tags, notes, and custom fields for files/folders.
# ------------------------------------------------------------
class PropertyAssignmentDialog(QDialog):

    def __init__(
        self,
        paths,
        fields,
        current_values=None,
        known_tags=None,
        allow_scope=True,
        parent=None,
    ):
        super().__init__(parent)
        configureDialog(self, "Assign Properties", min_w=560, min_h=420, wide=True)
        self._paths = list(paths or [])
        self._fields = list(fields or [])
        self._current_values = current_values or {}
        self._editors = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        if len(self._paths) == 1:
            form.addRow("Item:", selectablePathLabel(self._paths[0]))
        else:
            form.addRow("Items:", QLabel(f"{len(self._paths)} selected"))

        self._scope = QComboBox()
        self._scope.addItem("Selected items", SCOPE_SELECTED)
        self._scope.addItem("This folder only", SCOPE_FOLDER)
        self._scope.addItem("Files in this folder", SCOPE_FOLDER_FILES)
        self._scope.addItem("All descendants", SCOPE_DESCENDANTS)
        self._scope.setEnabled(bool(allow_scope))
        form.addRow("Apply to:", self._scope)

        self._inherit = QCheckBox("Also inherit to future items in this folder")
        form.addRow("", self._inherit)

        layout.addLayout(form)

        for field in self._fields:
            editor = self._makeEditor(field, self._current_values.get(field["id"], []))
            self._editors[field["id"]] = editor
            form.addRow(field.get("name", "Field") + ":", editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._manage_btn = buttons.addButton("Manage fields...", QDialogButtonBox.ActionRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(hintLabel(
            "Tags and custom fields are shared across libraries. "
            "Inherited rules apply to items added later under this folder."
        ))
        layout.addWidget(buttons)
        self.manageFieldsRequested = False
        self._manage_btn.clicked.connect(self._onManageFields)

    def _onManageFields(self):
        self.manageFieldsRequested = True
        self.accept()

    def _makeEditor(self, field, values):
        field_type = field.get("type")
        values = values or []
        if field["id"] == FIELD_TAGS or field_type == FIELD_TYPE_MULTI:
            editor = QLineEdit(", ".join(values))
            editor.setPlaceholderText("Comma-separated values")
            if field["id"] == FIELD_TAGS:
                editor.setPlaceholderText("Example: customer:Acme, industry:Hatchery")
            return editor
        if field_type == FIELD_TYPE_BOOLEAN:
            editor = QCheckBox("Yes")
            editor.setChecked(values[:1] == ["1"])
            return editor
        if field_type == FIELD_TYPE_NUMBER:
            editor = QLineEdit(values[0] if values else "")
            editor.setPlaceholderText("Number")
            return editor
        if field_type == FIELD_TYPE_DATE:
            editor = QDateEdit()
            editor.setCalendarPopup(True)
            if values:
                parsed = QDate.fromString(values[0], "yyyy-MM-dd")
                if parsed.isValid():
                    editor.setDate(parsed)
                else:
                    editor.setDate(QDate.currentDate())
            else:
                editor.setDate(QDate.currentDate())
            editor.setSpecialValueText(" ")
            return editor
        if field_type == FIELD_TYPE_CHOICE:
            editor = QComboBox()
            editor.setEditable(True)
            editor.addItem("")
            for option in field.get("options") or []:
                editor.addItem(option)
            if values:
                editor.setEditText(values[0])
            return editor
        editor = QLineEdit(values[0] if values else "")
        if field["id"] == FIELD_NOTES:
            editor.setPlaceholderText("Optional note")
        return editor

    def values(self):
        assigned = {}
        for field in self._fields:
            editor = self._editors.get(field["id"])
            field_type = field.get("type")
            if editor is None:
                continue
            if field["id"] == FIELD_TAGS or field_type == FIELD_TYPE_MULTI:
                raw = editor.text().split(",")
                assigned[field["id"]] = [item.strip() for item in raw if item.strip()]
            elif field_type == FIELD_TYPE_BOOLEAN:
                assigned[field["id"]] = ["1" if editor.isChecked() else "0"]
            elif field_type == FIELD_TYPE_DATE:
                assigned[field["id"]] = [editor.date().toString("yyyy-MM-dd")]
            elif field_type == FIELD_TYPE_CHOICE:
                text = editor.currentText().strip()
                assigned[field["id"]] = [text] if text else []
            else:
                text = editor.text().strip()
                assigned[field["id"]] = [text] if text else []
        return {
            "values": assigned,
            "scope": self._scope.currentData() or SCOPE_SELECTED,
            "inherit": self._inherit.isChecked(),
            "manage_fields": self.manageFieldsRequested,
        }


# Backward-compatible alias used by older smoke tests.
class TagAssignmentDialog(PropertyAssignmentDialog):

    def __init__(self, folder_path, existing_tags=None, existing_note="", known_tags=None, parent=None):
        fields = [
            {"id": FIELD_TAGS, "name": "Tags", "type": FIELD_TYPE_MULTI, "options": known_tags or []},
            {"id": FIELD_NOTES, "name": "Notes", "type": FIELD_TYPE_TEXT, "options": []},
        ]
        current = {
            FIELD_TAGS: existing_tags or [],
            FIELD_NOTES: [existing_note] if existing_note else [],
        }
        super().__init__(
            [folder_path],
            fields,
            current_values=current,
            known_tags=known_tags,
            allow_scope=False,
            parent=parent,
        )

    def values(self):
        data = super().values()
        assigned = data.get("values") or {}
        tags = assigned.get(FIELD_TAGS, [])
        notes = assigned.get(FIELD_NOTES, [])
        return {
            "tags": tags,
            "note": notes[0] if notes else "",
        }
