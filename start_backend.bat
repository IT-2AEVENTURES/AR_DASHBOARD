@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
if %ERRORLEVEL% NEQ 0 pause
