@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 智能设计工作台启动器 (Smart Design Workbench)

echo ===================================================
echo      正在读取配置并启动工作台...
echo ===================================================

:: 1. 检查配置文件是否存在
if not exist "config.ini" (
    echo [错误] 找不到 config.ini 文件！
    echo 请参考 config.ini.example 创建并配置本地路径。
    pause
    exit /b
)

:: 2. 解析 config.ini 获取 python_path
set "PYTHON_EXE="
for /f "tokens=1* delims==" %%A in ('type config.ini ^| findstr /b "python_path="') do (
    set "PYTHON_EXE=%%B"
    :: 去除空格
    set "PYTHON_EXE=!PYTHON_EXE: =!"
)

if "%PYTHON_EXE%"=="" (
    echo [错误] 配置文件中未定义 python_path。
    pause
    exit /b
)

echo [检测到环境] %PYTHON_EXE%

:: 3. 启动 Flask 应用
:: 直接使用全路径 python 启动 app.py，无需手动 call Scripts\activate
echo 正在启动服务器，请稍后...
echo 访问地址: http://127.0.0.1:5000
echo.

"%PYTHON_EXE%" app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [运行错误] 服务器非正常退出，代码: %ERRORLEVEL%
    pause
)
