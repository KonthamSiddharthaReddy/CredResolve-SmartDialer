@echo off
setlocal enabledelayedexpansion

title CredResolve SmartDialer - Environment Health Check

echo =====================================================================
echo  CredResolve SmartDialer - System and Environment Diagnostics
echo =====================================================================
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set "STATUS_OK=1"

:: 1. Detect uv / Python
set "UV_CMD="
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where uv.exe >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('uv --version 2^>nul') do (
        echo  [OK] uv Package Manager : %%v
        set "UV_CMD=uv"
    )
) else (
    where python.exe >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%v in ('python --version 2^>nul') do (
            echo  [OK] Python Runtime     : %%v
            set "UV_CMD=python"
        )
    ) else (
        echo  [FAIL] Python / uv       : Neither 'uv' nor 'python' was found on PATH.
        set "STATUS_OK=0"
    )
)

:: 2. Detect Node.js
set "NODE_DIR="
where node.exe >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%n in ('where node.exe 2^>nul') do (
        if not defined NODE_DIR (
            set "NODE_DIR=%%~dpn"
            set "PATH=!NODE_DIR!;!PATH!"
        )
    )
    for /f "tokens=*" %%v in ('node -v 2^>nul') do echo  [OK] Node.js Runtime     : %%v
) else (
    echo  [FAIL] Node.js Runtime     : 'node' was not found on PATH.
    set "STATUS_OK=0"
)

:: 3. Detect npm
set "NPM_FOUND=0"
where npm.exe >nul 2>&1
if %errorlevel% equ 0 (
    set "NPM_FOUND=1"
) else (
    where npm.cmd >nul 2>&1
    if %errorlevel% equ 0 (
        set "NPM_FOUND=1"
    ) else (
        if defined NODE_DIR if exist "!NODE_DIR!npm.exe" (
            set "PATH=!NODE_DIR!;!PATH!"
            set "NPM_FOUND=1"
        )
    )
)

if %NPM_FOUND% equ 1 (
    for /f "tokens=*" %%v in ('npm -v 2^>nul') do echo  [OK] npm Package Manager : v%%v
) else (
    echo  [FAIL] npm Package Manager : 'npm' was not found on PATH.
    set "STATUS_OK=0"
)

:: 4. Check Backend Dependencies (.venv)
if exist "%PROJECT_DIR%.venv" (
    echo  [OK] Python Environment  : .venv directory exists
) else (
    echo  [WARN] Python Environment: .venv missing (START_CREDRESOLVE will auto-create)
)

:: 5. Check Frontend Dependencies (node_modules)
if exist "%PROJECT_DIR%frontend\node_modules" (
    echo  [OK] Frontend Dependencies: frontend\node_modules exists
) else (
    echo  [WARN] Frontend Dep.: frontend\node_modules missing (START_CREDRESOLVE will auto-install)
)

:: 6. Check Compiled Frontend Build (dist)
if exist "%PROJECT_DIR%frontend\dist\index.html" (
    echo  [OK] Production Build    : frontend\dist compiled and ready
) else (
    echo  [INFO] Production Build   : frontend\dist not built yet (can run via Vite dev server)
)

echo.
echo ---------------------------------------------------------------------
echo  Service and Port Status Checks
echo ---------------------------------------------------------------------

:: 7. Check Port 8000 (Backend Health)
curl.exe -s -m 2 http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo  [ACTIVE] Backend Service : RUNNING on http://localhost:8000
    echo                            API Docs: http://localhost:8000/docs
) else (
    echo  [STOPPED] Backend Service: Not running on port 8000
)

:: 8. Check Port 3000 / 3001 (Frontend Dev Server)
curl.exe -s -m 2 http://localhost:3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo  [ACTIVE] Frontend Service: RUNNING on http://localhost:3000
) else (
    curl.exe -s -m 2 http://localhost:3001 >nul 2>&1
    if !errorlevel! equ 0 (
        echo  [ACTIVE] Frontend Service: RUNNING on http://localhost:3001
    ) else (
        echo  [STOPPED] Frontend Service: Not running on port 3000 or 3001
    )
)

echo.
echo =====================================================================
if %STATUS_OK% equ 1 (
    echo  DIAGNOSTICS PASSED: System is ready to run!
    echo  To start the application, double-click START_CREDRESOLVE.bat
    echo  To stop the application, double-click STOP_CREDRESOLVE.bat
) else (
    echo  DIAGNOSTICS FAILED: Please install the missing prerequisites listed above.
)
echo =====================================================================
echo.
pause
