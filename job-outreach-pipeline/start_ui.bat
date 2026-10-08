@echo off
REM Job Outreach Pipeline - UI launcher (double-click friendly)
cd /d "%~dp0"

echo ===================================================
echo   Job Outreach Pipeline - Control Panel launcher
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment ^(.venv^)...
    py -m venv .venv
)

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [*] Installing dependencies...
"%PY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo [*] Starting the control panel...
echo.
"%PY%" app.py

pause
