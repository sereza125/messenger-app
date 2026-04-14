@echo off
chcp 65001 >nul
echo ==========================================
echo  RESTARTING MESSENGER SERVER
echo ==========================================
echo.

:: Kill existing processes
taskkill /F /IM python.exe 2>nul
taskkill /F /IM cloudflared.exe 2>nul
timeout /t 2 >nul

:: Change port to avoid conflicts
set PORT=8025

echo [1/3] Starting server on port %PORT%...
start /B python simple_http_server.py

timeout /t 3 >nul

echo [2/3] Starting cloudflared tunnel...
start /B cmd /c "cloudflared.exe tunnel --url http://localhost:%PORT% 2>&1 | findstr trycloudflare"

timeout /t 5 >nul

echo [3/3] Checking local server...
curl -s http://localhost:%PORT%/simple.html >nul && echo ✅ Server OK || echo ❌ Server failed

echo.
echo ==========================================
echo  Server running on http://localhost:%PORT%
echo  Check window title for Cloudflare URL
echo ==========================================
pause
