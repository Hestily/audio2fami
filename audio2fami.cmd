@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if exist "%~dp0third_party\ffmpeg\ffmpeg.exe" (
  set "PATH=%~dp0third_party\ffmpeg;%PATH%"
  set "AUDIO2FAMI_FFMPEG=%~dp0third_party\ffmpeg\ffmpeg.exe"
)
if exist "%USERPROFILE%\.dotnet\dotnet.exe" (
  set "DOTNET_ROOT=%USERPROFILE%\.dotnet"
  set "PATH=%USERPROFILE%\.dotnet;%PATH%"
)
if exist "%~dp0third_party\FamiStudio\" set "AUDIO2FAMI_FAMISTUDIO=%~dp0third_party\FamiStudio"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m audio2fami %*
  exit /b %ERRORLEVEL%
)
echo 还没有虚拟环境。请先双击 setup.cmd 或在 PowerShell 里运行:
echo   powershell -ExecutionPolicy Bypass -File setup.ps1
exit /b 1
