@echo off
cd /d "%~dp0"
echo =======================================================
echo  WEEKLY SWING SETUP SCANNER  v1  (Production)
echo  Full NSE EQ Universe (~2000+ stocks)
echo  %date%  %time%
echo =======================================================
echo.
echo  Run every Saturday. Expected time: 60-90 min.
echo.

echo [1/3] Running full scan...
python scanner.py --top 30 --min-score 50 --workers 4
if errorlevel 1 (
    echo ERROR: scanner.py failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Generating charts...
python gen_charts.py
if errorlevel 1 (
    echo WARNING: Chart generation failed. Scan results still saved.
)

echo.
echo [3/3] Sending Telegram notification...
python telegram_notify.py --top 15
if errorlevel 1 (
    echo WARNING: Telegram failed. Results still saved.
)

echo.
echo =======================================================
echo  Done at %date% %time%
echo  Results : results\
echo  Charts  : results\charts\
echo =======================================================
echo.
pause
