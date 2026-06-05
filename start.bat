@echo off
setlocal
cd /d "%~dp0"
title ProjectAce - Server

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment missing. Run install.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
echo ========================================
echo  ProjectAce - http://localhost:5001
echo  User manual: /docs/manual
echo  Press Ctrl+C to stop, or run stop.bat
echo ========================================
echo.
python run.py
