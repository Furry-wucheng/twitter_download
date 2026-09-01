@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo [Twitter Download] Checking runtime...

where uv >nul 2>&1
if not errorlevel 1 goto :use_uv

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :use_python
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.13"
    goto :use_python
)

echo [ERROR] Neither uv nor Python was found in PATH.
echo Install uv from https://docs.astral.sh/uv/ or install Python 3.13+.
pause
exit /b 1

:use_uv
echo [Runtime] uv
uv sync --locked
if errorlevel 1 goto :dependency_error
if /I "%~1"=="--check" (
    echo [OK] uv environment and dependencies are ready.
    exit /b 0
)
uv run --no-sync python gui.py
exit /b %errorlevel%

:use_python
echo [Runtime] %PYTHON_CMD%
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.13 or newer is required.
    pause
    exit /b 1
)

%PYTHON_CMD% -c "import httpx, PySide6, x_client_transaction" >nul 2>&1
if errorlevel 1 (
    echo [Dependencies] Installing packages from requirements.txt...
    %PYTHON_CMD% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 goto :dependency_error
)

if /I "%~1"=="--check" (
    echo [OK] Python environment and dependencies are ready.
    exit /b 0
)
%PYTHON_CMD% gui.py
exit /b %errorlevel%

:dependency_error
echo [ERROR] Dependency setup failed. Review the output above and try again.
pause
exit /b 1
