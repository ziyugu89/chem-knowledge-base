@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 打包氟化工知识库
echo 正在生成可发给同事的压缩包（不含 PDF、不含 .venv）...
python pack.py
if exist "氟化工生产技术知识库.zip" (
    echo 完成：%CD%\氟化工生产技术知识库.zip
) else (
    echo 打包失败。也可手动压缩本文件夹，但请不要把 .venv 打进去。
)
pause
