"""Unit tests for Git remote URL parsing and credential files."""

import os
import tempfile
import unittest

from config_backup import (
    _readPatFile,
    clearSavedGitPat,
    gitPatIsSaved,
    loadGitAccountProfile,
    loadSavedGitAuth,
    normalizeRemoteUrl,
    parseGitHubOwnerRepo,
    saveGitAccountCredentials,
)


class GitAccountTests(unittest.TestCase):
    def test_normalize_remote_url(self):
        self.assertEqual(
            normalizeRemoteUrl("owner/repo"),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(
            normalizeRemoteUrl("https://github.com/owner/repo"),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(
            normalizeRemoteUrl("git@github.com:owner/repo.git"),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(normalizeRemoteUrl(""), "")

    def test_parse_github_owner_repo(self):
        self.assertEqual(
            parseGitHubOwnerRepo("https://github.com/derya-kromeka/total-commander-clone.git"),
            ("derya-kromeka", "total-commander-clone"),
        )
        self.assertEqual(
            parseGitHubOwnerRepo("git@github.com:acme/app.git"),
            ("acme", "app"),
        )
        self.assertIsNone(parseGitHubOwnerRepo("https://example.com/not-github.git"))

    def test_save_profile_without_pat(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, msg = saveGitAccountCredentials(
                tmp,
                username="alice",
                remote_url="alice/my-fork",
                apply_to_repo=False,
            )
            self.assertTrue(ok, msg)
            profile = loadGitAccountProfile(tmp)
            self.assertEqual(profile.get("githubUsername"), "alice")
            self.assertEqual(
                profile.get("remoteUrl"),
                "https://github.com/alice/my-fork.git",
            )
            self.assertFalse(gitPatIsSaved(tmp))
            self.assertIsNone(loadSavedGitAuth(tmp))

    def test_plain_pat_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            pat_path = os.path.join(tmp, ".git-account.pat")
            with open(pat_path, "w", encoding="utf-8") as f:
                f.write("v1:ghp_test_token")
            self.assertEqual(_readPatFile(pat_path), "ghp_test_token")

    def test_save_and_load_pat(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, msg = saveGitAccountCredentials(
                tmp,
                username="bob",
                remote_url="https://github.com/bob/repo.git",
                pat="ghp_secret",
                commit_name="Bob",
                commit_email="bob@users.noreply.github.com",
                apply_to_repo=False,
            )
            self.assertTrue(ok, msg)
            self.assertTrue(gitPatIsSaved(tmp))
            auth = loadSavedGitAuth(tmp)
            self.assertIsNotNone(auth)
            self.assertEqual(auth["username"], "bob")
            self.assertEqual(auth["pat"], "ghp_secret")
            ok, _ = clearSavedGitPat(tmp)
            self.assertTrue(ok)
            self.assertFalse(gitPatIsSaved(tmp))
            self.assertIsNone(loadSavedGitAuth(tmp))

    def test_pat_requires_username(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, msg = saveGitAccountCredentials(
                tmp,
                username="",
                pat="ghp_secret",
                apply_to_repo=False,
            )
            self.assertFalse(ok)
            self.assertIn("username", msg.lower())


if __name__ == "__main__":
    unittest.main()
