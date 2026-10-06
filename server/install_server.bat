@echo off
rem ASCII only: cmd misreads lines when a .bat file contains Chinese (UTF-8)
title Install LLM server
cd /d "%~dp0"

rem Change the model here; start_server.bat does not need to change
set MODEL=qwen3:14b
set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe

rem The firewall rule needs admin, so relaunch as admin if needed.
rem The path goes through an env var so spaces or ' in folder names are fine.
set "SELF=%~f0"
net session >nul 2>&1 || (
    echo Needs admin rights. Click "Yes" in the popup.
    powershell -NoProfile -Command "Start-Process -FilePath $env:SELF -Verb RunAs"
    exit /b
)

if exist "%OLLAMA_EXE%" (
    echo Ollama is already installed.
) else (
    echo Downloading Ollama...
    curl -fL -o "%TEMP%\OllamaSetup.exe" https://ollama.com/download/OllamaSetup.exe || goto fail
    echo Installing Ollama, please wait...
    "%TEMP%\OllamaSetup.exe" /SILENT || goto fail
)
if not exist "%OLLAMA_EXE%" (
    echo Cannot find %OLLAMA_EXE%
    goto fail
)

rem Ollama may not be up right after installing: start it once, wait up to 60 seconds
echo Waiting for Ollama to start...
curl -s -o nul http://127.0.0.1:11434 || start "" /min "%OLLAMA_EXE%" serve
set /a TRIES=0
:wait
curl -s -o nul http://127.0.0.1:11434 && goto ready
set /a TRIES+=1
if %TRIES% geq 20 (
    echo Ollama did not start within 60 seconds.
    goto fail
)
ping -n 4 127.0.0.1 >nul
goto wait
:ready

echo Downloading %MODEL% (about 9GB, this takes a while)...
"%OLLAMA_EXE%" pull %MODEL% || goto fail

rem Only computers on the same network, or on your Tailscale (100.64.0.0/10), can
rem connect. Any profile, because Windows marks new Wi-Fi as Public by default. Naming the program stops Windows from
rem showing its own firewall popup, where a wrong click blocks Ollama.
echo Opening firewall port 11434 for the local network and Tailscale...
netsh advfirewall firewall delete rule name="Ollama LLM Server" >nul 2>&1
netsh advfirewall firewall add rule name="Ollama LLM Server" dir=in action=allow program="%OLLAMA_EXE%" protocol=TCP localport=11434 remoteip=localsubnet,100.64.0.0/10 profile=any >nul || goto fail

echo.
echo Done. From now on, double-click start_server.bat to run the server.
pause
exit /b

:fail
echo.
echo Install failed. See the error above.
pause
