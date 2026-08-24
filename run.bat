@echo off
REM BRM Territory Hub -- start the app (Windows)
cd /d "%~dp0"

if not exist ".venv" (
  echo Setting up (first run only)...
  python -m venv .venv
  .venv\Scripts\pip install --quiet -r requirements.txt
)

echo Starting BRM Territory Hub...
echo Open http://127.0.0.1:5000 in your browser. Close this window to stop.
.venv\Scripts\python app.py
pause
