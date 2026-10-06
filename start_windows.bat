@echo off
setlocal
cd /d "%~dp0"
echo 18wheelers Jobs - starting your workspace...
where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo Select "Add python.exe to PATH", then run this file again.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    %PYTHON% -m venv .venv
    if errorlevel 1 goto fail
)
if not exist ".venv\.18w-ready" (
    echo Installing the app's dependencies. Internet is needed for this first step.
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto fail
    echo ready>".venv\.18w-ready"
)
".venv\Scripts\python.exe" run.py
pause
exit /b 0
:fail
echo.
echo Setup failed. Read the message above, check your internet connection, and retry.
pause
exit /b 1
