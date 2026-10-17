@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 氟化工生产技术知识库
echo.
echo ============================================
echo   氟化工生产技术知识库  （发给别人也可运行）
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有检测到 Python。
    echo 请先安装 Python 3.10 或更高版本：
    echo https://www.python.org/downloads/
    echo 安装时勾选 Add Python to PATH。
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 正在创建虚拟环境，只需第一次等待...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
echo [2/3] 正在安装/检查依赖...
python -m pip install -U pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
)

echo [3/3] 启动知识库，浏览器将自动打开...
echo 关闭本窗口即停止服务。
echo.
python app.py
echo.
pause
