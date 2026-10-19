@echo off
chcp 65001 >nul
title agyred - GitHub Repo Adapter
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [HATA] Python bulunamadi! Lutfen Python'in kurulu ve PATH'e ekli oldugundan emin olun.
    pause
    exit /b 1
)

python adapt.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [HATA] Bir sorun olustu.
    pause
)
