"""
Total Commander Clone - Startup update check
Compare local APP_VERSION to the public GitHub repo (and/or local git remote)
and optionally launch scripts/update-and-rebuild.bat (pull + build).

The canonical public repo needs no username/PAT for read (fetch/pull/raw).
"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from config_backup import (
    _loadSavedGitAuth,
    _runGit,
    findGitRepoRoot,
    resolveBackupRepoRoot,
)


# Public upstream (read without credentials).
PUBLIC_REPO_HTTPS = "https://github.com/derya-kromeka/total-commander-clone.git"
PUBLIC_REPO_OWNER = "derya-kromeka"
PUBLIC_REPO_NAME = "total-commander-clone"
PUBLIC_DEFAULT_BRANCH = "main"

_VERSION_RE = re.compile(
    r'APP_VERSION\s*=\s*["\'](\d+\.\d+\.\d+(?:\.\d+)?)["\']'
)


# ------------------------------------------------------------
# Function: parseVersion
# Purpose: Parse "x.y.z" into a comparable tuple of ints.
# ------------------------------------------------------------
def parseVersion(text: str) -> Optional[Tuple[int, ...]]:
    raw = (text or "").strip()
    if not raw:
        return None
    parts = []
    for piece in raw.split("."):
        if not piece.isdigit():
            return None
        parts.append(int(piece))
    if len(parts) < 2:
        return None
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


# ------------------------------------------------------------
# Function: parseAppVersionFromText
# Purpose: Extract APP_VERSION from app_version.py contents.
# ------------------------------------------------------------
def parseAppVersionFromText(text: str) -> Optional[str]:
    match = _VERSION_RE.search(text or "")
    if not match:
        return None
    return match.group(1)


# ------------------------------------------------------------
# Function: compareVersions
# Purpose: -1 if a<b, 0 if equal, 1 if a>b. None if unparsable.
# ------------------------------------------------------------
def compareVersions(a: str, b: str) -> Optional[int]:
    ta = parseVersion(a)
    tb = parseVersion(b)
    if ta is None or tb is None:
        return None
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


# ------------------------------------------------------------
# Function: _looksLikeProjectRoot
# Purpose: Folder has main.py and the update/build scripts.
# ------------------------------------------------------------
def _looksLikeProjectRoot(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    return (
        os.path.isfile(os.path.join(path, "main.py"))
        and os.path.isfile(os.path.join(path, "scripts", "update-and-rebuild.bat"))
        and (
            os.path.isfile(os.path.join(path, "scripts", "build-user.bat"))
            or os.path.isfile(os.path.join(path, "scripts", "build.bat"))
        )
    )


# ------------------------------------------------------------
# Function: findProjectRoot
# Purpose: Walk parents for a project folder (with or without .git).
# ------------------------------------------------------------
def findProjectRoot(start_path: Optional[str] = None) -> Optional[str]:
    candidates: List[str] = []
    if start_path:
        candidates.append(start_path)
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    if getattr(__import__("sys"), "frozen", False):
        import sys

        candidates.append(os.path.dirname(sys.executable))

    seen = set()
    for start in candidates:
        if not start:
            continue
        cur = os.path.abspath(start)
        for _ in range(12):
            if cur in seen:
                break
            seen.add(cur)
            if _looksLikeProjectRoot(cur):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return None


# ------------------------------------------------------------
# Function: resolveUpdateRepoRoot
# Purpose: Find project root for updates (.git preferred, not required).
# ------------------------------------------------------------
def resolveUpdateRepoRoot(project_root: Optional[str] = None) -> Optional[str]:
    # Prefer a real git checkout when present.
    root = resolveBackupRepoRoot(project_root)
    if root and os.path.isdir(os.path.join(root, ".git")) and _looksLikeProjectRoot(root):
        return root
    if project_root:
        found = findGitRepoRoot(project_root)
        if found and _looksLikeProjectRoot(found):
            return found
    # Zip-based updates work without .git — only need source + scripts.
    return findProjectRoot(project_root)


# ------------------------------------------------------------
# Function: _gitAvailable
# ------------------------------------------------------------
def _gitAvailable() -> bool:
    try:
        completed = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            **(
                {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
                if os.name == "nt"
                else {}
            ),
        )
        return completed.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------
# Function: _currentBranch
# ------------------------------------------------------------
def _currentBranch(repo_root: str) -> str:
    ok, out = _runGit(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], timeout=15)
    branch = (out or "").strip()
    if ok and branch and branch != "HEAD":
        return branch
    return PUBLIC_DEFAULT_BRANCH


# ------------------------------------------------------------
# Function: _defaultRemote
# ------------------------------------------------------------
def _defaultRemote(repo_root: str) -> str:
    ok, out = _runGit(repo_root, ["remote"], timeout=15)
    if not ok:
        return "origin"
    remotes = [line.strip() for line in (out or "").splitlines() if line.strip()]
    if "origin" in remotes:
        return "origin"
    return remotes[0] if remotes else "origin"


# ------------------------------------------------------------
# Function: ensurePublicOrigin
# Purpose: If origin is missing, add the public HTTPS remote (no auth).
# ------------------------------------------------------------
def ensurePublicOrigin(repo_root: str) -> Tuple[bool, str]:
    remote = _defaultRemote(repo_root)
    ok, url = _runGit(repo_root, ["remote", "get-url", remote], timeout=15)
    if ok and (url or "").strip():
        return True, remote

    ok, out = _runGit(
        repo_root,
        ["remote", "add", "origin", PUBLIC_REPO_HTTPS],
        timeout=15,
    )
    if ok:
        return True, "origin"
    # Race / already exists under another form
    ok2, _ = _runGit(
        repo_root,
        ["remote", "set-url", "origin", PUBLIC_REPO_HTTPS],
        timeout=15,
    )
    if ok2:
        return True, "origin"
    return False, out or "Could not configure origin"


# ------------------------------------------------------------
# Function: fetchPublicAppVersionViaHttps
# Purpose: Read APP_VERSION from raw.githubusercontent.com (anonymous).
# ------------------------------------------------------------
def fetchPublicAppVersionViaHttps(branch: str = PUBLIC_DEFAULT_BRANCH) -> Tuple[Optional[str], str]:
    branches: List[str] = []
    if branch:
        branches.append(branch)
    if PUBLIC_DEFAULT_BRANCH not in branches:
        branches.append(PUBLIC_DEFAULT_BRANCH)
    if "master" not in branches:
        branches.append("master")

    errors = []
    for br in branches:
        url = (
            f"https://raw.githubusercontent.com/{PUBLIC_REPO_OWNER}/"
            f"{PUBLIC_REPO_NAME}/{br}/app_version.py"
        )
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TotalCommanderClone-Updater"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            ver = parseAppVersionFromText(text)
            if ver:
                return ver, br
            errors.append(f"{br}: no APP_VERSION in file")
        except urllib.error.HTTPError as exc:
            errors.append(f"{br}: HTTP {exc.code}")
        except Exception as exc:
            errors.append(f"{br}: {exc}")

    return None, "; ".join(errors) if errors else "HTTPS version fetch failed"


# ------------------------------------------------------------
# Function: _fetchRemoteBranch
# Purpose: Fetch remote/branch anonymously; retry with saved PAT only if needed.
# ------------------------------------------------------------
def _fetchRemoteBranch(repo_root: str, remote: str, branch: str) -> Tuple[bool, str]:
    ok, out = _runGit(repo_root, ["fetch", remote, branch], timeout=90)
    if ok:
        return True, out

    # Public HTTPS remotes normally succeed without auth. Retry with PAT only
    # when a saved account exists (e.g. private fork / rate limits).
    auth = _loadSavedGitAuth(repo_root)
    if not auth or not auth.get("pat"):
        return False, out

    import base64

    pair = f"{auth['username']}:{auth['pat']}"
    encoded = base64.b64encode(pair.encode("ascii")).decode("ascii")
    header = f"AUTHORIZATION: basic {encoded}"
    return _runGit(
        repo_root,
        ["-c", f"http.extraHeader={header}", "fetch", remote, branch],
        timeout=90,
    )


# ------------------------------------------------------------
# Function: checkRemoteAppVersion
# Purpose: Prefer anonymous GitHub raw version; fall back to git fetch/show.
# Output: dict with status, local, remote, message, repo_root, …
# ------------------------------------------------------------
def checkRemoteAppVersion(
    local_version: str,
    project_root: Optional[str] = None,
    skip_version: str = "",
) -> Dict[str, Any]:
    repo_root = resolveUpdateRepoRoot(project_root)
    result: Dict[str, Any] = {
        "status": "error",
        "local": local_version,
        "remote": "",
        "repo_root": repo_root or "",
        "message": "",
        "branch": "",
        "remote_name": "",
        "source": "",
    }

    if not repo_root:
        result["status"] = "no_repo"
        result["message"] = (
            "Could not find the project folder near this app "
            "(needs main.py and scripts\\update-and-rebuild.bat).\n"
            f"Public repo: https://github.com/{PUBLIC_REPO_OWNER}/{PUBLIC_REPO_NAME}"
        )
        return result

    script = os.path.join(repo_root, "scripts", "update-and-rebuild.bat")
    if not os.path.isfile(script):
        result["status"] = "no_script"
        result["message"] = (
            f"Update script not found:\n{script}\n\n"
            "Keep the full project folder so updates can download sources and rebuild."
        )
        return result

    has_git = _gitAvailable() and os.path.isdir(os.path.join(repo_root, ".git"))
    if has_git:
        ensurePublicOrigin(repo_root)
        remote = _defaultRemote(repo_root)
        branch = _currentBranch(repo_root)
        result["remote_name"] = remote
    else:
        remote = "origin"
        branch = PUBLIC_DEFAULT_BRANCH
        result["remote_name"] = "(GitHub zip / HTTPS)"
    result["branch"] = branch

    remote_version = None
    # 1) Anonymous HTTPS (no account, no Git) — preferred for the public repo.
    https_ver, https_info = fetchPublicAppVersionViaHttps(branch)
    if https_ver:
        remote_version = https_ver
        result["source"] = "https"
        if https_info and https_info != branch:
            result["branch"] = https_info
            branch = https_info
    elif has_git:
        # 2) Fall back to local git fetch + show.
        ok, fetch_out = _fetchRemoteBranch(repo_root, remote, branch)
        if not ok:
            result["status"] = "fetch_failed"
            result["message"] = (
                "Could not read the latest version from GitHub "
                f"({PUBLIC_REPO_OWNER}/{PUBLIC_REPO_NAME}).\n\n"
                f"HTTPS: {https_info}\n"
                f"Git: {(fetch_out or 'Unknown fetch error')[:400]}"
            )
            return result

        ok, remote_file = _runGit(
            repo_root,
            ["show", f"{remote}/{branch}:app_version.py"],
            timeout=30,
        )
        if not ok:
            result["status"] = "no_remote_version"
            result["message"] = (
                f"Could not read app_version.py from {remote}/{branch}."
            )
            return result

        remote_version = parseAppVersionFromText(remote_file)
        result["source"] = "git"
    else:
        result["status"] = "fetch_failed"
        result["message"] = (
            "Could not read the latest version from GitHub "
            f"({PUBLIC_REPO_OWNER}/{PUBLIC_REPO_NAME}).\n\n"
            f"{https_info}\n\n"
            "No Git install is required when the network can reach GitHub."
        )
        return result

    if not remote_version:
        result["status"] = "no_remote_version"
        result["message"] = "Remote app_version.py has no parsable APP_VERSION."
        return result

    result["remote"] = remote_version
    cmp = compareVersions(local_version, remote_version)
    if cmp is None:
        result["status"] = "error"
        result["message"] = "Could not compare version numbers."
        return result

    if cmp >= 0:
        result["status"] = "up_to_date"
        if cmp == 0:
            result["message"] = (
                f"You are on the latest version (v{local_version})."
            )
        else:
            result["message"] = (
                f"Your version (v{local_version}) is newer than "
                f"GitHub (v{remote_version})."
            )
        return result

    if skip_version and skip_version.strip() == remote_version:
        result["status"] = "skipped"
        result["message"] = (
            f"Update to v{remote_version} was skipped earlier."
        )
        return result

    result["status"] = "update_available"
    how = (
        "download the public zip (no Git install needed)"
        if not (_gitAvailable() and os.path.isdir(os.path.join(repo_root, ".git")))
        else "pull the latest public code"
    )
    result["message"] = (
        f"A newer version is available on GitHub.\n\n"
        f"Current:  v{local_version}\n"
        f"GitHub:   v{remote_version}\n"
        f"Repo:     {PUBLIC_REPO_OWNER}/{PUBLIC_REPO_NAME}\n"
        f"Branch:   {branch}\n\n"
        f"Update now? This will close the app, {how}, "
        "rebuild the .exe (scripts\\build-user.bat), and restart.\n"
        "No GitHub login is required."
    )
    return result


# ------------------------------------------------------------
# Function: launchUpdateAndRebuild
# Purpose: Start scripts/update-and-rebuild.bat in a new console,
#          detached so it survives after this process exits.
# ------------------------------------------------------------
def launchUpdateAndRebuild(repo_root: str) -> Tuple[bool, str]:
    if not repo_root or not os.path.isdir(repo_root):
        return False, "Invalid project root."

    bat = os.path.join(repo_root, "scripts", "update-and-rebuild.bat")
    if not os.path.isfile(bat):
        return False, f"Missing update script:\n{bat}"

    # Only configure origin when Git + .git are available.
    if _gitAvailable() and os.path.isdir(os.path.join(repo_root, ".git")):
        ensurePublicOrigin(repo_root)

    try:
        if os.name == "nt":
            # `start "title" ...` — first quoted arg is the window title.
            # DETACHED_PROCESS keeps the updater alive after we quit.
            creationflags = (
                getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            )
            subprocess.Popen(
                [
                    "cmd.exe",
                    "/c",
                    "start",
                    "Total Commander Clone — Update",
                    "cmd.exe",
                    "/c",
                    bat,
                ],
                cwd=repo_root,
                close_fds=True,
                creationflags=creationflags,
            )
        else:
            subprocess.Popen(
                ["bash", bat.replace(".bat", ".sh")],
                cwd=repo_root,
                start_new_session=True,
            )
        return True, ""
    except Exception as exc:
        return False, str(exc)
