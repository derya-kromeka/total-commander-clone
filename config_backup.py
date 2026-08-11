"""
Config backup: write latest settings/bookmarks/libraries under
backup/settings/<computer-name>/ and best-effort commit+push to git.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
BACKUP_ROOT_NAME = "backup"
BACKUP_SETTINGS_NAME = "settings"
MANIFEST_FILENAME = "backup_manifest.json"

# Debounce rapid saves (settings + state often write back-to-back).
_GIT_DEBOUNCE_SEC = 2.5
_git_timer_lock = threading.Lock()
_git_timer = None  # type: Optional[threading.Timer]


# ------------------------------------------------------------
# Function: sanitizeComputerName
# Purpose: Folder-safe hostname for backup/settings/<name>/.
# ------------------------------------------------------------
def sanitizeComputerName(name: str) -> str:
    raw = (name or "").strip() or "unknown-host"
    cleaned = re.sub(r"[^\w.\-]+", "_", raw, flags=re.UNICODE)
    cleaned = cleaned.strip("._") or "unknown-host"
    return cleaned[:80]


# ------------------------------------------------------------
# Function: getComputerName
# Purpose: Local machine name for per-PC backup folders.
# ------------------------------------------------------------
def getComputerName() -> str:
    for getter in (
        lambda: os.environ.get("COMPUTERNAME"),
        lambda: os.environ.get("HOSTNAME"),
        socket.gethostname,
    ):
        try:
            value = getter()
            if value and str(value).strip():
                return sanitizeComputerName(str(value))
        except Exception:
            continue
    return "unknown-host"


# ------------------------------------------------------------
# Function: findGitRepoRoot
# Purpose: Walk parents of start_path looking for a .git directory.
# ------------------------------------------------------------
def findGitRepoRoot(start_path: str) -> Optional[str]:
    if not start_path:
        return None
    cur = os.path.abspath(start_path)
    for _ in range(10):
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


# ------------------------------------------------------------
# Function: resolveBackupRepoRoot
# Purpose: Prefer an explicit project root, else walk from candidates.
# ------------------------------------------------------------
def resolveBackupRepoRoot(project_root: Optional[str] = None) -> Optional[str]:
    candidates = []
    if project_root:
        candidates.append(project_root)
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    if getattr(__import__("sys"), "frozen", False):
        import sys

        candidates.append(os.path.dirname(sys.executable))
    for start in candidates:
        root = findGitRepoRoot(start)
        if root:
            return root
    # Dev without .git yet: still write under project/source folder.
    if project_root and os.path.isdir(project_root):
        return os.path.abspath(project_root)
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(here):
        return here
    return None


# ------------------------------------------------------------
# Function: getComputerBackupDir
# Purpose: backup/settings/<computer-name>/ under the repo root.
# ------------------------------------------------------------
def getComputerBackupDir(repo_root: str, computer_name: Optional[str] = None) -> str:
    host = computer_name or getComputerName()
    return os.path.join(repo_root, BACKUP_ROOT_NAME, BACKUP_SETTINGS_NAME, host)


# ------------------------------------------------------------
# Function: _writeJson
# Purpose: Write pretty JSON; replace previous file in place (latest only).
# ------------------------------------------------------------
def _writeJson(path: str, data: Any) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


# ------------------------------------------------------------
# Function: writeConfigBackup
# Purpose: Write latest settings/bookmarks/libraries for this PC.
#          Overwrites previous files in the same computer folder.
# Output: Absolute backup directory path, or None on failure.
# ------------------------------------------------------------
def writeConfigBackup(
    settings: Dict[str, Any],
    state: Dict[str, Any],
    project_root: Optional[str] = None,
) -> Optional[str]:
    repo_root = resolveBackupRepoRoot(project_root)
    if not repo_root:
        return None

    host = getComputerName()
    backup_dir = getComputerBackupDir(repo_root, host)
    os.makedirs(backup_dir, exist_ok=True)

    # Keep only these latest files (overwrite; remove stray older copies).
    payload = {
        "settings.json": settings or {},
        "bookmarks.json": {
            "bookmarks": (state or {}).get("bookmarks", []),
        },
        "libraries.json": {
            "libraries": (state or {}).get("libraries", []),
            "folder_tags": (state or {}).get("folder_tags", {}),
            "saved_library_filters": (state or {}).get("saved_library_filters", []),
        },
        "state.json": {
            "bookmarks": (state or {}).get("bookmarks", []),
            "libraries": (state or {}).get("libraries", []),
            "folder_tags": (state or {}).get("folder_tags", {}),
            "saved_library_filters": (state or {}).get("saved_library_filters", []),
            "saved_file_filters": (state or {}).get("saved_file_filters", []),
            "sidebar_state": (state or {}).get("sidebar_state", {}),
            "recent_paths": (state or {}).get("recent_paths", []),
            "left_panel": (state or {}).get("left_panel", {}),
            "right_panel": (state or {}).get("right_panel", {}),
        },
    }

    for filename, data in payload.items():
        _writeJson(os.path.join(backup_dir, filename), data)

    manifest = {
        "computer_name": host,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "files": sorted(payload.keys()),
        "app_note": "Latest backup only for this computer; overwritten on each save.",
    }
    _writeJson(os.path.join(backup_dir, MANIFEST_FILENAME), manifest)

    # Remove unknown extras so the folder stays "latest only".
    keep = set(payload.keys()) | {MANIFEST_FILENAME}
    try:
        for name in os.listdir(backup_dir):
            if name in keep or name.endswith(".tmp"):
                continue
            path = os.path.join(backup_dir, name)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
    except OSError:
        pass

    return backup_dir


# ------------------------------------------------------------
# Function: _hiddenSubprocessKwargs
# Purpose: On Windows, hide console windows for git/powershell so the
#          GUI app does not flash cmd windows on every backup upload.
# ------------------------------------------------------------
def _hiddenSubprocessKwargs() -> Dict[str, Any]:
    if os.name != "nt":
        return {}
    # CREATE_NO_WINDOW (0x08000000) — available on Python 3.7+ as
    # subprocess.CREATE_NO_WINDOW; keep literal fallback for older builds.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    kwargs: Dict[str, Any] = {"creationflags": flags}
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    return kwargs


# ------------------------------------------------------------
# Function: _runGit
# Purpose: Run a git command in repo_root; return (ok, combined output).
# ------------------------------------------------------------
def _runGit(repo_root: str, args, timeout: int = 60):
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **_hiddenSubprocessKwargs(),
        )
        out = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, out.strip()
    except Exception as exc:
        return False, str(exc)


# ------------------------------------------------------------
# Function: _loadSavedGitAuth
# Purpose: Username + DPAPI-decrypted PAT from .git-account.* (Windows).
# ------------------------------------------------------------
def _loadSavedGitAuth(repo_root: str):
    profile_path = os.path.join(repo_root, ".git-account.json")
    pat_path = os.path.join(repo_root, ".git-account.pat")
    if not os.path.isfile(profile_path) or not os.path.isfile(pat_path):
        return None
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        username = (profile.get("githubUsername") or "").strip()
        if not username:
            return None
        if os.name != "nt":
            return None
        # Escape single quotes for PowerShell single-quoted path literal.
        pat_ps = pat_path.replace("'", "''")
        ps = (
            "$ErrorActionPreference='Stop';"
            f"$enc = Get-Content -LiteralPath '{pat_ps}' -Raw -Encoding UTF8;"
            "$sec = ConvertTo-SecureString -String $enc;"
            "$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec);"
            "try { [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }"
            "finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }"
        )
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            **_hiddenSubprocessKwargs(),
        )
        if completed.returncode != 0:
            return None
        pat = (completed.stdout or "").strip()
        if not pat:
            return None
        return {"username": username, "pat": pat}
    except Exception:
        return None


# ------------------------------------------------------------
# Function: loadGitAccountProfile
# Purpose: Read .git-account.json fields (no PAT decrypt).
# ------------------------------------------------------------
def loadGitAccountProfile(repo_root: str) -> Optional[Dict[str, Any]]:
    if not repo_root:
        return None
    profile_path = os.path.join(repo_root, ".git-account.json")
    if not os.path.isfile(profile_path):
        return None
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


# ------------------------------------------------------------
# Function: saveGitAccountCredentials
# Purpose: Save GitHub username/URL to .git-account.json and encrypt
#          PAT into .git-account.pat (Windows DPAPI via PowerShell).
# ------------------------------------------------------------
def saveGitAccountCredentials(
    repo_root: str,
    username: str,
    remote_url: str = "",
    pat: str = "",
    commit_name: str = "",
    commit_email: str = "",
) -> Tuple[bool, str]:
    if not repo_root or not os.path.isdir(repo_root):
        return False, "Invalid repository root."
    username = (username or "").strip()
    if not username:
        return False, "GitHub username is required."
    if os.name != "nt":
        return False, "Saving an encrypted PAT is only supported on Windows."

    existing = loadGitAccountProfile(repo_root) or {}
    profile = {
        "label": existing.get("label") or "default",
        "remoteUrl": (remote_url or "").strip() or (existing.get("remoteUrl") or ""),
        "commitName": (commit_name or "").strip() or (existing.get("commitName") or ""),
        "commitEmail": (commit_email or "").strip() or (existing.get("commitEmail") or ""),
        "githubUsername": username,
    }
    profile_path = os.path.join(repo_root, ".git-account.json")
    pat_path = os.path.join(repo_root, ".git-account.pat")
    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as exc:
        return False, f"Could not write .git-account.json: {exc}"

    pat = (pat or "").strip()
    if not pat:
        return True, "Saved profile (PAT unchanged)."

    import tempfile

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="tcc-pat-", suffix=".txt")
        os.close(fd)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(pat)
        tmp_ps = tmp_path.replace("'", "''")
        pat_ps = pat_path.replace("'", "''")
        ps = (
            "$ErrorActionPreference='Stop';"
            f"$plain = (Get-Content -LiteralPath '{tmp_ps}' -Raw -Encoding UTF8).Trim();"
            "if (-not $plain) { throw 'Empty PAT' };"
            "$secure = ConvertTo-SecureString -String $plain -AsPlainText -Force;"
            "$enc = ConvertFrom-SecureString -SecureString $secure;"
            f"Set-Content -LiteralPath '{pat_ps}' -Value $enc -Encoding UTF8 -NoNewline;"
        )
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            **_hiddenSubprocessKwargs(),
        )
        if completed.returncode != 0:
            err = (completed.stderr or completed.stdout or "encrypt failed").strip()
            return False, f"Could not encrypt PAT: {err[:300]}"
        return True, "Saved profile and encrypted PAT."
    except Exception as exc:
        return False, str(exc)
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ------------------------------------------------------------
# Function: _authExtraHeaderArgs
# Purpose: git -c http.extraHeader=AUTHORIZATION… args, or [].
# ------------------------------------------------------------
def _authExtraHeaderArgs(auth: Optional[Dict[str, Any]]):
    if not auth or not auth.get("pat"):
        return []
    import base64

    user = (auth.get("username") or "").strip()
    pat = (auth.get("pat") or "").strip()
    if not user or not pat:
        return []
    pair = f"{user}:{pat}"
    encoded = base64.b64encode(pair.encode("ascii")).decode("ascii")
    header = f"AUTHORIZATION: basic {encoded}"
    return ["-c", f"http.extraHeader={header}"]


# ------------------------------------------------------------
# Function: runGitPushWithAuth
# Purpose: Push HEAD with optional explicit auth; never force.
# Output: (ok, combined git output).
# ------------------------------------------------------------
def runGitPushWithAuth(
    repo_root: str,
    auth: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    push_args = ["push", "-u", "origin", "HEAD"]
    use_auth = auth if auth and auth.get("pat") else _loadSavedGitAuth(repo_root)
    header_args = _authExtraHeaderArgs(use_auth)
    if header_args:
        ok, out = _runGit(repo_root, [*header_args, *push_args], timeout=120)
        if ok:
            return True, out
        # Fall through to plain push only when no explicit auth was given.
        if auth and auth.get("pat"):
            return False, out
    return _runGit(repo_root, push_args, timeout=120)


# ------------------------------------------------------------
# Function: _runGitPush
# Purpose: Push HEAD; prefer saved PAT header, else plain git push.
# ------------------------------------------------------------
def _runGitPush(repo_root: str) -> bool:
    ok, _ = runGitPushWithAuth(repo_root)
    return ok


# ------------------------------------------------------------
# Function: uploadBackupToGit
# Purpose: Stage backup/settings/<host>/, commit if dirty, push origin.
#          Non-interactive; uses saved PAT or existing git credentials.
# ------------------------------------------------------------
def uploadBackupToGit(backup_dir: str, project_root: Optional[str] = None) -> bool:
    if not backup_dir or not os.path.isdir(backup_dir):
        return False
    repo_root = resolveBackupRepoRoot(project_root) or findGitRepoRoot(backup_dir)
    if not repo_root or not os.path.isdir(os.path.join(repo_root, ".git")):
        return False

    rel = os.path.relpath(backup_dir, repo_root).replace("\\", "/")
    host = os.path.basename(backup_dir.rstrip("\\/"))

    ok, _ = _runGit(repo_root, ["add", "--", rel])
    if not ok:
        return False

    ok, status = _runGit(repo_root, ["status", "--porcelain", "--", rel])
    if not ok:
        return False
    if not (status or "").strip():
        # Nothing new to commit; still try push in case a prior commit is unpushed.
        return _runGitPush(repo_root)

    msg = f"backup: settings for {host}"
    ok, _ = _runGit(repo_root, ["commit", "-m", msg])
    if not ok:
        return False

    return _runGitPush(repo_root)


# ------------------------------------------------------------
# Function: scheduleBackupGitUpload
# Purpose: Debounced background git upload after config backup writes.
# ------------------------------------------------------------
def scheduleBackupGitUpload(backup_dir: str, project_root: Optional[str] = None) -> None:
    global _git_timer

    def _job():
        try:
            uploadBackupToGit(backup_dir, project_root=project_root)
        except Exception:
            pass

    with _git_timer_lock:
        if _git_timer is not None:
            try:
                _git_timer.cancel()
            except Exception:
                pass
        _git_timer = threading.Timer(_GIT_DEBOUNCE_SEC, _job)
        _git_timer.daemon = True
        _git_timer.start()


# ------------------------------------------------------------
# Function: backupConfigAndUpload
# Purpose: Write latest per-PC backup, then schedule git commit/push.
# ------------------------------------------------------------
def backupConfigAndUpload(
    settings: Dict[str, Any],
    state: Dict[str, Any],
    project_root: Optional[str] = None,
    upload: bool = True,
) -> Optional[str]:
    try:
        backup_dir = writeConfigBackup(settings, state, project_root=project_root)
    except Exception as exc:
        print(f"[ConfigBackup] Write failed: {exc}")
        return None
    if backup_dir and upload:
        scheduleBackupGitUpload(backup_dir, project_root=project_root)
    return backup_dir
