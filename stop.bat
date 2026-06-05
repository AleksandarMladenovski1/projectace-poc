@echo off
setlocal
cd /d "%~dp0"
title ProjectAce - Stop

set PORT=5001
echo Stopping ProjectAce (port %PORT%)...

powershell -NoProfile -Command ^
  "Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

timeout /t 1 /nobreak >nul

powershell -NoProfile -Command ^
  "Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo Done.
pause
