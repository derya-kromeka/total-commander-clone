#Requires -Version 5.1
<#
.SYNOPSIS
  Saves a GitHub Personal Access Token (PAT) for HTTPS Git in this repo only.
  Called from git-hub-menu.bat (option 11). Do not commit .git/gh-credential-store.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-BannerWarningSsh {
    Write-Host ''
    Write-Host '**********************************************************************'
    Write-Host '*  WARNING                                                           *'
    Write-Host '*  Your remote "origin" uses SSH (git@github.com:...), not HTTPS.  *'
    Write-Host '*  Saving an HTTPS token here does NOT change that. Git will keep   *'
    Write-Host '*  using SSH for push/pull until you switch the URL (menu opt. 3) *'
    Write-Host '*  or set up SSH keys.                                             *'
    Write-Host '**********************************************************************'
    Write-Host ''
}

function Write-BannerFail {
    param([string]$Title = 'FAILED')
    Write-Host ''
    Write-Host '**********************************************************************'
    Write-Host "*  $Title  *"
    Write-Host '**********************************************************************'
    Write-Host ''
}

function Write-BannerSuccess {
    Write-Host ''
    Write-Host '**********************************************************************'
    Write-Host '*                         SUCCESS                                    *'
    Write-Host '*  Git reached GitHub using your saved credentials (HTTPS store).   *'
    Write-Host '*  Next: in git-hub-menu use option 6 (Save to GitHub) to push.   *'
    Write-Host '**********************************************************************'
    Write-Host ''
}

function ConvertFrom-SecureStringPlain {
    param([System.Security.SecureString]$SecureString)
    if ($null -eq $SecureString) { return '' }
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Set-GhCredentialStoreAclCurrentUserOnly {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return }
    $acct = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $FilePath /inheritance:r /grant:r "$($acct):(R,W)" | Out-Null
}

function Show-LsRemoteHints {
    param([string]$ErrText)
    $t = $ErrText
    if ($t -match '401|Authentication failed|could not read Username|Missing or invalid credentials|403|invalid credentials') {
        Write-Host 'What this usually means (plain English):'
        Write-Host '  - The token is wrong or expired, or the username does not match GitHub.'
        Write-Host '  - Fix: create a new token on GitHub and run this wizard again.'
    }
    elseif ($t -match 'Repository not found|404') {
        Write-Host 'What this usually means (plain English):'
        Write-Host '  - Wrong repo URL, or you do not have access, or the repo name is private.'
        Write-Host '  - Fix: check option 3 (remote URL) and that you are logged into the right GitHub account.'
    }
    elseif ($t -match 'Could not resolve host|timed out|Network is unreachable') {
        Write-Host 'What this usually means (plain English):'
        Write-Host '  - Network or DNS problem (offline, firewall, VPN).'
    }
    else {
        Write-Host 'See the Git message above. If unsure, use git-hub-menu option 12 (diagnose).'
    }
}

# ------------------------------------------------------------
# Resolve project root (folder that contains .git)
# ------------------------------------------------------------
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$GitDir = Join-Path $ProjectRoot '.git'
$StoreFile = Join-Path $GitDir 'gh-credential-store'

Clear-Host
Write-Host '========== GitHub HTTPS - Personal Access Token (wizard) =========='
Write-Host ''
Write-Host 'GitHub does not accept your normal account password for Git over HTTPS.'
Write-Host 'You need a token (Personal Access Token / PAT) and we store it only for'
Write-Host 'this repo on this PC (not in your source code).'
Write-Host ''

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-BannerFail 'Git not found in PATH'
    Write-Host 'Install Git for Windows, then close and reopen this window.'
    Write-Host 'https://git-scm.com/download/win'
    exit 1
}

if (-not (Test-Path -LiteralPath $GitDir)) {
    Write-BannerFail 'Not a Git repository'
    Write-Host "There is no folder: $GitDir"
    Write-Host 'Use git-hub-menu option 2 first (init repository).'
    exit 1
}

$originUrl = ''
try {
    $originUrl = (& git -C $ProjectRoot remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0) { $originUrl = '' }
}
catch { $originUrl = '' }

if ([string]::IsNullOrWhiteSpace($originUrl)) {
    Write-BannerFail 'No remote named origin'
    Write-Host 'Set your GitHub URL first: git-hub-menu option 3.'
    exit 1
}

if ($originUrl -match '^git@github\.com') {
    Write-BannerWarningSsh
}

Write-Host '--- Step 1: Create a token on GitHub (pick one path) ---'
Write-Host ''
Write-Host '  1) Classic token (simple)'
Write-Host '     - Scope: repo (full control of private repositories)'
Write-Host '  2) Fine-grained token (least access)'
Write-Host '     - Repository contents: Read and write; Metadata: Read'
Write-Host '  3) I already copied a token — skip opening the browser'
Write-Host ''
$pick = Read-Host 'Enter 1, 2, or 3'
$pick = $pick.Trim()

if ($pick -eq '1') {
    Write-Host ''
    Write-Host 'On the website: Generate new token (classic), enable scope "repo", then copy'
    Write-Host 'the token (often starts with ghp_). It is shown only once.'
    Write-Host ''
    $open = Read-Host 'Open the Classic tokens page in your browser now? [y/N]'
    if ($open -eq 'y' -or $open -eq 'yes') {
        Start-Process 'https://github.com/settings/tokens'
    }
}
elseif ($pick -eq '2') {
    Write-Host ''
    Write-Host 'On the website: choose repository access and permissions as above, then copy'
    Write-Host 'the generated token.'
    Write-Host ''
    $open = Read-Host 'Open the Fine-grained token page in your browser now? [y/N]'
    if ($open -eq 'y' -or $open -eq 'yes') {
        Start-Process 'https://github.com/settings/personal-access-tokens/new'
    }
}
else {
    Write-Host ''
    Write-Host 'Have your token ready to paste in the next step.'
    Write-Host ''
}

Write-Host ''
Write-Host '--- Step 2: Save token for THIS repository only ---'
Write-Host "Stored in (never committed): $StoreFile"
Write-Host ''
Write-Host 'GitHub username = your login name on github.com (not your email, usually).'
Write-Host ''
$ghUser = Read-Host 'GitHub username (empty = cancel)'
$ghUser = $ghUser.Trim()
if ([string]::IsNullOrWhiteSpace($ghUser)) {
    Write-Host 'Cancelled — nothing was saved.'
    exit 0
}

$sec = Read-Host -AsSecureString 'Paste token (input is hidden)'
$ghToken = ConvertFrom-SecureStringPlain -SecureString $sec
$sec = $null
$ghToken = ($ghToken -replace "`r`n|`n|`r", '').Trim()

if ([string]::IsNullOrWhiteSpace($ghToken)) {
    Write-BannerFail 'Empty token'
    Write-Host 'No token was saved. Run this script again when you have a token.'
    exit 1
}

$line = "https://${ghUser}:${ghToken}@github.com`n"
$ghToken = $null

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($StoreFile, $line, $utf8NoBom)
Set-GhCredentialStoreAclCurrentUserOnly -FilePath $StoreFile

$storeForGit = ($StoreFile -replace '\\', '/')
& git -C $ProjectRoot config --local credential.helper "store --file=$storeForGit"
if ($LASTEXITCODE -ne 0) {
    Write-BannerFail 'Could not set credential.helper'
    Write-Host 'Your token file was written, but git config failed. Check permissions on .git'
    exit 1
}

Write-Host ''
Write-Host 'Saved. Testing: git ls-remote --heads origin'
Write-Host ''

$prevEa = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$lsOut = & git -C $ProjectRoot ls-remote --heads origin 2>&1
$exit = $LASTEXITCODE
$ErrorActionPreference = $prevEa

$combined = ''
if ($null -ne $lsOut) {
    if ($lsOut -is [System.Array]) {
        $combined = ($lsOut | ForEach-Object { "$_" }) -join "`n"
    }
    else {
        $combined = "$lsOut"
    }
}
$combined = $combined.Trim()

if ($exit -eq 0) {
    Write-BannerSuccess
}
else {
    Write-BannerFail 'CONNECTION TEST FAILED'
    Write-Host 'Git output (last lines help explain the problem):'
    if ([string]::IsNullOrWhiteSpace($combined)) {
        Write-Host '  (no output from git)'
    }
    else {
        $lines = $combined -split "`n"
        $tail = $lines | Select-Object -Last 12
        foreach ($ln in $tail) { Write-Host "  $ln" }
    }
    Write-Host ''
    Show-LsRemoteHints -ErrText $combined
    Write-Host ''
    Write-Host 'You can fix the remote URL (option 3) or run option 12 (diagnose).'
    Write-Host 'Your token file is still saved; if the problem was network, try again later.'
}

Write-Host ''
$rm = Read-Host 'Remove saved token and repo-only credential helper now? [y/N]'
if ($rm -eq 'y' -or $rm -eq 'yes') {
    if (Test-Path -LiteralPath $StoreFile) {
        Remove-Item -LiteralPath $StoreFile -Force
    }
    & git -C $ProjectRoot config --local --unset credential.helper 2>$null
    Write-Host 'Removed .git/gh-credential-store and local credential.helper.'
}
else {
    Write-Host 'Token left in place. Done.'
}

Write-Host ''
Read-Host 'Press Enter to return to the menu'
