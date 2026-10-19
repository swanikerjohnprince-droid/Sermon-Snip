@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install 64-bit Python 3.11 or 3.12 and enable Add Python to PATH.
  pause
  exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
python app.py
if errorlevel 1 pause
