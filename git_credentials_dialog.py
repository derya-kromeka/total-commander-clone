"""
GitHub credentials dialog for publishing a local version.
Collects remote URL, username, and PAT; optionally saves to .git-account.*.
"""

from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
)

from app_updater import PUBLIC_REPO_HTTPS, getRemoteUrl
from config_backup import loadGitAccountProfile, saveGitAccountCredentials
from ui_helpers import (
    accentButtonFromBox,
    configureDialog,
    errorLabel,
    hintLabel,
    setAccessible,
)


# ------------------------------------------------------------
# Class: GitCredentialsDialog
# Purpose: Prompt for GitHub HTTPS URL, username, and PAT.
# ------------------------------------------------------------
class GitCredentialsDialog(QDialog):
    def __init__(self, repo_root, parent=None, message=""):
        super().__init__(parent)
        self._repo_root = repo_root or ""
        configureDialog(self, "GitHub credentials", min_h=280)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(hintLabel(
            message
            or (
                "Enter GitHub credentials to push. "
                "Use a Personal Access Token (PAT), not your account password."
            )
        ))

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
            "GitHub personal access token used instead of a password.",
        )

        self._save = QCheckBox("Save credentials on this PC (.git-account.*)", self)
        self._save.setChecked(True)
        self._save.setAccessibleDescription(
            "Stores username, remote URL, and token in .git-account files in the project folder."
        )
        form.addRow("", self._save)

        layout.addLayout(form)
        self._error = errorLabel("", self)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttons.accepted.connect(self._onAccept)
        buttons.rejected.connect(self.reject)
        accentButtonFromBox(buttons, QDialogButtonBox.Ok)
        layout.addWidget(buttons)

    def _onTogglePatVisible(self, visible):
        self._pat.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._btn_show_pat.setText("Hide" if visible else "Show")

    # --------------------------------------------------------
    # Method: _onAccept
    # Purpose: Validate fields; optionally persist credentials.
    # --------------------------------------------------------
    def _onAccept(self):
        username = self._username.text().strip()
        pat = self._pat.text().strip()
        if not username:
            self._error.setText("Username is required.")
            self._error.setVisible(True)
            self._username.setFocus()
            return
        if not pat:
            self._error.setText("Personal Access Token is required.")
            self._error.setVisible(True)
            self._pat.setFocus()
            return
        self._error.setVisible(False)
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
