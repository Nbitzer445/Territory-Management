@echo off
REM BRM Territory Hub -- back up your data (Windows)
cd /d "%~dp0"

if not exist "data\backups" mkdir "data\backups"
if not exist "data\territory.db" goto nodata

set DATESTAMP=%date:~-4%%date:~-10,2%%date:~-7,2%
set TIMESTAMP=%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
copy "data\territory.db" "data\backups\territory-%DATESTAMP%-%TIMESTAMP%.db"
echo Backed up.
goto end

:nodata
echo No data\territory.db found yet -- nothing to back up.

:end
pause
