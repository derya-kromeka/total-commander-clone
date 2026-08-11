# Saves GitHub HTTPS credentials for this repo only (.git/gh-credential-store).
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/git-subscripts/save-github-token.ps1
$ErrorActionPreference = "Stop"
# Windows PowerShell 5.1: Join-Path only accepts two path segments (not three).
$repoRoot = Join-Path (Join-Path $PSScriptRoot "..") ".."
$root = (Resolve-Path $repoRoot).Path
Set-Location $root
$store = Join-Path $root ".git\gh-credential-store"

Write-Host ""
Write-Host "GitHub username (login, not email): " -NoNewline
$user = Read-Host
$sec = Read-Host "Paste token" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try {
  $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) | Out-Null
}
if ([string]::IsNullOrWhiteSpace($user) -or [string]::IsNullOrWhiteSpace($token)) {
  Write-Host "Cancelled (empty username or token)."
  exit 1
}
$line = "https://${user}:${token}@github.com"
[System.IO.File]::WriteAllText($store, $line)
$storeGit = ($store -replace "\\", "/")
& git config --local credential.helper "store --file=$storeGit"
Write-Host ""
Write-Host "Saved for this repo: $store"
Write-Host "Try pull/push from git-hub-menu.bat (options 4 / 6)."
