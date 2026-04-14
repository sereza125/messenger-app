@echo off
chcp 65001 >nul
echo ==========================================
echo  Starting Messenger Server
echo ==========================================

:: Kill existing processes
taskkill /F /IM python.exe 2>nul
timeout /t 1 >nul

:: Start HTTP server
echo [1/2] Starting HTTP server on port 8012...
start /B python simple_http_server.py

timeout /t 2 >nul

:: Start cloudflared tunnel
echo [2/2] Starting cloudflared tunnel...
echo.
echo Waiting for tunnel URL...
echo.

start /B cmd /c "cloudflared.exe tunnel --url http://localhost:8012 2>&1 | findstr trycloudflare"

timeout /t 5 >nul

echo.
echo ==========================================
echo  Local: http://localhost:8012/simple.html
echo ==========================================
echo.
echo If cloudflared URL appears above, you can share it!
echo Press Ctrl+C to stop
echo.

pause
