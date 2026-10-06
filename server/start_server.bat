@echo off
rem ASCII only: cmd misreads lines when a .bat file contains Chinese (UTF-8)
title LLM Server
set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe

if not exist "%OLLAMA_EXE%" (
    echo Ollama is not installed. Run install_server.bat first.
    pause
    exit /b
)

rem The Ollama that starts with Windows only listens to this computer:
rem close it and start again with the settings below
taskkill /f /im "ollama app.exe" >nul 2>&1
taskkill /f /im ollama.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul

rem Let other computers connect; keep the model in VRAM; 8192-token context
set OLLAMA_HOST=0.0.0.0:11434
set OLLAMA_KEEP_ALIVE=-1
set OLLAMA_CONTEXT_LENGTH=8192

echo This computer's IP. Put it in server.base_url in config/llm.json on the chat computer:
ipconfig | findstr /c:"IPv4"
echo.
echo Server is running. Close this window to stop it.
echo.
"%OLLAMA_EXE%" serve
pause
