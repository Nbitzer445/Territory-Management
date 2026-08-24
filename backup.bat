@echo off
REM BRM Territory Hub -- back up your data (Windows)
cd /d "%~dp0"
if not exist "data\backups" mkdir "data\backups"
if not exist "data\territory.db" (
  echo No data\territory.db found yet -- nothing to back up.
  goto :end
)
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set DATESTAMP=%%c%%a%%b
set TIMESTAMP=%time::=%
set TIMESTAMP=%TIMESTAMP: =0%
copy "data\territory.db" "data\backups\territory-%DATESTAMP%-%TIMESTAMP%.db"
echo Backed up.
:end
pause
