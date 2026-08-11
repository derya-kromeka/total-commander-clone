#Requires -Version 5.1
<#
.SYNOPSIS
  Configure Git remote, commit identity, and GitHub credentials for this repository.

.DESCRIPTION
  Saves settings to .git-account.json (gitignored) and encrypts the PAT in
  .git-account.pat (gitignored, Windows DPAPI). git-sync.ps1 loads these on push/pull.

.EXAMPLE
  .\scripts\git-config-account.cmd
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-GitAccountRepoRoot {
    if ($script:GitAccountRepoRoot) { return $script:GitAccountRepoRoot }
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-GitAccountPaths {
    $root = Get-GitAccountRepoRoot
    return @{
        Root    = $root
        Profile = Join-Path $root ".git-account.json"
        Pat     = Join-Path $root ".git-account.pat"
    }
}

function Write-AccountStep([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-AccountOk([string]$Message) {
    Write-Host "    $Message" -ForegroundColor Green
}

function Write-AccountWarn([string]$Message) {
    Write-Host "    $Message" -ForegroundColor Yellow
}

function Read-HostWithDefault {
    param([string] $Prompt, [string] $Default = "")
    if ($Default) {
        $value = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
        return $value
    }
    do {
        $value = Read-Host $Prompt
    } while ([string]::IsNullOrWhiteSpace($value))
    return $value
}

function Read-SecurePat {
    param([string] $Prompt = "Personal Access Token (PAT)")
    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Invoke-GitAccountGit {
    param([Parameter(Mandatory)][string[]] $Args)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $paths = Get-GitAccountPaths
        Push-Location $paths.Root
        try {
            $raw = & git @Args 2>&1
            $exit = $LASTEXITCODE
            $text = (@($raw) | ForEach-Object { $_.ToString() }) -join "`n"
            if ($exit -ne 0) {
                throw "git $($Args -join ' ') failed (exit $exit):`n$text"
            }
            return $text.Trim()
        } finally {
            Pop-Location
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

function Normalize-RemoteUrl {
    param([string] $Url)
    $Url = $Url.Trim()
    if ($Url -notmatch '^https?://') {
        if ($Url -match '^[\w\.\-]+/[\w\.\-]+/[\w\.\-]+') {
            $Url = "https://github.com/$Url"
        } else {
            $Url = "https://$Url"
        }
    }
    if ($Url -notmatch '\.git$') {
        $Url = "$Url.git"
    }
    return $Url
}

function Get-GitAccountProfile {
    $paths = Get-GitAccountPaths
    if (-not (Test-Path $paths.Profile)) {
        return $null
    }
    $raw = Get-Content -Path $paths.Profile -Raw -Encoding UTF8
    return ($raw | ConvertFrom-Json)
}

function Save-GitAccountProfile {
    param(
        [string] $Label,
        [string] $RemoteUrl,
        [string] $CommitName,
        [string] $CommitEmail,
        [string] $GithubUsername
    )
    $paths = Get-GitAccountPaths
    $existing = Get-GitAccountProfile
    $profile = [ordered]@{
        label          = if ($Label) { $Label } elseif ($existing) { $existing.label } else { "default" }
        remoteUrl      = $RemoteUrl
        commitName     = $CommitName
        commitEmail    = $CommitEmail
        githubUsername = $GithubUsername
    }
    $profile | ConvertTo-Json | Set-Content -Path $paths.Profile -Encoding UTF8
    Write-AccountOk "Saved profile to $($paths.Profile)"
}

function Save-GitAccountPat {
    param([Parameter(Mandatory)][string] $Pat)
    if ([string]::IsNullOrWhiteSpace($Pat)) {
        throw "PAT cannot be empty."
    }
    $paths = Get-GitAccountPaths
    $secure = ConvertTo-SecureString -String $Pat -AsPlainText -Force
    $encrypted = ConvertFrom-SecureString -SecureString $secure
    Set-Content -Path $paths.Pat -Value $encrypted -Encoding UTF8 -NoNewline
    Write-AccountOk "PAT saved (encrypted for this Windows user) in $($paths.Pat)"
}

function Get-GitAccountPat {
    $paths = Get-GitAccountPaths
    if (-not (Test-Path $paths.Pat)) {
        return $null
    }
    try {
        $encrypted = Get-Content -Path $paths.Pat -Raw -Encoding UTF8
        $secure = ConvertTo-SecureString -String $encrypted
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            return [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    } catch {
        Write-AccountWarn "Could not read saved PAT (re-run this script and set PAT again)."
        return $null
    }
}

function Remove-GitAccountPat {
    $paths = Get-GitAccountPaths
    if (Test-Path $paths.Pat) {
        Remove-Item -Path $paths.Pat -Force
        Write-AccountOk "Removed saved PAT"
    } else {
        Write-AccountWarn "No saved PAT file"
    }
}

function Remove-GitAccountProfile {
    $paths = Get-GitAccountPaths
    if (Test-Path $paths.Profile) {
        Remove-Item -Path $paths.Profile -Force
        Write-AccountOk "Removed profile"
    }
    Remove-GitAccountPat
}

function Get-GitAccountAuth {
    $profile = Get-GitAccountProfile
    if (-not $profile -or -not $profile.githubUsername) {
        return $null
    }
    $pat = Get-GitAccountPat
    if (-not $pat) {
        return $null
    }
    return @{ Username = $profile.githubUsername.ToString(); Pat = $pat }
}

function Apply-GitAccountProfile {
    param(
        [object] $Profile,
        [string] $RemoteName = "origin"
    )
    if (-not $Profile) { return }

    if ($Profile.remoteUrl) {
        $url = Normalize-RemoteUrl -Url $Profile.remoteUrl.ToString()
        Invoke-GitAccountGit -Args @("remote", "set-url", $RemoteName, $url) | Out-Null
        Write-AccountOk "Remote '$RemoteName' -> $url"
    }
    if ($Profile.commitName) {
        Invoke-GitAccountGit -Args @("config", "--local", "user.name", $Profile.commitName.ToString()) | Out-Null
        Write-AccountOk "Commit name: $($Profile.commitName)"
    }
    if ($Profile.commitEmail) {
        Invoke-GitAccountGit -Args @("config", "--local", "user.email", $Profile.commitEmail.ToString()) | Out-Null
        Write-AccountOk "Commit email: $($Profile.commitEmail)"
    }
}

function Import-GitAccountProfile {
    param([string] $RemoteName = "origin")
    $profile = Get-GitAccountProfile
    if (-not $profile) { return $null }
    Apply-GitAccountProfile -Profile $profile -RemoteName $RemoteName
    return $profile
}

function Show-GitAccountStatus {
    param([string] $RemoteName = "origin")
    $paths = Get-GitAccountPaths
    $profile = Get-GitAccountProfile
    $hasPat = Test-Path $paths.Pat

    Write-AccountStep "Current Git settings"
    try {
        $remote = Invoke-GitAccountGit -Args @("remote", "get-url", $RemoteName)
        Write-AccountOk "Remote '$RemoteName': $remote"
    } catch {
        Write-AccountWarn "Remote '$RemoteName' is not set"
    }
    try {
        $name = Invoke-GitAccountGit -Args @("config", "--get", "user.name")
        $email = Invoke-GitAccountGit -Args @("config", "--get", "user.email")
        Write-AccountOk "Commit identity: $name <$email>"
    } catch {
        Write-AccountWarn "Commit identity not configured"
    }

    Write-AccountStep "Saved account profile"
    if ($profile) {
        Write-AccountOk "Label: $($profile.label)"
        Write-AccountOk "Profile remote: $($profile.remoteUrl)"
        Write-AccountOk "Profile commit: $($profile.commitName) <$($profile.commitEmail)>"
        Write-AccountOk "GitHub username: $($profile.githubUsername)"
        if ($hasPat) {
            Write-AccountOk "PAT: saved (encrypted)"
        } else {
            Write-AccountWarn "PAT: not saved (you will be prompted on push)"
        }
    } else {
        Write-AccountWarn "No .git-account.json (run option 2 to create one)"
    }
}

function Invoke-GitAccountWizard {
    param([string] $RemoteName = "origin")

    Write-Host @"

Configure push account for this repository.
Settings are stored locally (gitignored) and applied when you run git-push.cmd.

Use a GitHub Personal Access Token, not your password.
  GitHub: Settings -> Developer settings -> Personal access tokens

"@ -ForegroundColor DarkGray

    $currentRemote = ""
    $currentName = ""
    $currentEmail = ""
    $currentGithub = ""
    try { $currentRemote = Invoke-GitAccountGit -Args @("remote", "get-url", $RemoteName) } catch { }
    try { $currentName = Invoke-GitAccountGit -Args @("config", "--get", "user.name") } catch { }
    try { $currentEmail = Invoke-GitAccountGit -Args @("config", "--get", "user.email") } catch { }
    $saved = Get-GitAccountProfile
    if ($saved -and $saved.githubUsername) { $currentGithub = $saved.githubUsername.ToString() }

    $label = Read-HostWithDefault -Prompt "Profile label (e.g. korhag, work)" -Default $(if ($saved) { $saved.label } else { "default" })
    $remote = Read-HostWithDefault -Prompt "Remote repository URL" -Default $(if ($currentRemote) { $currentRemote } else { "" })
    $remote = Normalize-RemoteUrl -Url $remote

    $commitName = Read-HostWithDefault -Prompt "Name on commits" -Default $currentName
    $commitEmail = Read-HostWithDefault -Prompt "Email on commits" -Default $currentEmail
    $githubUser = Read-HostWithDefault -Prompt "GitHub username (for HTTPS push)" -Default $currentGithub

    Write-Host ""
    $savePat = (Read-Host "Save PAT for later pushes? [Y/n]").Trim()
    if ($savePat -eq "" -or $savePat -match '^[Yy]') {
        $pat = Read-SecurePat -Prompt "Personal Access Token (PAT) [input hidden]"
        Save-GitAccountPat -Pat $pat
    } else {
        Write-AccountWarn "PAT not saved; git-push will ask when needed"
    }

    Save-GitAccountProfile -Label $label -RemoteUrl $remote -CommitName $commitName -CommitEmail $commitEmail -GithubUsername $githubUser
    Apply-GitAccountProfile -Profile (Get-GitAccountProfile) -RemoteName $RemoteName
    Write-AccountOk "Done. Use scripts\git-push.cmd to push with these settings."
}

function Show-GitAccountMenu {
    param([string] $RemoteName = "origin")
    while ($true) {
        Write-Host ""
        Write-Host "Git account for this repo" -ForegroundColor White
        Write-Host "  [1] Show current settings"
        Write-Host "  [2] Configure account (URL, commit identity, GitHub user, optional PAT)"
        Write-Host "  [3] Change remote URL only"
        Write-Host "  [4] Change commit name / email only"
        Write-Host "  [5] Change GitHub username / PAT only"
        Write-Host "  [6] Remove saved PAT"
        Write-Host "  [7] Remove entire saved profile"
        Write-Host "  [Q] Quit"
        $choice = (Read-Host "Choice").Trim().ToUpperInvariant()
        switch ($choice) {
            "1" { Show-GitAccountStatus -RemoteName $RemoteName }
            "2" { Invoke-GitAccountWizard -RemoteName $RemoteName }
            "3" {
                $current = ""
                try { $current = Invoke-GitAccountGit -Args @("remote", "get-url", $RemoteName) } catch { }
                $remote = Normalize-RemoteUrl -Url (Read-HostWithDefault -Prompt "Remote URL" -Default $current)
                Invoke-GitAccountGit -Args @("remote", "set-url", $RemoteName, $remote) | Out-Null
                $p = Get-GitAccountProfile
                if ($p) {
                    Save-GitAccountProfile -Label $p.label -RemoteUrl $remote -CommitName $p.commitName -CommitEmail $p.commitEmail -GithubUsername $p.githubUsername
                } else {
                    Save-GitAccountProfile -Label "default" -RemoteUrl $remote -CommitName "" -CommitEmail "" -GithubUsername ""
                }
                Write-AccountOk "Remote updated"
            }
            "4" {
                $name = Read-HostWithDefault -Prompt "Commit name"
                $email = Read-HostWithDefault -Prompt "Commit email"
                Invoke-GitAccountGit -Args @("config", "--local", "user.name", $name) | Out-Null
                Invoke-GitAccountGit -Args @("config", "--local", "user.email", $email) | Out-Null
                $p = Get-GitAccountProfile
                if ($p) {
                    Save-GitAccountProfile -Label $p.label -RemoteUrl $p.remoteUrl -CommitName $name -CommitEmail $email -GithubUsername $p.githubUsername
                }
                Write-AccountOk "Commit identity updated"
            }
            "5" {
                $p = Get-GitAccountProfile
                $defaultUser = if ($p) { $p.githubUsername } else { "" }
                $githubUser = Read-HostWithDefault -Prompt "GitHub username" -Default $defaultUser
                $pat = Read-SecurePat -Prompt "PAT [input hidden]"
                Save-GitAccountPat -Pat $pat
                if ($p) {
                    Save-GitAccountProfile -Label $p.label -RemoteUrl $p.remoteUrl -CommitName $p.commitName -CommitEmail $p.commitEmail -GithubUsername $githubUser
                } else {
                    Save-GitAccountProfile -Label "default" -RemoteUrl "" -CommitName "" -CommitEmail "" -GithubUsername $githubUser
                }
                Write-AccountOk "GitHub credentials updated"
            }
            "6" { Remove-GitAccountPat }
            "7" { Remove-GitAccountProfile }
            "Q" { return }
            default { Write-AccountWarn "Enter 1-7 or Q" }
        }
    }
}

# Run menu only when executed directly (not dot-sourced from git-sync.ps1)
if ($MyInvocation.InvocationName -ne '.') {
    $script:GitAccountRepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $repoName = Split-Path -Leaf $script:GitAccountRepoRoot
    Write-Host "`n$repoName - Git account setup`n" -ForegroundColor White
    try {
        Show-GitAccountMenu
        Write-Host "`nDone.`n" -ForegroundColor Green
    } catch {
        Write-Host "`nERROR: $($_.Exception.Message)`n" -ForegroundColor Red
        exit 1
    }
}
