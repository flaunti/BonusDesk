@echo off
setlocal
cd /d "%~dp0"

call build_windows.bat
if errorlevel 1 exit /b 1

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo.
  echo Inno Setup 6 ne naiden. Ustanovi ego s https://jrsoftware.org/isdl.php
  pause
  exit /b 1
)

"%ISCC%" /DMyAppVersion=2.1.0 "installer\BonusDesk.iss"
if errorlevel 1 (
  echo.
  echo Oshibka sborki ustanovshika.
  pause
  exit /b 1
)

echo.
echo Gotovo: installer\output\BonusDesk-Setup-x64.exe
pause
