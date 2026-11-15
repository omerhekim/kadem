@echo off
rem KADEM - Windows programi (.exe) olusturma
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  KADEM - .exe olusturuluyor (5-10 dakika surebilir)
echo ============================================================
if exist ".venv-derleme\Scripts\python.exe" goto paketler
py -3 -m venv .venv-derleme >nul 2>&1
if not exist ".venv-derleme\Scripts\python.exe" python -m venv .venv-derleme
if not exist ".venv-derleme\Scripts\python.exe" (
  echo Python bulunamadi. https://www.python.org adresinden Python 3.10+ kurun ve tekrar deneyin.
  pause
  exit /b 1
)
:paketler
".venv-derleme\Scripts\python.exe" -m pip install --upgrade pip
".venv-derleme\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo Paketler kurulamadi. Internet baglantisini kontrol edin.
  pause
  exit /b 1
)
".venv-derleme\Scripts\python.exe" -m PyInstaller --noconfirm --clean KADEM.spec
if errorlevel 1 (
  echo.
  echo HATA: .exe olusturulamadi. Yukaridaki mesajin ekran goruntusunu gonderin.
  pause
  exit /b 1
)
echo.
echo Tamamlandi:  dist\KADEM\KADEM.exe
echo Meslektaslariniza "dist\KADEM" klasorunun tamamini (zip olarak) verin.
explorer "dist\KADEM"
pause
