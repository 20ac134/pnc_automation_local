@echo off
setlocal enabledelayedexpansion

REM -------------------------------
REM Self-elevate to administrator if not already.
REM This must happen BEFORE anything else, including setlocal/cd commands
REM that depend on the user's environment.
REM
REM `net session` is the canonical non-destructive admin check — it requires
REM admin to succeed and exits with an error otherwise. No side effects.
REM -------------------------------
net session >nul 2>&1
if errorlevel 1 (
    echo This setup needs administrator privileges to install Node.js.
    echo Requesting elevation...
    echo.
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

REM After elevation, the working directory defaults to system32. Re-anchor.
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

REM Minimum versions
set "MIN_PY_MAJOR=3"
set "MIN_PY_MINOR=10"
set "MIN_NODE_MAJOR=18"

REM Versions to install when missing
set "PY_INSTALL_VERSION=3.12.7"
set "NODE_INSTALL_VERSION=20.18.0"

title PnC Automation Tool - Windows Setup

echo ========================================
echo PnC Automation Tool - Windows Setup
echo ========================================
echo Running as Administrator.
echo.
echo Root folder:
echo %CD%
echo.

REM -------------------------------
REM Check project folders
REM -------------------------------
echo Checking project folders...

IF NOT EXIST "%ROOT%\vosyn-automation" (
    echo ERROR: Backend folder not found:
    echo %ROOT%\vosyn-automation
    pause
    exit /b 1
)

IF NOT EXIST "%ROOT%\university-job-portal\university-job-portal" (
    echo ERROR: Frontend folder not found:
    echo %ROOT%\university-job-portal\university-job-portal
    pause
    exit /b 1
)

echo Project folders found.
echo.

REM -------------------------------
REM Check curl (required for direct downloads)
REM -------------------------------
where curl >nul 2>&1
if errorlevel 1 (
    echo ERROR: curl not found. curl ships with Windows 10 1803+ and Server 2019+.
    echo On older Windows, install Python and Node.js manually:
    echo   Python: https://www.python.org/downloads/
    echo   Node.js: https://nodejs.org/
    pause
    exit /b 1
)

REM -------------------------------
REM Check Python — version verified by running Python itself, NOT by parsing
REM the --version string (CMD's GEQ falls back to string comparison and lies).
REM -------------------------------
echo Checking Python...

set "PYTHON_CMD="

REM Try py launcher first (python.org installer registers this globally).
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (%MIN_PY_MAJOR%, %MIN_PY_MINOR%) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

REM Fall back to python on PATH, skipping the Microsoft Store stub.
if not defined PYTHON_CMD (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_CMD (
            echo %%i | findstr /i "WindowsApps" >nul
            if errorlevel 1 (
                "%%i" -c "import sys; sys.exit(0 if sys.version_info >= (%MIN_PY_MAJOR%, %MIN_PY_MINOR%) else 1)" >nul 2>&1
                if not errorlevel 1 set "PYTHON_CMD=%%i"
            )
        )
    )
)

if defined PYTHON_CMD (
    echo Found Python: !PYTHON_CMD!
    !PYTHON_CMD! --version
    echo Python OK. Continuing...
    goto :python_done
)

REM -------------------------------
REM No usable Python — install from python.org directly
REM -------------------------------
echo Python %MIN_PY_MAJOR%.%MIN_PY_MINOR%+ not found ^(or only the Microsoft Store stub is present^).
echo.
echo Installing Python %PY_INSTALL_VERSION% from python.org...
echo.

set "PY_INSTALLER=%TEMP%\python-%PY_INSTALL_VERSION%-installer.exe"
set "PY_URL=https://www.python.org/ftp/python/%PY_INSTALL_VERSION%/python-%PY_INSTALL_VERSION%-amd64.exe"

echo Downloading from:
echo %PY_URL%
echo.

curl -L -o "%PY_INSTALLER%" "%PY_URL%"
if errorlevel 1 (
    echo.
    echo ERROR: Download failed. Check your internet connection.
    echo Or install manually from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Running silent installer...
echo ----------------------------------------
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1 Include_launcher=1
set "INSTALL_RESULT=!ERRORLEVEL!"
echo ----------------------------------------

del "%PY_INSTALLER%" >nul 2>&1

if not "!INSTALL_RESULT!"=="0" (
    echo.
    echo ERROR: Python installer exited with code !INSTALL_RESULT!.
    echo Install manually from https://www.python.org/downloads/
    echo Make sure "Add python.exe to PATH" is checked.
    pause
    exit /b 1
)

echo.
echo Python %PY_INSTALL_VERSION% installed successfully.
echo.
echo IMPORTANT: Close this window and run setup_windows.bat again.
echo The new PATH won't take effect in this session.
pause
exit /b 0

:python_done
echo.

REM -------------------------------
REM Check Node.js — version verified by running Node itself
REM -------------------------------
echo Checking Node.js...

set "NODE_OK=0"
where node >nul 2>&1
if not errorlevel 1 (
    node -e "process.exit(parseInt(process.versions.node.split('.')[0]) >= %MIN_NODE_MAJOR% ? 0 : 1)" >nul 2>&1
    if not errorlevel 1 set "NODE_OK=1"
)

if "!NODE_OK!"=="1" (
    echo Found Node.js:
    node --version
    echo Node.js OK. Continuing...
    goto :node_done
)

REM -------------------------------
REM No usable Node — install from nodejs.org directly
REM -------------------------------
echo Node.js %MIN_NODE_MAJOR%+ not found.
echo.
echo Installing Node.js %NODE_INSTALL_VERSION% LTS from nodejs.org...
echo.

set "NODE_INSTALLER=%TEMP%\node-%NODE_INSTALL_VERSION%-installer.msi"
set "NODE_URL=https://nodejs.org/dist/v%NODE_INSTALL_VERSION%/node-v%NODE_INSTALL_VERSION%-x64.msi"

echo Downloading from:
echo %NODE_URL%
echo.

curl -L -o "%NODE_INSTALLER%" "%NODE_URL%"
if errorlevel 1 (
    echo.
    echo ERROR: Download failed. Check your internet connection.
    echo Or install manually from https://nodejs.org/
    pause
    exit /b 1
)

echo.
echo Running silent installer...
echo ----------------------------------------
msiexec /i "%NODE_INSTALLER%" /quiet /norestart ADDLOCAL=ALL
set "INSTALL_RESULT=!ERRORLEVEL!"
echo ----------------------------------------

del "%NODE_INSTALLER%" >nul 2>&1

if not "!INSTALL_RESULT!"=="0" (
    echo.
    echo ERROR: Node.js installer exited with code !INSTALL_RESULT!.
    echo Common causes:
    echo   - Antivirus blocked the installer
    echo   - Disk full or permission issue on Program Files
    echo Install manually from https://nodejs.org/
    pause
    exit /b 1
)

echo.
echo Node.js %NODE_INSTALL_VERSION% installed successfully.
echo.
echo IMPORTANT: Close this window and run setup_windows.bat again.
echo The new PATH won't take effect in this session.
pause
exit /b 0

:node_done
echo.

REM -------------------------------
REM Check npm — npm is npm.cmd on Windows, MUST be invoked with `call`
REM or control transfers and never returns to this script.
REM -------------------------------
echo Checking npm...

set "NPM_OK=0"
where npm >nul 2>&1
if not errorlevel 1 (
    call npm --version >nul 2>&1
    if not errorlevel 1 set "NPM_OK=1"
)

if not "!NPM_OK!"=="1" (
    echo ERROR: npm not found or not working.
    echo Node.js may not have installed correctly.
    echo Reinstall Node.js LTS from https://nodejs.org/
    pause
    exit /b 1
)

echo Found npm:
call npm --version
echo npm OK. Continuing...
echo.

REM -------------------------------
REM Backend setup
REM -------------------------------
echo ========================================
echo Setting up backend
echo ========================================
echo.

cd /d "%ROOT%\vosyn-automation"

IF NOT EXIST requirements.txt (
    echo ERROR: requirements.txt not found in backend folder.
    echo Current folder: %CD%
    pause
    exit /b 1
)

REM Detect and rebuild broken venvs. The shim env\Scripts\python.exe can still
REM exist as a file even when pyvenv.cfg points to a deleted Python install
REM (e.g. system Python was uninstalled, or you switched from system-wide to
REM per-user Python). Only running the venv python tells us if it actually works.
IF EXIST env (
    set "VENV_OK=0"
    IF EXIST "env\Scripts\python.exe" (
        "env\Scripts\python.exe" -c "import sys" >nul 2>&1
        if not errorlevel 1 set "VENV_OK=1"
    )

    IF "!VENV_OK!"=="0" (
        echo Found broken virtual environment ^(stale interpreter reference^).
        echo Removing and recreating...
        rmdir /s /q env
    ) ELSE (
        echo Backend virtual environment is healthy.
    )
)

IF NOT EXIST env (
    echo Creating Python virtual environment...
    !PYTHON_CMD! -m venv env

    IF ERRORLEVEL 1 (
        echo ERROR: Failed to create Python virtual environment.
        pause
        exit /b 1
    )

    IF NOT EXIST "env\Scripts\python.exe" (
        echo ERROR: venv reported success but env\Scripts\python.exe is missing.
        pause
        exit /b 1
    )
)

REM Use the venv's python directly. No `call activate` needed.
echo Upgrading pip...
"env\Scripts\python.exe" -m pip install --upgrade pip

IF ERRORLEVEL 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

echo Installing backend dependencies...
"env\Scripts\python.exe" -m pip install -r requirements.txt

IF ERRORLEVEL 1 (
    echo ERROR: Failed to install backend dependencies.
    pause
    exit /b 1
)

echo.

REM -------------------------------
REM Frontend setup
REM -------------------------------
echo ========================================
echo Setting up frontend
echo ========================================
echo.

cd /d "%ROOT%\university-job-portal\university-job-portal"

IF NOT EXIST package.json (
    echo ERROR: package.json not found in frontend folder.
    echo Current folder: %CD%
    pause
    exit /b 1
)

IF NOT EXIST node_modules (
    echo node_modules not found. Installing frontend dependencies...
    REM `call` is required — npm is npm.cmd and would terminate this script otherwise.
    call npm install

    IF ERRORLEVEL 1 (
        echo ERROR: Failed to install frontend dependencies.
        pause
        exit /b 1
    )
) ELSE (
    echo Frontend dependencies already installed.
)

echo.
echo ========================================
echo Setup complete.
echo Now double-click start.bat in the project root.
echo ========================================
echo.
pause