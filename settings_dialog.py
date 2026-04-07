"""
Settings dialog: theme, font, file display, delete confirmation, default pane paths.
Based on patterns from https://github.com/denizko-gh/total-commander-clone-1 (fork).
"""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QSpinBox,
)


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self._settings = settings_manager
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 340)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._theme_mode = QComboBox(self)
        self._theme_mode.addItem("Dark", "dark")
        self._theme_mode.addItem("Light", "light")
        self._theme_mode.addItem("Same as system", "system")
        current_theme = self._settings.getSetting("theme_mode", "dark")
        self._theme_mode.setCurrentIndex(max(0, self._theme_mode.findData(current_theme)))
        form.addRow("Theme", self._theme_mode)

        self._font_size = QSpinBox(self)
        self._font_size.setRange(8, 24)
        self._font_size.setValue(int(self._settings.getSetting("font_size", 10)))
        form.addRow("Font size", self._font_size)

        self._show_hidden = QCheckBox("Show hidden files", self)
        self._show_hidden.setChecked(self._settings.getSetting("show_hidden_files", False))
        form.addRow("Files", self._show_hidden)

        self._confirm_delete = QCheckBox("Ask before deleting files", self)
        self._confirm_delete.setChecked(self._settings.getSetting("confirm_delete", True))
        form.addRow("Delete", self._confirm_delete)

        self._default_left_path = QLineEdit(
            self._settings.getSetting("default_left_path", ""), self
        )
        form.addRow("Default left path", self._default_left_path)

        self._default_right_path = QLineEdit(
            self._settings.getSetting("default_right_path", ""), self
        )
        form.addRow("Default right path", self._default_right_path)

        self._mirror_mode = QComboBox(self)
        self._mirror_mode.addItem(
            "Inactive panel follows active (open active’s folder in the other pane)",
            "to_other",
        )
        self._mirror_mode.addItem(
            "Active panel follows inactive (open inactive’s folder in the active pane)",
            "to_active",
        )
        cur_mirror = self._settings.getSetting("mirror_mode", "to_other")
        self._mirror_mode.setCurrentIndex(
            max(0, self._mirror_mode.findData(cur_mirror))
        )
        form.addRow("Mirror (Ctrl+Shift+M)", self._mirror_mode)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {
            "theme_mode": self._theme_mode.currentData(),
            "font_size": self._font_size.value(),
            "show_hidden_files": self._show_hidden.isChecked(),
            "confirm_delete": self._confirm_delete.isChecked(),
            "default_left_path": self._default_left_path.text().strip(),
            "default_right_path": self._default_right_path.text().strip(),
            "mirror_mode": self._mirror_mode.currentData(),
        }
