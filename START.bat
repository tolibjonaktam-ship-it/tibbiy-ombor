@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MedStock ERP
echo ==========================================
echo            MedStock ERP
echo   Ombor, sotuv va qaytarish tizimi
echo ==========================================
echo.

REM Python qaysi nom bilan ishlashini aniqlash
set PY=python
%PY% --version >nul 2>&1
if errorlevel 1 set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo [XATO] Python topilmadi!
  echo Python o'rnating: https://www.python.org/downloads/
  echo O'rnatishda "Add Python to PATH" katagiga belgi qo'ying.
  pause
  exit /b
)

echo [1/2] Kerakli kutubxonalar tekshirilmoqda...
%PY% -m pip install -r requirements.txt --quiet
echo.
echo [2/2] Dastur ishga tushmoqda...
echo Brauzer ochiladi: http://localhost:5000
echo Login: admin   Parol: admin123
echo.
echo Bu oynani YOPMANG - dastur shu orqali ishlaydi.
echo To'xtatish uchun: Ctrl+C yoki oynani yoping.
echo.

REM 3 soniyadan keyin brauzerni ochish
start "" cmd /c "timeout /t 3 >nul & start http://localhost:5000"

%PY% server.py
pause
