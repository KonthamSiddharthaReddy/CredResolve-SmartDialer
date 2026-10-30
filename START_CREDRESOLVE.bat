@echo off
setlocal enabledelayedexpansion

title CredResolve SmartDialer Launcher

echo =====================================================================
echo  CredResolve SmartDialer - One-Click Launcher
echo =====================================================================
echo.

:: 1. Detect project root directory using BAT file location
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "RUN_DIR=%PROJECT_DIR%.run"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"

:: 2. Configure environment paths for local uv and Node.js
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

set "NODE_DIR="
where node.exe >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%n in ('where node.exe 2^>nul') do (
        if not defined NODE_DIR (
            set "NODE_DIR=%%~dpn"
            set "PATH=!NODE_DIR!;!PATH!"
        )
    )
)

:: Verify uv
set "HAS_UV=0"
where uv.exe >nul 2>&1
if %errorlevel% equ 0 set "HAS_UV=1"

:: Verify node
set "HAS_NODE=0"
where node.exe >nul 2>&1
if %errorlevel% equ 0 set "HAS_NODE=1"

:: Verify npm
set "HAS_NPM=0"
where npm.exe >nul 2>&1
if %errorlevel% equ 0 (
    set "HAS_NPM=1"
) else (
    where npm.cmd >nul 2>&1
    if %errorlevel% equ 0 (
        set "HAS_NPM=1"
    ) else (
        if defined NODE_DIR if exist "!NODE_DIR!npm.exe" (
            set "PATH=!NODE_DIR!;!PATH!"
            set "HAS_NPM=1"
        )
    )
)

if %HAS_UV% equ 0 (
    echo [ERROR] 'uv' was not found on PATH or in %%USERPROFILE%%\.local\bin.
    echo Please install uv from https://docs.astral.sh/uv/
    echo.
    pause
    exit /b 1
)

if %HAS_NODE% equ 0 (
    echo [ERROR] Node.js was not found on PATH.
    echo Please install Node.js 18+ from https://nodejs.org/
    echo.
    pause
    exit /b 1
)

if %HAS_NPM% equ 0 (
    echo [ERROR] 'npm' was not found on PATH.
    echo Please ensure npm is installed and added to PATH.
    echo.
    pause
    exit /b 1
)

echo [OK] All system prerequisites verified: uv, Node.js, and npm are available.
echo.

:: 3. Check and install dependencies only if missing
if not exist "%PROJECT_DIR%.venv" (
    echo [INFO] Python virtual environment missing. Setting up .venv...
    uv venv .venv --python 3.12
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create Python virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Installing backend dependencies...
    uv pip install -r backend/requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install backend dependencies.
        pause
        exit /b 1
    )
) else (
    echo [OK] Python virtual environment ready: .venv
)

if not exist "%PROJECT_DIR%frontend\node_modules" (
    echo [INFO] Frontend node_modules missing. Running npm install...
    pushd "%PROJECT_DIR%frontend"
    call npm install
    popd
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
) else (
    echo [OK] Frontend dependencies ready: node_modules
)

echo.
echo ---------------------------------------------------------------------
echo  Starting Services
echo ---------------------------------------------------------------------

:: 4. Start FastAPI Backend
curl.exe -s -m 1 http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [1/3] Backend is ALREADY RUNNING on http://localhost:8000. Skipping launch.
) else (
    echo [1/3] Starting FastAPI Backend on port 8000...
    powershell -NoProfile -Command "(Start-Process cmd.exe -ArgumentList '/k title CredResolve_Backend && uv run python backend/run_server.py' -WorkingDirectory '%PROJECT_DIR%' -PassThru).Id | Out-File -FilePath '%RUN_DIR%\backend.pid' -Encoding ascii -NoNewline"
    
    echo       Waiting for Backend to become healthy...
    set "BACKEND_READY=0"
    for /l %%i in (1,1,25) do (
        if !BACKEND_READY! equ 0 (
            timeout /t 1 /nobreak >nul 2>&1
            curl.exe -s -m 1 http://127.0.0.1:8000/health >nul 2>&1
            if !errorlevel! equ 0 (
                set "BACKEND_READY=1"
            )
        )
    )
    if !BACKEND_READY! equ 1 (
        echo       [OK] Backend is healthy and ready on port 8000.
    ) else (
        echo       [WARN] Backend is taking longer than usual to initialize. Continuing...
    )
)

:: 5. Start React/Vite Frontend
set "FRONTEND_PORT=3000"
curl.exe -s -m 1 http://localhost:3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo [2/3] Frontend is ALREADY RUNNING on http://localhost:3000. Skipping launch.
) else (
    echo [2/3] Starting React/Vite Frontend...
    powershell -NoProfile -Command "(Start-Process cmd.exe -ArgumentList '/k title CredResolve_Frontend && npm run dev' -WorkingDirectory '%PROJECT_DIR%frontend' -PassThru).Id | Out-File -FilePath '%RUN_DIR%\frontend.pid' -Encoding ascii -NoNewline"
    
    echo       Waiting for Frontend dev server to bind...
    set "FRONTEND_READY=0"
    for /l %%j in (1,1,15) do (
        if !FRONTEND_READY! equ 0 (
            timeout /t 1 /nobreak >nul 2>&1
            curl.exe -s -m 1 http://localhost:3000 >nul 2>&1
            if !errorlevel! equ 0 (
                set "FRONTEND_READY=1"
                set "FRONTEND_PORT=3000"
            ) else (
                curl.exe -s -m 1 http://localhost:3001 >nul 2>&1
                if !errorlevel! equ 0 (
                    set "FRONTEND_READY=1"
                    set "FRONTEND_PORT=3001"
                )
            )
        )
    )
    if !FRONTEND_READY! equ 1 (
        echo       [OK] Frontend is responding on port !FRONTEND_PORT!.
    ) else (
        echo       [INFO] Frontend server initialized.
    )
)

:: 6. Open Browser
echo [3/3] Opening SmartDialer Dashboard in browser...
start http://localhost:!FRONTEND_PORT!

echo.
echo =====================================================================
echo  CredResolve SmartDialer is RUNNING
echo.
echo   * Web Dashboard  : http://localhost:!FRONTEND_PORT!
echo   * Backend API    : http://localhost:8000
echo   * Swagger Docs   : http://localhost:8000/docs
echo   * Health Check   : http://localhost:8000/health
echo.
echo  Controls:
echo   - [S] Stop all services safely
echo   - [C] Check system diagnostics
echo   - [R] Restart services
echo   - [Q] Quit launcher (keeps services running in background)
echo =====================================================================
echo.

:MENU_LOOP
set "USER_CHOICE="
set /p "USER_CHOICE=Select option [S/C/R/Q] or press Enter to exit: "
if defined USER_CHOICE set "USER_CHOICE=!USER_CHOICE: =!"
if "!USER_CHOICE!"=="" (
    echo Launcher exited. Background services remain active.
    exit /b 0
)
if /i "!USER_CHOICE!"=="S" (
    call "%PROJECT_DIR%STOP_CREDRESOLVE.bat"
    exit /b 0
)
if /i "!USER_CHOICE!"=="C" (
    call "%PROJECT_DIR%CHECK_CREDRESOLVE.bat"
    goto MENU_LOOP
)
if /i "!USER_CHOICE!"=="R" (
    echo Restarting services...
    call "%PROJECT_DIR%STOP_CREDRESOLVE.bat"
    timeout /t 2 /nobreak >nul
    call "%PROJECT_DIR%START_CREDRESOLVE.bat"
    exit /b 0
)
if /i "!USER_CHOICE!"=="Q" (
    echo Launcher exited. Background services remain active.
    exit /b 0
)
echo Invalid option '!USER_CHOICE!'.
goto MENU_LOOP
