@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "AUDIO2FAMI_OPEN_BROWSER=1"
echo 启动网页界面 http://127.0.0.1:43187 ...
call "%~dp0audio2fami.cmd" ui --host 127.0.0.1 --port 43187
