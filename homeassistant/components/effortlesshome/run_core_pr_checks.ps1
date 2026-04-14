[CmdletBinding()]
param(
    [ValidateSet("all", "prek", "hassfest", "pylint", "mypy")]
    [string[]]$Checks = @("all"),

    [string]$Integration = "effortlesshome",

    [switch]$Setup
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$Name' is not available on PATH."
    }

    return $command.Path
}

function Find-PythonCommand {
    foreach ($candidate in @("py", "python", "python3")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Path
        }
    }

    throw "No Python command found on PATH. Install Python 3.13 and retry."
}

# Setup steps: abort immediately on failure.
function Invoke-SetupStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host ""
    Write-Host "========== $Name =========="
    & $Action
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Setup step '$Name' failed with exit code $LASTEXITCODE."
    }
}

# Check steps: always run to completion; failures are collected and reported at the end.
$script:checkResults = [System.Collections.Generic.List[object]]::new()

function Invoke-CheckStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host ""
    Write-Host "========== $Name =========="
    & $Action
    $code = $LASTEXITCODE
    if ($code -and $code -ne 0) {
        $script:checkResults.Add([pscustomobject]@{ Name = $Name; Passed = $false; ExitCode = $code })
    }
    else {
        $script:checkResults.Add([pscustomobject]@{ Name = $Name; Passed = $true; ExitCode = 0 })
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$coreRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")

Set-Location $coreRoot

$componentPath = "homeassistant/components/$Integration"
if (-not (Test-Path $componentPath)) {
    throw "Integration path '$componentPath' does not exist under $coreRoot"
}

$venvPython = Join-Path $coreRoot ".venv\Scripts\python.exe"
$venvScripts = Join-Path $coreRoot ".venv\Scripts"
$prekExe = Join-Path $venvScripts "prek.exe"
$pylintExe = Join-Path $venvScripts "pylint.exe"
$mypyExe = Join-Path $venvScripts "mypy.exe"

if ($Checks -contains "all") {
    $checksToRun = @("prek", "hassfest", "pylint", "mypy")
}
else {
    $checksToRun = $Checks
}

$needsSetup = $Setup -or -not (Test-Path $venvPython)
if (-not $needsSetup) {
    if (($checksToRun -contains "prek") -and -not (Test-Path $prekExe)) {
        $needsSetup = $true
    }
    if (($checksToRun -contains "pylint") -and -not (Test-Path $pylintExe)) {
        $needsSetup = $true
    }
    if (($checksToRun -contains "mypy") -and -not (Test-Path $mypyExe)) {
        $needsSetup = $true
    }
}

# Prevent git from trying to hash .agent/skills (incompatible file on Windows)
# that causes `git diff` to fail with "Function not implemented" inside prek.
$agentSkills = Join-Path (Join-Path $coreRoot ".agent") "skills"
if (Test-Path $agentSkills) {
    git -C $coreRoot update-index --assume-unchanged ".agent/skills" 2>$null
}

if ($needsSetup) {
    $uvCommand = Get-Command "uv" -ErrorAction SilentlyContinue
    $uvPath = $null
    if ($uvCommand) {
        $uvPath = $uvCommand.Path
    }
    $pythonBootstrap = Find-PythonCommand

    if (-not (Test-Path $venvPython)) {
        Invoke-SetupStep -Name "Create .venv" -Action {
            if ($uvPath) {
                & $uvPath venv .venv
            }
            else {
                & $pythonBootstrap -m venv .venv
            }
        }
    }

    # Install HA core + its runtime dependencies (brings in orjson etc.)
    Invoke-SetupStep -Name "Install HA package (editable)" -Action {
        if ($uvPath) {
            & $uvPath pip install --python $venvPython -e . --config-settings editable_mode=compat
        }
        else {
            & $venvPython -m pip install --upgrade pip
            & $venvPython -m pip install -e . --config-settings editable_mode=compat
        }
    }

    # Install base HA runtime requirements (includes orjson, needed by translations/hassfest)
    Invoke-SetupStep -Name "Install requirements.txt" -Action {
        if ($uvPath) {
            & $uvPath pip install --python $venvPython -r requirements.txt
        }
        else {
            & $venvPython -m pip install -r requirements.txt
        }
    }

    # Install linting tools: prek, pylint, mypy, and typed stubs
    Invoke-SetupStep -Name "Install requirements_test.txt (lint tools)" -Action {
        if ($uvPath) {
            & $uvPath pip install --python $venvPython -r requirements_test.txt
        }
        else {
            & $venvPython -m pip install -r requirements_test.txt
        }
    }
}

if (-not (Test-Path $venvPython)) {
    throw "Missing .venv python at $venvPython after setup."
}

# Make .venv tools resolvable for subprocesses (hassfest calls `ruff`).
if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $venvScripts })) {
    $env:PATH = "$venvScripts;$env:PATH"
}

foreach ($check in $checksToRun) {
    switch ($check) {
        "prek" {
            if (-not (Test-Path $prekExe)) {
                throw "prek is not installed in .venv after setup."
            }

            Invoke-CheckStep -Name "Run prek checks" -Action {
                # Re-apply assume-unchanged in case git index was refreshed.
                git -C $coreRoot update-index --assume-unchanged ".agent/skills" 2>$null

                # Use --files to target only integration files.
                # Avoids --all-files which runs git ls-files and tries to hash
                # .agent/skills (incompatible on Windows).
                $rootLen = ([string]$coreRoot).Length + 1
                $integrationFiles = Get-ChildItem -Path $componentPath -Recurse -File |
                Where-Object { $_.Extension -in @('.py', '.yaml', '.json', '.md', '.js') } |
                ForEach-Object { $_.FullName.Substring($rootLen).Replace('\', '/') }

                if (-not $integrationFiles) {
                    Write-Host "No checkable files found in $componentPath - skipping prek."
                    return
                }

                $env:PREK_SKIP = "no-commit-to-branch,mypy,pylint,gen_requirements_all,hassfest,hassfest-metadata,hassfest-mypy-config,zizmor"
                & $prekExe run --files @integrationFiles
                Remove-Item Env:PREK_SKIP -ErrorAction SilentlyContinue
            }
        }

        "hassfest" {
            Invoke-CheckStep -Name "Check hassfest" -Action {
                & $venvPython -m script.hassfest --requirements --action validate --integration-path $componentPath
            }
        }

        "pylint" {
            if (-not (Test-Path $pylintExe)) {
                throw "pylint is not installed in .venv after setup."
            }

            Invoke-CheckStep -Name "Check pylint" -Action {
                & $pylintExe --ignore-missing-annotations=y $componentPath
            }
        }

        "mypy" {
            if (-not (Test-Path $mypyExe)) {
                throw "mypy is not installed in .venv after setup."
            }

            Invoke-CheckStep -Name "Check mypy" -Action {
                & $mypyExe $componentPath
            }
        }
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "RESULTS"
Write-Host "============================================================"
$anyFailed = $false
foreach ($r in $script:checkResults) {
    if ($r.Passed) {
        Write-Host "  PASSED  $($r.Name)"
    }
    else {
        Write-Host "  FAILED  $($r.Name)  (exit $($r.ExitCode))"
        $anyFailed = $true
    }
}
Write-Host ""
if ($anyFailed) {
    Write-Host "One or more checks failed."
    exit 1
}
else {
    Write-Host "All checks passed."
    exit 0
}