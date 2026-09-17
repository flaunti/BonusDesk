@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul || goto :nopython
if not exist .venv (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python main.py
exit /b %errorlevel%

:nopython
echo Python ne naiden. Ustanovi Python 3.11 ili 3.12 s python.org i vklyuchi Add Python to PATH.
pause
exit /b 1
