@echo off
call "%~dp0..\Start_Windows.bat" --setup %*
exit /b %errorlevel%
