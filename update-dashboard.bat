@echo off
REM Token Dashboard Update Script
REM Runs tracker and sends Discord report

echo ========================================
echo Shadowfax Token Dashboard Update
echo ========================================
echo.

echo [1/2] Running token tracker...
python token_tracker.py
if %errorlevel% neq 0 (
    echo ERROR: Token tracker failed!
    pause
    exit /b 1
)

echo.
echo [2/2] Sending Discord report...
python discord_report.py
if %errorlevel% neq 0 (
    echo WARNING: Discord report failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Update complete!
echo ========================================
echo.
echo Dashboard data updated: usage-data.json
echo Discord report sent to #morning-briefs
echo.
echo Open dashboard: start index.html
echo.
pause
