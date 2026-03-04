@echo off
setlocal

set VENV_DIR=.venv
set REQUIREMENTS=requirements.txt
set ENTRY_POINT=migrate.py

:: --- Locate Python 3 ---
set PYTHON=
where python3 >nul 2>&1 && (
    for /f "tokens=2 delims= " %%v in ('python3 --version 2^>^&1') do set PYVER=%%v
    set PYTHON=python3
    goto :found
)
where python >nul 2>&1 && (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
    set PYTHON=python
    goto :found
)

echo ERROR: Python 3 is required but not found.
echo        Install it from https://www.python.org/downloads/
exit /b 1

:found
echo Using Python %PYVER%

:: --- Create virtual environment if missing ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Creating virtual environment...
    %PYTHON% -m venv %VENV_DIR%
)

:: --- Activate virtual environment ---
call %VENV_DIR%\Scripts\activate.bat

:: --- Install / update dependencies ---
pip install --quiet --upgrade pip
pip install --quiet -r %REQUIREMENTS%

:: --- Run the wizard ---
python %ENTRY_POINT%

endlocal
