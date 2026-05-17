@echo off
cd /d "%~dp0"
echo =======================================================
echo  WEEKLY SWING SETUP SCANNER
echo  Full NSE EQ Universe (~2000+ stocks)
echo  %date%  %time%
echo =======================================================
echo.
echo  Run every Saturday for deep scan.
echo  Expected time: 60-90 minutes.
echo.
echo  Starting scan...
echo.
python scanner.py --top 30 --min-score 50 --workers 4
echo.
echo  Sending Telegram notification...
python telegram_notify.py --top 15
echo.
echo  Done! Check results\ folder for output.
echo.
pause
