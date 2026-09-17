@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python ne naiden. Ustanovi Python 3.11 ili 3.12 s python.org i vklyuchi Add Python to PATH.
  pause
  exit /b 1
)

if not exist .venv (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --windowed --onedir --name "BonusDesk" --icon "assets\bonusdesk.ico" --version-file "assets\version_info.txt" --add-data "assets;assets" main.py
if errorlevel 1 goto :error

echo.
echo Gotovo: dist\BonusDesk\BonusDesk.exe
pause
exit /b 0

:error
echo.
echo Oshibka sborki. Skopirui tekst vyshe.
pause
exit /b 1
