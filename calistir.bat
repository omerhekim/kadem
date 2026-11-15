@echo off
rem KADEM - kaynaktan calistirma (Python kurulu bilgisayar icin)
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto kur
".venv\Scripts\python.exe" -c "import numpy, scipy, pandas, openpyxl, xlsxwriter" >nul 2>&1
if not errorlevel 1 goto calistir
echo Yeni surum icin eksik paketler kuruluyor (internet gerekir)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if not errorlevel 1 goto calistir
echo Paketler kurulamadi. Internet baglantisini kontrol edip tekrar deneyin.
pause
exit /b 1
:kur
echo Ilk calistirma: Python ortami hazirlaniyor (bir kez, internet gerekir)...
py -3 -m venv .venv >nul 2>&1
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Python bulunamadi. https://www.python.org adresinden Python 3.10 ya da daha yenisini kurun
  echo ^(kurulumda "Add python.exe to PATH" kutusunu isaretleyin^) ve bu dosyayi tekrar calistirin.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Paketler kurulamadi. Internet baglantisini kontrol edip tekrar deneyin.
  rmdir /s /q .venv
  pause
  exit /b 1
)
:calistir
start "" ".venv\Scripts\pythonw.exe" -m kadem
