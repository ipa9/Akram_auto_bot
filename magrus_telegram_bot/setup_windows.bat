@echo off
cd /d "%~dp0"

echo.
echo ======================================
echo      MAGRUS TELEGRAM BOT SETUP
echo ======================================
echo.

echo Checking Python...

where py >nul 2>nul

if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    goto python_found
)

where python >nul 2>nul

if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto python_found
)

echo.
echo ERROR: Python 3 not found.
echo Please install Python 3.
echo.
pause
exit /b 1

:python_found

echo.
echo Python found:
%PYTHON_CMD% --version

if not exist "bot.py" (
    echo.
    echo ERROR: bot.py not found.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo.
    echo ERROR: requirements.txt not found.
    pause
    exit /b 1
)

if not exist "service_account.json" (
    echo.
    echo WARNING: service_account.json not found.
    echo Google Sheets may not work.
    echo.
)

echo.
echo Creating virtual environment...

if not exist ".venv" (
    %PYTHON_CMD% -m venv .venv
)

echo.
echo Activating environment...

call .venv\Scripts\activate.bat

echo.
echo Updating pip...

python -m pip install --upgrade pip

echo.
echo Installing dependencies...

python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR installing dependencies.
    pause
    exit /b 1
)

echo.
echo Checking dependencies...

python -m pip check

echo.
echo Checking bot.py...

python -m py_compile bot.py

if errorlevel 1 (
    echo.
    echo ERROR in bot.py.
    pause
    exit /b 1
)

echo.
echo ======================================
echo        INSTALLATION COMPLETE
echo ======================================
echo.
echo Now run:
echo start_windows.bat
echo.

pause