@echo off
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0genesis_quiescent_eco.py" install --monitor-minutes 2
) else (
  python "%~dp0genesis_quiescent_eco.py" install --monitor-minutes 2
)
echo.
echo GENESIS QUIESCENT ECO install finished. Review the JSON verdict above.
pause
