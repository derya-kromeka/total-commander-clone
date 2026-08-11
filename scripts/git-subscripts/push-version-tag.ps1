#Requires -Version 5.1
<#
.SYNOPSIS
  Create Git tag vX.Y.Z from Cargo.toml version and push to origin (releases only).

.PARAMETER DryRun
  Print commands without creating the tag or pushing.

.PARAMETER ProjectRoot
  Repository root (default: parent of scripts/).
#>
param(
    [switch] $DryRun,
    [string] $ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDir ".." "..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}
Set-Location $ProjectRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is not installed or not in PATH."
}

$SubscriptsDir = Join-Path (Split-Path $ScriptDir -Parent) "subscripts"
$VersionFromCargo = Join-Path $SubscriptsDir "version-from-cargo.ps1"
$Version = & $VersionFromCargo
$Tag = "v$Version"

Write-Host ">>> Cargo.toml version: $Version"
Write-Host ">>> Git tag to create:  $Tag"

git rev-parse "$Tag" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host ">>> Tag $Tag already exists locally."
    Write-Host "    To push it:  git push origin $Tag"
    exit 0
}

if ($DryRun) {
    Write-Host ">>> Dry run: would run: git tag -a $Tag -m `"Release $Tag`""
    Write-Host ">>> Dry run: would run: git push origin $Tag"
    exit 0
}

git tag -a $Tag -m "Release $Tag"
Write-Host ">>> Created tag $Tag"
Write-Host ">>> Pushing tag to origin..."
git push origin $Tag
Write-Host ">>> Done."
