@echo off
REM BRM Territory Hub -- start the app (Windows)
cd /d "%~dp0"

if exist ".venv" goto run

echo Setting up (first run only)...
python -m venv .venv
if errorlevel 1 goto pyerror
.venv\Scripts\pip install --quiet -r requirements.txt

:run
echo Starting BRM Territory Hub...
echo Open http://127.0.0.1:5000 in your browser. Close this window to stop.
.venv\Scripts\python app.py
pause
goto :eof

:pyerror
echo.
echo Could not find Python. Please install it from https://www.python.org/downloads/
echo and make sure to check "Add Python to PATH" during setup, then try again.
pause
