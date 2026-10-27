@echo off
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0genesis_quiescent_eco.py" install
) else (
  python "%~dp0genesis_quiescent_eco.py" install
)
echo.
echo GENESIS QUIESCENT ECO install finished. Review the JSON verdict above.
pause
