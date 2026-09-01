@echo off
REM BRM Territory Hub -- download and install the latest version (Windows)
REM Your data folder is never touched.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run
python update.py
goto done

:run
.venv\Scripts\python update.py

:done
echo.
pause
