"""Offscreen smoke tests for themed dialogs."""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialogButtonBox


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeSettings:
    def __init__(self):
        self._data = {
            "theme_mode": "dark",
            "font_size": 10,
            "ui_scale": 100,
            "show_hidden_files": False,
            "confirm_delete": True,
            "check_for_updates_on_startup": True,
            "cache_recursive_scans": True,
            "default_left_path": "",
            "default_right_path": "",
            "mirror_mode": "to_other",
        }

    def getSetting(self, key, default=None):
        return self._data.get(key, default)

    def getSavedFileFilters(self):
        return []


class DialogSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _app()

    def test_settings_dialog_accessible_theme(self):
        from settings_dialog import SettingsDialog

        dlg = SettingsDialog(_FakeSettings())
        self.assertTrue(dlg._theme_mode.accessibleName())
        scroll = dlg.findChild(type(dlg), "dialogScrollArea")
        from PyQt5.QtWidgets import QScrollArea

        self.assertIsNotNone(dlg.findChild(QScrollArea, "dialogScrollArea"))
        self.assertEqual(
            dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).objectName(),
            "accentButton",
        )
        dlg.close()

    def test_filter_dialog_disables_spinners(self):
        from file_panel import FilePanel
        from filter_options_dialog import FilterOptionsDialog

        panel = FilePanel("left")
        dlg = FilterOptionsDialog(panel, _FakeSettings())
        dlg._chk_size.setChecked(False)
        dlg._chk_date.setChecked(False)
        dlg._syncAdvancedEnabled()
        self.assertFalse(dlg._spin_min_mb.isEnabled())
        self.assertFalse(dlg._dt_after.isEnabled())
        dlg._chk_size.setChecked(True)
        dlg._syncAdvancedEnabled()
        self.assertTrue(dlg._spin_min_mb.isEnabled())
        self.assertTrue(dlg._filter_text.accessibleName())
        dlg.close()
        panel.close()

    def test_batch_rename_and_compare_construct(self):
        from batch_rename_dialog import BatchRenameDialog
        from compare_paths_dialog import ComparePathsDialog

        entries = [{"name": "a.txt", "is_dir": False}]
        with tempfile.TemporaryDirectory() as tmp:
            dlg = BatchRenameDialog(entries, tmp)
            dlg._find_edit.setText("a")
            dlg._replace_edit.setText("b")
            dlg._updatePreview()
            self.assertGreaterEqual(dlg._preview_table.rowCount(), 1)
            dlg.close()
        cmp_dlg = ComparePathsDialog("", "", parent=None)
        self.assertEqual(cmp_dlg._diff_label.objectName(), "compareDiffSummary")
        cmp_dlg.close()

    def test_small_dialogs_construct(self):
        from bookmark_dialogs import BookmarkEditDialog
        from library_dialogs import LibraryRootDialog, TagAssignmentDialog
        from git_credentials_dialog import GitCredentialsDialog
        from file_properties_dialog import FilePropertiesDialog
        from transfers_bar import TransfersBar

        BookmarkEditDialog().close()
        LibraryRootDialog([]).close()
        TagAssignmentDialog("C:\\tmp").close()
        git = GitCredentialsDialog("")
        self.assertTrue(git._pat.accessibleName())
        git.close()
        entry = {
            "name": "x.txt",
            "full_path": os.path.abspath(__file__),
            "is_dir": False,
            "size": 1,
            "modified": 0,
            "type": "Text",
        }
        FilePropertiesDialog(entry).close()
        bar = TransfersBar()
        bar.applyLayoutTier(__import__("ui_layout_policy", fromlist=["LayoutTier"]).LayoutTier.CRITICAL)
        bar.close()


if __name__ == "__main__":
    unittest.main()
