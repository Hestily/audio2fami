@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Bypass execution policy so double-click / cmd users can run setup.ps1.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo setup.ps1 失败，退出码 %ERR%。
  pause
)
exit /b %ERR%
