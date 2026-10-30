@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo [PRE-SUBMISSION] 1. START_CREDRESOLVE.bat
echo ========================================================
echo Q | call START_CREDRESOLVE.bat

echo.
echo ========================================================
echo [PRE-SUBMISSION] 2. Run API and Frontend Smoke Tests
echo ========================================================
uv run python scripts/smoke_test_api.py
set "SMOKE_RES=!errorlevel!"

echo.
echo ========================================================
echo [PRE-SUBMISSION] 3. STOP_CREDRESOLVE.bat
echo ========================================================
call STOP_CREDRESOLVE.bat

echo.
echo ========================================================
echo [PRE-SUBMISSION] 4. Verify STOP cleaned up and left ports free
echo ========================================================
call CHECK_CREDRESOLVE.bat < nul

exit /b !SMOKE_RES!
