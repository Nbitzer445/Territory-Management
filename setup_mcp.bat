@echo off
REM BRM Territory Hub -- connect to Claude Desktop (Windows)
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run
echo Setting up first...
python -m venv .venv
if errorlevel 1 goto pyerror
.venv\Scripts\pip install --quiet -r requirements.txt

:run
.venv\Scripts\python setup_mcp.py
pause
goto :eof

:pyerror
echo.
echo Could not find Python. Install it from https://www.python.org/downloads/
echo and make sure to check "Add Python to PATH" during setup, then try again.
pause
