@echo off
rem Start Blockplan on Windows. The first run sets everything up.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Blockplan needs Python 3.10 or newer. Install it from https://www.python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist .venv (
  echo First run: setting up, this takes a minute...
  python -m venv .venv
  .venv\Scripts\python -m pip install --quiet --upgrade pip
  .venv\Scripts\python -m pip install --quiet -r requirements.txt
  copy /y requirements.txt .venv\.requirements >nul
)

rem After an update, install anything new.
fc /b requirements.txt .venv\.requirements >nul 2>nul
if errorlevel 1 (
  echo Installing updates...
  .venv\Scripts\python -m pip install --quiet -r requirements.txt
  copy /y requirements.txt .venv\.requirements >nul
)

if not exist .env copy .env.example .env >nul

echo Blockplan is starting. Close this window to stop it.
.venv\Scripts\python -m app.main
pause
