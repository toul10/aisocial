@echo off
rem AI Social: double-click this file to start (Windows).
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 start.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  python start.py %*
)
if errorlevel 1 pause
exit /b

:nopython
echo.
echo [AI Social] Python 3.10 or newer was not found.
echo Download it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during installation.
echo.
pause
exit /b 1
