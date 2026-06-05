@echo off
setlocal
cd /d "%~dp0"
title ProjectAce - Install

echo ========================================
echo  ProjectAce (p1) - Install
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3.10+ and add to PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create .venv
    pause
    exit /b 1
  )
) else (
  echo Virtual environment already exists.
)

call .venv\Scripts\activate.bat
echo Upgrading pip...
python -m pip install --upgrade pip -q
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed.
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo Created .env from .env.example
  )
) else (
  echo .env already exists - not overwritten.
)

echo.
echo Install complete. Run start.bat to launch the app.
echo ========================================
pause
