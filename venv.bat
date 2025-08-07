@echo off
REM Simple virtual environment activation wrapper
SET VENV_DIR=%~dp0.venv
IF NOT EXIST "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)
REM Activate the virtual environment
CALL "%VENV_DIR%\Scripts\activate.bat"