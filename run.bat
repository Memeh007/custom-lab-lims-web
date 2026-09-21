@echo off
cd /d "%~dp0"
title Custom Lab LIMS
echo.
echo  Custom Lab LIMS (FastAPI)
echo  ========================
echo.

set "PY=python"
where python >nul 2>&1 || set "PY=py -3"

if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv venv
  if errorlevel 1 (
    echo.
    echo FAILED to create venv. Install Python 3.12+ from python.org and retry.
    pause
    exit /b 1
  )
)

echo Installing / updating packages...
"venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo FAILED to install requirements.
  pause
  exit /b 1
)

set PORT=8765
echo.
echo Starting server on http://127.0.0.1:%PORT%
echo Leave this window open. Press Ctrl+C to stop.
echo.
start "" "http://127.0.0.1:%PORT%/"
"venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port %PORT%
if errorlevel 1 (
  echo.
  echo Server exited with an error.
  pause
)
