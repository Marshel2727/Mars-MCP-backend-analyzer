@echo off
setlocal

cd /d "%~dp0"

set "SCRIPT=%~dp0mars.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*

if "%~1"=="" (
  pause
)
