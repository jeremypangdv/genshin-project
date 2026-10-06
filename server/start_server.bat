@echo off
chcp 65001 >nul
title LLM Server
set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe

rem 開機自動開的 Ollama 只聽本機，先關掉再用下面的設定重開
taskkill /f /im "ollama app.exe" >nul 2>&1
taskkill /f /im ollama.exe >nul 2>&1

rem 讓其他電腦連得到；模型一直留在顯存；上下文 8192 token
set OLLAMA_HOST=0.0.0.0:11434
set OLLAMA_KEEP_ALIVE=-1
set OLLAMA_CONTEXT_LENGTH=8192

echo 這部電腦的 IP（填到聊天電腦 config/llm.json 的 server.base_url）：
ipconfig | findstr /c:"IPv4"
echo.
echo 伺服器運行中，關掉這個視窗就會停止。
echo.
"%OLLAMA_EXE%" serve
pause
