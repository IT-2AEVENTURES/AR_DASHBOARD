@echo off
setlocal
cd /d "%~dp0\frontend"
set PATH=C:\Program Files\nodejs;%PATH%
npm run dev:lan
