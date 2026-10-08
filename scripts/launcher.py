"""Freminet Chat.exe: starts Ollama if needed, then the chat app in its own window, with no console window.

Build it with build_exe.bat; the exe goes in the project folder and runs
python scripts/app.py --window, which opens the chat in its own window.
Everything app.py prints goes to app.log.
"""

import ctypes
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
if PROJECT.name == "scripts":
    PROJECT = PROJECT.parent
HIDDEN = subprocess.CREATE_NO_WINDOW


def up(url):
    try:
        urllib.request.urlopen(url, timeout=1)
        return True
    except OSError:
        return False


def error(text):
    ctypes.windll.user32.MessageBoxW(None, text, "Freminet Chat", 0x10)


def main():
    if up("http://127.0.0.1:5000/api/ready"):
        # 已經在跑了，叫它多開一個視窗就好
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5000/api/open", method="POST"), timeout=5)
        return
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
           # 模型一直留在記憶體，不會閒置 5 分鐘就被卸載
           "OLLAMA_KEEP_ALIVE": "-1"}
    try:
        local = subprocess.run(["python", "scripts/llm.py", "--is-local"], cwd=PROJECT, env=env,
                               creationflags=HIDDEN).returncode == 0
    except FileNotFoundError:
        error("找不到 Python，請先安裝，並加進 PATH")
        return
    # 用這部電腦的模型時，Ollama 沒開的話在背景開起來；用另一部電腦（server）就不用
    if local and not up("http://127.0.0.1:11434"):
        try:
            subprocess.Popen(["ollama", "serve"], env=env, creationflags=HIDDEN)
        except FileNotFoundError:
            error("找不到 Ollama，請先安裝")
            return
    log_path = PROJECT / "app.log"
    with open(log_path, "w", encoding="utf-8") as log:
        code = subprocess.run(["python", "scripts/app.py", "--window"], cwd=PROJECT, env=env,
                              stdout=log, stderr=subprocess.STDOUT, creationflags=HIDDEN).returncode
    if code:
        error(f"聊天程式出錯了，記錄在：\n{log_path}")


main()
