@echo off
setlocal

cd /d "%~dp0"

chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python "qt_octopus_pet.py"
if errorlevel 1 (
    echo.
    echo Octopus pet exited with an error.
    pause
)
