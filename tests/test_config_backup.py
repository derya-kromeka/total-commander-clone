"""
Regression tests: local settings backups never touch Git.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import config_backup


# ------------------------------------------------------------
# Class: TestConfigBackup
# Purpose: Prove backups write under a temp user-data directory,
#          keep the expected JSON files, and never invoke Git.
# ------------------------------------------------------------
class TestConfigBackup(unittest.TestCase):

    EXPECTED_FILES = (
        "settings.json",
        "bookmarks.json",
        "libraries.json",
        "state.json",
        "backup_manifest.json",
    )

    SAMPLE_SETTINGS = {
        "theme_mode": "dark",
        "font_size": 11,
        "show_hidden_files": False,
    }

    SAMPLE_STATE = {
        "bookmarks": [{"name": "Home", "path": "C:\\Users\\Test"}],
        "libraries": [{"name": "Docs", "roots": ["C:\\Docs"]}],
        "folder_tags": {"C:\\Docs": ["work"]},
        "saved_library_filters": [{"name": "pdf"}],
        "saved_file_filters": [{"name": "images"}],
        "sidebar_state": {"current_tab": "bookmarks"},
        "recent_paths": ["C:\\Users\\Test"],
        "left_panel": {"current_path": "C:\\Users\\Test"},
        "right_panel": {"current_path": "C:\\Docs"},
    }

    # --------------------------------------------------------
    # Method: setUp
    # Purpose: Isolate each test in a temporary user-data folder.
    # --------------------------------------------------------
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.user_data_dir = self._tmp.name
        self.host = "TEST-HOST"

    def tearDown(self):
        self._tmp.cleanup()

    def _writeBackup(self):
        with mock.patch.object(config_backup, "getComputerName", return_value=self.host):
            return config_backup.writeConfigBackup(
                self.SAMPLE_SETTINGS,
                self.SAMPLE_STATE,
                user_data_dir=self.user_data_dir,
            )

    # --------------------------------------------------------
    # Method: test_getUserDataDir_uses_appdata
    # Purpose: Backups resolve beneath APPDATA on Windows-style env.
    # --------------------------------------------------------
    def test_getUserDataDir_uses_appdata(self):
        fake_appdata = os.path.join(self.user_data_dir, "AppData")
        os.makedirs(fake_appdata, exist_ok=True)
        with mock.patch.object(config_backup.os, "name", "nt"):
            with mock.patch.dict(os.environ, {"APPDATA": fake_appdata}, clear=False):
                path = config_backup.getUserDataDir()
        self.assertEqual(
            path,
            os.path.join(fake_appdata, config_backup.APP_DATA_DIRNAME),
        )
        self.assertTrue(path.startswith(fake_appdata))

    # --------------------------------------------------------
    # Method: test_backup_path_is_under_user_data
    # Purpose: Per-PC folder is <user-data>/backups/<host>/.
    # --------------------------------------------------------
    def test_backup_path_is_under_user_data(self):
        backup_dir = self._writeBackup()
        self.assertIsNotNone(backup_dir)
        expected = os.path.join(self.user_data_dir, "backups", self.host)
        self.assertEqual(os.path.normpath(backup_dir), os.path.normpath(expected))
        self.assertTrue(os.path.isdir(backup_dir))

    # --------------------------------------------------------
    # Method: test_backup_writes_expected_json_files
    # Purpose: Latest backup contains the five JSON files.
    # --------------------------------------------------------
    def test_backup_writes_expected_json_files(self):
        backup_dir = self._writeBackup()
        names = sorted(
            name for name in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, name))
        )
        self.assertEqual(names, sorted(self.EXPECTED_FILES))

        with open(os.path.join(backup_dir, "settings.json"), encoding="utf-8") as f:
            settings = json.load(f)
        self.assertEqual(settings["theme_mode"], "dark")
        self.assertEqual(settings["font_size"], 11)

        with open(os.path.join(backup_dir, "bookmarks.json"), encoding="utf-8") as f:
            bookmarks = json.load(f)
        self.assertEqual(bookmarks["bookmarks"][0]["name"], "Home")

        with open(os.path.join(backup_dir, "libraries.json"), encoding="utf-8") as f:
            libraries = json.load(f)
        self.assertEqual(libraries["libraries"][0]["name"], "Docs")

        with open(os.path.join(backup_dir, "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["left_panel"]["current_path"], "C:\\Users\\Test")

        with open(os.path.join(backup_dir, "backup_manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["computer_name"], self.host)
        self.assertEqual(sorted(manifest["files"]), sorted(self.EXPECTED_FILES[:-1]))

    # --------------------------------------------------------
    # Method: test_backupConfig_never_invokes_git
    # Purpose: backupConfig writes files without running git.
    # --------------------------------------------------------
    def test_backupConfig_never_invokes_git(self):
        with mock.patch.object(config_backup, "getComputerName", return_value=self.host):
            with mock.patch.object(config_backup.subprocess, "run") as git_run:
                result = config_backup.backupConfig(
                    self.SAMPLE_SETTINGS,
                    self.SAMPLE_STATE,
                    user_data_dir=self.user_data_dir,
                )
        self.assertTrue(os.path.isdir(result))
        git_run.assert_not_called()

    # --------------------------------------------------------
    # Method: test_git_upload_helpers_are_removed
    # Purpose: Automatic commit/push helpers no longer exist.
    # --------------------------------------------------------
    def test_git_upload_helpers_are_removed(self):
        for name in (
            "uploadBackupToGit",
            "scheduleBackupGitUpload",
            "backupConfigAndUpload",
            "_runGitPush",
        ):
            self.assertFalse(
                hasattr(config_backup, name),
                f"{name} should not exist (settings backups must not upload to Git)",
            )

    # --------------------------------------------------------
    # Method: test_publish_git_helpers_still_exist
    # Purpose: Explicit Publish Version still has credential/push APIs.
    # --------------------------------------------------------
    def test_publish_git_helpers_still_exist(self):
        self.assertTrue(callable(config_backup.runGitPushWithAuth))
        self.assertTrue(callable(config_backup.loadGitAccountProfile))
        self.assertTrue(callable(config_backup.saveGitAccountCredentials))
        self.assertTrue(callable(config_backup.findGitRepoRoot))


if __name__ == "__main__":
    unittest.main()
