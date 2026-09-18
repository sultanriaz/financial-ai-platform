#Requires -Version 5.1
<#
.SYNOPSIS
    Apply all 19 bug-fix patches to the Financial AI Platform.
.DESCRIPTION
    This is a thin wrapper. All patching logic lives in patch.py so that
    file-writing uses Python's UTF-8 support with no PowerShell encoding issues.

    Run from the project root:
        cd C:\black_paper\Projects\financial-ai-platform
        .\Apply-Patches.ps1

    Flags:
        -WhatIf     Preview changes without writing any files.
        -NoBackup   Skip creating .bak copies of originals.

.REQUIREMENTS
    Python 3.8+ must be on PATH.  Verify with: python --version
#>
param(
    [string]$ProjectRoot = $PSScriptRoot,
    [switch]$WhatIf,
    [switch]$NoBackup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Resolve python executable (try python3 first, then python)
$py = $null
foreach ($candidate in @("python3", "python")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python 3") { $py = $candidate; break }
    } catch { }
}
if (-not $py) {
    Write-Error "Python 3 not found on PATH. Install from https://python.org and retry."
    exit 1
}

$patchScript = Join-Path $PSScriptRoot "patch.py"
if (-not (Test-Path $patchScript)) {
    Write-Error "patch.py not found next to Apply-Patches.ps1. Both files must be in the project root."
    exit 1
}

$argList = @($patchScript, $ProjectRoot)
if ($WhatIf)   { $argList += "--whatif"    }
if ($NoBackup) { $argList += "--no-backup" }

& $py @argList
exit $LASTEXITCODE
