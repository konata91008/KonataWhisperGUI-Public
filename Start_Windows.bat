@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title TJKSub
"venv\Scripts\python.exe" -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12)" >nul 2>&1
if not errorlevel 1 goto check_packages

for %%V in (3.12 3.11 3.10) do (
    py -%%V -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 (
        set "TJK_PYTHON=py -%%V"
        goto create_venv
    )
)
python -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12) and sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 (
    echo 請先安裝 Python 3.10 - 3.12 Windows x64，然後重新開啟。
    echo https://www.python.org/downloads/windows/
    goto failure
)
set "TJK_PYTHON=python"

:create_venv
if exist "venv" (
    %TJK_PYTHON% -c "from pathlib import Path; import uuid; Path('venv').rename('venv.backup-'+uuid.uuid4().hex[:10])"
    if errorlevel 1 goto failure
)
%TJK_PYTHON% -m venv venv
if errorlevel 1 goto failure

:check_packages
"venv\Scripts\python.exe" -c "import PyQt5, opencc" >nul 2>&1
if not errorlevel 1 goto run_app
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failure

:run_app
"venv\Scripts\python.exe" "WhisperGUI\main.py" %*
if errorlevel 1 goto failure
exit /b 0

:failure
echo 啟動未完成，請查看上方訊息。原有模型及引擎不會被刪除。
pause
exit /b 1
