@echo off
setlocal enabledelayedexpansion

title CredResolve SmartDialer - Stop Services

echo =====================================================================
echo  CredResolve SmartDialer - Shutting Down Services
echo =====================================================================
echo.

set "PROJECT_DIR=%~dp0"
set "RUN_DIR=%PROJECT_DIR%.run"

:: 1. Stop Backend via PID
if exist "%RUN_DIR%\backend.pid" (
    set /p B_PID=<"%RUN_DIR%\backend.pid"
    if defined B_PID (
        set "B_PID=!B_PID: =!"
        echo  [1/2] Terminating Backend process tree: PID !B_PID!...
        taskkill /F /T /PID !B_PID! >nul 2>&1
        if !errorlevel! equ 0 (
            echo        Backend process tree terminated.
        ) else (
            echo        Backend process was not active.
        )
        del /f /q "%RUN_DIR%\backend.pid" >nul 2>&1
    )
)

:: 2. Stop Frontend via PID
if exist "%RUN_DIR%\frontend.pid" (
    set /p F_PID=<"%RUN_DIR%\frontend.pid"
    if defined F_PID (
        set "F_PID=!F_PID: =!"
        echo  [2/2] Terminating Frontend process tree: PID !F_PID!...
        taskkill /F /T /PID !F_PID! >nul 2>&1
        if !errorlevel! equ 0 (
            echo        Frontend process tree terminated.
        ) else (
            echo        Frontend process was not active.
        )
        del /f /q "%RUN_DIR%\frontend.pid" >nul 2>&1
    )
)

:: 3. Target uniquely titled launcher windows in case PID file was lost
taskkill /F /FI "WINDOWTITLE eq CredResolve_Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq CredResolve_Frontend*" >nul 2>&1

:: 4. Verify Port Status
echo.
echo ---------------------------------------------------------------------
echo  Verifying Service Shutdown
echo ---------------------------------------------------------------------

timeout /t 1 /nobreak >nul 2>&1

curl.exe -s -m 1 http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo  [OK] Backend Service  : Successfully stopped. Port 8000 released.
) else (
    echo  [WARN] Backend is still responding on port 8000.
)

curl.exe -s -m 1 http://localhost:3000 >nul 2>&1
if %errorlevel% neq 0 (
    echo  [OK] Frontend Service : Successfully stopped. Port 3000 released.
) else (
    echo  [WARN] Frontend is still responding on port 3000.
)

echo.
echo =====================================================================
echo  CredResolve SmartDialer services have been stopped.
echo  You can restart anytime by running START_CREDRESOLVE.bat
echo =====================================================================
echo.
timeout /t 2 >nul 2>&1
