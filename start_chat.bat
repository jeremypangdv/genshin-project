@echo off
chcp 65001 >nul
title Freminet Chat
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem Ollama 沒開的話，在背景開起來
curl -s -o nul http://127.0.0.1:11434 || (
    echo 正在啟動 Ollama…
    start "" /min ollama serve
)

rem 伺服器開起來後自動打開瀏覽器
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"

python scripts\app.py

echo.
echo 聊天伺服器已經關閉。
pause
