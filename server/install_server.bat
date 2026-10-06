@echo off
chcp 65001 >nul
title 安裝 LLM 伺服器
cd /d "%~dp0"

rem 想換模型就改這裏，start_server.bat 不用跟着改
set MODEL=qwen3:14b
set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe

rem 開防火牆要管理員權限，不是的話自己重新用管理員身份開
net session >nul 2>&1 || (
    echo 需要管理員權限，請在彈出的視窗按「是」。
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

if exist "%OLLAMA_EXE%" (
    echo Ollama 已經安裝。
) else (
    echo 正在下載 Ollama…
    curl -L -o "%TEMP%\OllamaSetup.exe" https://ollama.com/download/OllamaSetup.exe || goto fail
    echo 正在安裝 Ollama（安裝視窗會自己完成）…
    "%TEMP%\OllamaSetup.exe" /SILENT || goto fail
    del "%TEMP%\OllamaSetup.exe"
)

rem 剛裝完 Ollama 可能還沒開好，等它回應才下載模型
echo 等待 Ollama 啟動…
:wait
curl -s -o nul http://127.0.0.1:11434 && goto ready
start "" /min "%OLLAMA_EXE%" serve
timeout /t 3 >nul
goto wait
:ready

echo 正在下載模型 %MODEL%（約 9GB，要等一陣子）…
"%OLLAMA_EXE%" pull %MODEL% || goto fail

echo 開放防火牆 11434 端口（只限區域網絡）…
netsh advfirewall firewall delete rule name="Ollama LLM Server" >nul 2>&1
netsh advfirewall firewall add rule name="Ollama LLM Server" dir=in action=allow protocol=TCP localport=11434 profile=private >nul || goto fail

echo.
echo 安裝完成。之後雙擊 start_server.bat 開伺服器。
echo 注意：Windows 的網絡要設成「私人網絡」，另一部電腦才連得到。
pause
exit /b

:fail
echo.
echo 安裝失敗，請看上面的錯誤訊息。
pause
