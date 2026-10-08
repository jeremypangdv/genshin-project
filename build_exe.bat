@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 做出 Freminet Chat.exe（放在這個資料夾，雙擊就能聊天）
python -m pip install -q pyinstaller pillow

rem 圖示用菲米尼的頭像；沒有頭像就用預設圖示
set ICON=
if not exist build mkdir build
if exist characters\freminet.jpg (
    python -c "from PIL import Image; Image.open('characters/freminet.jpg').convert('RGBA').resize((256,256)).save('build/freminet.ico', sizes=[(256,256),(64,64),(32,32),(16,16)])"
    set ICON=--icon "%CD%\build\freminet.ico"
)

python -m PyInstaller --onefile --noconsole --name "Freminet Chat" %ICON% --distpath . --workpath build --specpath build scripts\launcher.py
echo.
echo 完成：Freminet Chat.exe
pause
