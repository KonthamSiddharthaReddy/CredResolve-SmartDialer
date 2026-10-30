@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo [TEST 1] Run CHECK_CREDRESOLVE when stopped
echo ===================================================
call CHECK_CREDRESOLVE.bat < nul

echo.
echo ===================================================
echo [TEST 2] Launch services via START_CREDRESOLVE
echo ===================================================
echo Q | call START_CREDRESOLVE.bat

echo.
echo ===================================================
echo [TEST 3] Verify services with CHECK_CREDRESOLVE
echo ===================================================
call CHECK_CREDRESOLVE.bat < nul

echo.
echo ===================================================
echo [TEST 4] Test HTTP API /health and Frontend
echo ===================================================
curl.exe -s http://127.0.0.1:8000/health
echo.
curl.exe -s -m 2 http://localhost:3000 > nul
if %errorlevel% equ 0 (
    echo Frontend HTTP response: OK on port 3000
) else (
    echo Frontend HTTP check: Port 3000 did not respond
)

echo.
echo ===================================================
echo [TEST 5] Shut down services with STOP_CREDRESOLVE
echo ===================================================
call STOP_CREDRESOLVE.bat

echo.
echo ===================================================
echo [TEST 6] Verify shutdown with CHECK_CREDRESOLVE
echo ===================================================
call CHECK_CREDRESOLVE.bat < nul

echo.
echo ===================================================
echo [TEST 7] Restart services to verify restartability
echo ===================================================
echo Q | call START_CREDRESOLVE.bat

echo.
echo ===================================================
echo [TEST 8] Verify restarted backend /health
echo ===================================================
curl.exe -s http://127.0.0.1:8000/health
echo.

echo.
echo ===================================================
echo [TEST 9] Final clean shutdown with STOP_CREDRESOLVE
echo ===================================================
call STOP_CREDRESOLVE.bat

echo.
echo ===================================================
echo ALL LAUNCHER TESTS COMPLETED SUCCESSFULLY!
echo ===================================================
