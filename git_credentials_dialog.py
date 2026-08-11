"""
GitHub credentials dialog for publishing a local version.
Collects remote URL, username, and PAT; optionally saves to .git-account.*.
"""

from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app_updater import PUBLIC_REPO_HTTPS, getRemoteUrl
from config_backup import loadGitAccountProfile, saveGitAccountCredentials


# ------------------------------------------------------------
# Class: GitCredentialsDialog
# Purpose: Prompt for GitHub HTTPS URL, username, and PAT.
# ------------------------------------------------------------
class GitCredentialsDialog(QDialog):
    def __init__(self, repo_root, parent=None, message=""):
        super().__init__(parent)
        self._repo_root = repo_root or ""
        self.setWindowTitle("GitHub credentials")
        self.setModal(True)
        self.resize(520, 280)

        layout = QVBoxLayout(self)
        hint = QLabel(
            message
            or (
                "Enter GitHub credentials to push. "
                "Use a Personal Access Token (PAT), not your account password."
            ),
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        profile = loadGitAccountProfile(self._repo_root) or {}
        default_url = (profile.get("remoteUrl") or "").strip() or getRemoteUrl(
            self._repo_root
        )
        default_user = (profile.get("githubUsername") or "").strip()

        self._remote_url = QLineEdit(self)
        self._remote_url.setText(default_url or PUBLIC_REPO_HTTPS)
        self._remote_url.setPlaceholderText(PUBLIC_REPO_HTTPS)
        form.addRow("Remote URL", self._remote_url)

        self._username = QLineEdit(self)
        self._username.setText(default_user)
        self._username.setPlaceholderText("GitHub username")
        form.addRow("Username", self._username)

        self._pat = QLineEdit(self)
        self._pat.setEchoMode(QLineEdit.Password)
        self._pat.setPlaceholderText("Personal Access Token (PAT)")
        form.addRow("PAT", self._pat)

        self._save = QCheckBox("Save credentials on this PC (.git-account.*)", self)
        self._save.setChecked(True)
        form.addRow("", self._save)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttons.accepted.connect(self._onAccept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --------------------------------------------------------
    # Method: _onAccept
    # Purpose: Validate fields; optionally persist credentials.
    # --------------------------------------------------------
    def _onAccept(self):
        username = self._username.text().strip()
        pat = self._pat.text().strip()
        if not username:
            self._username.setFocus()
            return
        if not pat:
            self._pat.setFocus()
            return
        if self._save.isChecked() and self._repo_root:
            ok, err = saveGitAccountCredentials(
                self._repo_root,
                username=username,
                remote_url=self._remote_url.text().strip(),
                pat=pat,
            )
            if not ok:
                # Still allow one-shot use; keep dialog open only on hard failure
                # to empty username/pat which we already checked.
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Save credentials",
                    err or "Could not save credentials. Continuing without save.",
                )
        self.accept()

    # --------------------------------------------------------
    # Method: authDict
    # Purpose: Values for publishLocalVersionToGitHub(auth=…).
    # --------------------------------------------------------
    def authDict(self):
        return {
            "username": self._username.text().strip(),
            "pat": self._pat.text().strip(),
            "remote_url": self._remote_url.text().strip(),
        }
