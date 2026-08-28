@echo off
setlocal
cd /d "%~dp0"

if not exist "instalar.ps1" (
    echo Baixando instalador...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Wulululuu/meus-investimentos/main/pacote-para-amigo/instalar.ps1' -OutFile 'instalar.ps1'"
)

powershell -NoProfile -ExecutionPolicy Bypass -File "instalar.ps1"

echo.
pause
