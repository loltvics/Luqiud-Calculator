@echo off
setlocal

cd /d %~dp0

REM Choose Python launcher
where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py
) else (
  set PY=python
)

echo =========================================
echo   Liquid Calculator - first start check
echo =========================================

%PY% -m pip install -r requirements.txt

echo =========================================
echo   Starting server...
echo =========================================

%PY% app.py

pause
