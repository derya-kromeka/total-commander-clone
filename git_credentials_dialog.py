"""
Git settings dialog: remote URL, username, optional PAT, commit identity.
Used from Help → Git settings and when publishing needs credentials.
"""

import os
import shutil

from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from app_updater import PUBLIC_REPO_HTTPS, getRemoteUrl
from config_backup import (
    clearSavedGitPat,
    gitPatIsSaved,
    loadGitAccountProfile,
    saveGitAccountCredentials,
    testGitRemoteAccess,
)
from ui_helpers import (
    accentButtonFromBox,
    configureDialog,
    errorLabel,
    hintLabel,
    setAccessible,
)


# ------------------------------------------------------------
# Class: GitCredentialsDialog
# Purpose: Configure Git remote URL, username, PAT, and commit identity.
# ------------------------------------------------------------
class GitCredentialsDialog(QDialog):
    def __init__(
        self,
        repo_root,
        parent=None,
        message="",
        require_pat=False,
        settings_mode=False,
    ):
        super().__init__(parent)
        self._repo_root = repo_root or ""
        self._require_pat = bool(require_pat)
        self._settings_mode = bool(settings_mode)
        title = "Git settings" if self._settings_mode else "GitHub credentials"
        configureDialog(self, title, min_h=360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(hintLabel(
            message
            or (
                "Set the Git remote URL, GitHub username, and optional Personal "
                "Access Token (PAT). Public remotes can pull without a PAT. "
                "Pushing to GitHub needs a PAT, not your account password."
            )
        ))

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        profile = loadGitAccountProfile(self._repo_root) or {}
        default_url = (profile.get("remoteUrl") or "").strip() or getRemoteUrl(
            self._repo_root
        )
        default_user = (profile.get("githubUsername") or "").strip()
        default_name = (profile.get("commitName") or "").strip()
        default_email = (profile.get("commitEmail") or "").strip()

        url_row = QHBoxLayout()
        self._remote_url = QLineEdit(self)
        self._remote_url.setText(default_url or PUBLIC_REPO_HTTPS)
        self._remote_url.setPlaceholderText(PUBLIC_REPO_HTTPS)
        url_row.addWidget(self._remote_url, 1)
        self._btn_public = QToolButton(self)
        self._btn_public.setText("Public")
        self._btn_public.setToolTip("Fill the public Total Commander Clone repository URL.")
        self._btn_public.clicked.connect(self._onUsePublicRepo)
        url_row.addWidget(self._btn_public)
        form.addRow("Remote URL", url_row)
        setAccessible(
            self._remote_url,
            "Remote URL",
            "HTTPS Git remote, for example https://github.com/owner/repo.git",
        )

        self._username = QLineEdit(self)
        self._username.setText(default_user)
        self._username.setPlaceholderText("GitHub username")
        form.addRow("Username", self._username)

        self._pat = QLineEdit(self)
        self._pat.setEchoMode(QLineEdit.Password)
        self._pat.setPlaceholderText(
            "Personal Access Token (required to push)"
            if self._require_pat
            else "Personal Access Token (optional for public pull)"
        )
        pat_row = QHBoxLayout()
        pat_row.addWidget(self._pat, 1)
        self._btn_show_pat = QToolButton(self)
        self._btn_show_pat.setCheckable(True)
        self._btn_show_pat.setText("Show")
        self._btn_show_pat.setToolTip("Show or hide the personal access token.")
        self._btn_show_pat.toggled.connect(self._onTogglePatVisible)
        pat_row.addWidget(self._btn_show_pat)
        form.addRow("PAT", pat_row)
        setAccessible(
            self._pat,
            "Personal Access Token",
            "GitHub personal access token used instead of a password. "
            "Required to push; optional for public remotes.",
        )

        self._commit_name = QLineEdit(self)
        self._commit_name.setText(default_name)
        self._commit_name.setPlaceholderText("Name on git commits (optional)")
        form.addRow("Commit name", self._commit_name)

        self._commit_email = QLineEdit(self)
        self._commit_email.setText(default_email)
        self._commit_email.setPlaceholderText("email@example.com (optional)")
        form.addRow("Commit email", self._commit_email)

        self._save = QCheckBox("Save credentials on this PC (.git-account.*)", self)
        self._save.setChecked(True)
        self._save.setAccessibleDescription(
            "Stores username, remote URL, and token in .git-account files in the project folder."
        )
        form.addRow("", self._save)

        layout.addLayout(form)

        status = []
        if shutil.which("git"):
            status.append("Git is installed.")
        else:
            status.append("Git is not on PATH — install Git to pull or push.")
        if self._repo_root:
            if os.path.isdir(os.path.join(self._repo_root, ".git")):
                status.append("This folder is a Git checkout.")
            else:
                status.append("No .git folder — clone or copy the full repository to push.")
            if gitPatIsSaved(self._repo_root):
                status.append("A PAT is already saved on this PC.")
        layout.addWidget(hintLabel(" ".join(status), self))

        action_row = QHBoxLayout()
        self._btn_test = QPushButton("Test connection", self)
        self._btn_test.setToolTip("Run git ls-remote against the URL (uses PAT if entered or saved).")
        self._btn_test.clicked.connect(self._onTestConnection)
        action_row.addWidget(self._btn_test)
        self._btn_clear_pat = QPushButton("Remove saved PAT", self)
        self._btn_clear_pat.setEnabled(gitPatIsSaved(self._repo_root))
        self._btn_clear_pat.clicked.connect(self._onClearPat)
        action_row.addWidget(self._btn_clear_pat)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self._error = errorLabel("", self)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttons.accepted.connect(self._onAccept)
        buttons.rejected.connect(self.reject)
        accentButtonFromBox(buttons, QDialogButtonBox.Ok)
        layout.addWidget(buttons)

    def _onUsePublicRepo(self):
        self._remote_url.setText(PUBLIC_REPO_HTTPS)

    def _onTogglePatVisible(self, visible):
        self._pat.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._btn_show_pat.setText("Hide" if visible else "Show")

    def _onClearPat(self):
        if not self._repo_root:
            return
        ok, err = clearSavedGitPat(self._repo_root)
        if ok:
            self._btn_clear_pat.setEnabled(False)
            self._pat.clear()
            QMessageBox.information(self, "Git settings", err or "Removed saved PAT.")
        else:
            QMessageBox.warning(self, "Git settings", err or "Could not remove PAT.")

    def _onTestConnection(self):
        auth = None
        username = self._username.text().strip()
        pat = self._pat.text().strip()
        if username and pat:
            auth = {"username": username, "pat": pat}
        ok, msg = testGitRemoteAccess(
            self._repo_root,
            url=self._remote_url.text().strip(),
            auth=auth,
        )
        if ok:
            QMessageBox.information(self, "Test connection", msg)
        else:
            QMessageBox.warning(
                self,
                "Test connection",
                msg or "Could not reach the remote. Check the URL and PAT.",
            )

    # --------------------------------------------------------
    # Method: _onAccept
    # Purpose: Validate fields; persist credentials and apply to git.
    # --------------------------------------------------------
    def _onAccept(self):
        username = self._username.text().strip()
        pat = self._pat.text().strip()
        url = self._remote_url.text().strip()
        if self._require_pat:
            if not username:
                self._error.setText("Username is required to push.")
                self._error.setVisible(True)
                self._username.setFocus()
                return
            if not pat and not gitPatIsSaved(self._repo_root):
                self._error.setText("Personal Access Token is required to push.")
                self._error.setVisible(True)
                self._pat.setFocus()
                return
        if pat and not username:
            self._error.setText("Username is required when saving a PAT.")
            self._error.setVisible(True)
            self._username.setFocus()
            return
        if self._settings_mode and not url:
            self._error.setText("Remote URL is required.")
            self._error.setVisible(True)
            self._remote_url.setFocus()
            return
        self._error.setVisible(False)
        if self._save.isChecked() and self._repo_root:
            ok, err = saveGitAccountCredentials(
                self._repo_root,
                username=username,
                remote_url=url,
                pat=pat,
                commit_name=self._commit_name.text().strip(),
                commit_email=self._commit_email.text().strip(),
                apply_to_repo=True,
            )
            if not ok:
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
            "commit_name": self._commit_name.text().strip(),
            "commit_email": self._commit_email.text().strip(),
        }
