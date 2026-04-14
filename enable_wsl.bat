@echo off
chcp 65001 >nul
echo ==========================================
echo  ВКЛЮЧЕНИЕ WSL ДЛЯ DOCKER
echo ==========================================
echo.
echo Требуются права администратора!
echo.

:: Enable WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

:: Enable Virtual Machine Platform  
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

echo.
echo ==========================================
echo  Готово! Перезагрузите компьютер.
echo  После перезагрузки Docker будет работать.
echo ==========================================
pause
