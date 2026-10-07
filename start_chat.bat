@echo off
chcp 65001 >nul
title Freminet Chat
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem 用這部電腦的模型時，Ollama 沒開的話，在背景開起來；模型一直留在記憶體，不會閒置 5 分鐘就被卸載
rem 用另一部電腦（config/llm.json 的 active 是 server）就不用，這部也不用裝 Ollama
set OLLAMA_KEEP_ALIVE=-1
python scripts\llm.py --is-local && (
    curl -s -o nul http://127.0.0.1:11434 || (
        echo 正在啟動 Ollama…
        start "" /min ollama serve
    )
)

rem 模型載入、預熱完 app.py 會自己打開瀏覽器
python scripts\app.py

echo.
echo 聊天伺服器已經關閉。
pause
