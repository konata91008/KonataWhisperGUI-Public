@echo off
call "%~dp0..\Start_Windows.bat" --check-updates %*
exit /b %errorlevel%
