<#
.SYNOPSIS
    Build the QtProcMan standalone executable with Nuitka (via pyside6-deploy).

.DESCRIPTION
    Steps:
      1. Sync dependencies (incl. the 'dev' group that provides Nuitka) with uv.
      2. Regenerate app.ico from the programmatic icon.
      3. Run pyside6-deploy using pysidedeploy.spec (onefile, no console).

    Output executable lands in .\dist (per exec_directory in pysidedeploy.spec).

.PARAMETER SkipIcon
    Skip regenerating app.ico.

.PARAMETER Clean
    Remove previous build artifacts (dist, build, *.build, *.dist, *.onefile-build) first.

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Clean
#>
[CmdletBinding()]
param(
    [switch]$SkipIcon,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# Resolve uv
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    throw "uv not found on PATH. Install from https://docs.astral.sh/uv/ or build manually."
}

if ($Clean) {
    Write-Step "Cleaning build artifacts"
    $targets = @('dist', 'build') + (Get-ChildItem -Path . -Directory -Filter '*.build' -ErrorAction SilentlyContinue).FullName `
                                  + (Get-ChildItem -Path . -Directory -Filter '*.dist' -ErrorAction SilentlyContinue).FullName `
                                  + (Get-ChildItem -Path . -Directory -Filter '*.onefile-build' -ErrorAction SilentlyContinue).FullName
    foreach ($t in $targets) {
        if ($t -and (Test-Path $t)) {
            Write-Host "    removing $t"
            Remove-Item -Recurse -Force $t
        }
    }
}

Write-Step "Syncing dependencies (uv sync --dev)"
& uv sync --dev
if ($LASTEXITCODE -ne 0) { throw "uv sync failed (exit $LASTEXITCODE)" }

if (-not $SkipIcon) {
    Write-Step "Regenerating app.ico"
    & uv run python build_icon.py
    if ($LASTEXITCODE -ne 0) { throw "icon generation failed (exit $LASTEXITCODE)" }
}

Write-Step "Building executable (pyside6-deploy)"
& uv run pyside6-deploy --force -c pysidedeploy.spec
if ($LASTEXITCODE -ne 0) { throw "pyside6-deploy failed (exit $LASTEXITCODE)" }

$exe = Join-Path $PSScriptRoot 'dist\QtProcMan.exe'
if (Test-Path $exe) {
    Write-Step "Done: $exe"
} else {
    Write-Step "Done. Check .\dist for output."
}
