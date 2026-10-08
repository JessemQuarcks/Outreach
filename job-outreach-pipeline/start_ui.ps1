# Job Outreach Pipeline — UI launcher (PowerShell)
# Creates a local virtual environment if needed, installs dependencies,
# and starts the web control panel in your browser.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "==================================================="
Write-Host "  Job Outreach Pipeline - Control Panel launcher"
Write-Host "==================================================="

# 1. Ensure a virtual environment exists.
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment (.venv)..."
    py -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# 2. Install / update dependencies.
Write-Host "[*] Installing dependencies..."
& $py -m pip install --quiet --disable-pip-version-check -r requirements.txt

# 3. Launch the app (it opens the browser itself).
Write-Host "[*] Starting the control panel..."
Write-Host ""
& $py app.py
