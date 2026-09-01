@echo off
cd /d "%~dp0"

echo.
echo ======================================
echo        MAGRUS TELEGRAM BOT
echo ======================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Bot is not installed yet.
    echo.
    echo First run:
    echo setup_windows.bat
    echo.
    pause
    exit /b 1
)

if not exist "bot.py" (
    echo ERROR: bot.py not found.
    pause
    exit /b 1
)

echo Starting bot...
echo.
echo Press CTRL+C to stop.
echo.

".venv\Scripts\python.exe" bot.py

echo.
echo Bot stopped.
echo.

pause