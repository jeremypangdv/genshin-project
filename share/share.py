"""Share the chat with friends through ngrok: run 分享給朋友.bat and send them the link it prints.

Starts Ollama if needed, then app.py --share (no window, stays up while this
window is open), then an ngrok tunnel to port 5000 with the ngrok.exe at NGROK.
The link is copied to the clipboard.
Closing this window stops everything it started.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
BUNDLED_PYTHON = PROJECT / "GPT-SoVITS" / "runtime" / "python.exe"
BUNDLED_OLLAMA = PROJECT / "ollama" / "ollama.exe"
PYTHON = str(BUNDLED_PYTHON) if BUNDLED_PYTHON.is_file() else sys.executable
NGROK = Path(r"C:\ngrok\ngrok.exe")
APP_URL = "http://127.0.0.1:5000"


def up(url):
    try:
        urllib.request.urlopen(url, timeout=1)
        return True
    except OSError:
        return False


def ready():
    try:
        return json.load(urllib.request.urlopen(f"{APP_URL}/api/ready", timeout=2))["ready"]
    except OSError:
        return False


def has_token():
    config = Path(os.environ["LOCALAPPDATA"]) / "ngrok" / "ngrok.yml"
    return config.is_file() and "authtoken" in config.read_text(encoding="utf-8")


def public_url(ngrok):
    # ngrok 開好後，網址在它本機的 4040 介面上
    for _ in range(30):
        if ngrok.poll() is not None:
            return None
        try:
            tunnels = json.load(urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1))["tunnels"]
            url = next((t["public_url"] for t in tunnels if t["public_url"].startswith("https")), None)
            if url:
                return url
        except OSError:
            pass
        time.sleep(1)
    return None


def main():
    if up(f"{APP_URL}/api/ready"):
        print("聊天程式已經開着（Freminet Chat.exe）。請先關掉那個視窗，再重新打開這個。")
        return
    if not NGROK.is_file():
        print(f"找不到 {NGROK}，請把 ngrok.exe 放在那裏")
        return
    if not has_token():
        print("ngrok 還沒登入。到 https://dashboard.ngrok.com/get-started/your-authtoken 複製 token，然後在這裏貼上：")
        token = input("> ").strip()
        subprocess.run([str(NGROK), "config", "add-authtoken", token], check=True)

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "OLLAMA_KEEP_ALIVE": "-1"}
    ollama, ollama_url = "ollama", "http://127.0.0.1:11434"
    if BUNDLED_OLLAMA.is_file():
        ollama, ollama_url = str(BUNDLED_OLLAMA), "http://127.0.0.1:11435"
        env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_MODELS=str(PROJECT / "ollama" / "models"))

    started = []
    try:
        local = subprocess.run([PYTHON, "scripts/llm.py", "--is-local"], cwd=PROJECT, env=env).returncode == 0
        if local and not up(ollama_url):
            started.append(subprocess.Popen([ollama, "serve"], env=env,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        log = open(PROJECT / "app.log", "w", encoding="utf-8")
        app = subprocess.Popen([PYTHON, "scripts/app.py", "--share"], cwd=PROJECT, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
        started.append(app)
        ngrok = subprocess.Popen([str(NGROK), "http", "5000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started.append(ngrok)

        url = public_url(ngrok)
        if not url:
            print("ngrok 開不起來。可能是 token 不對，或另一個 ngrok 已經在跑。")
            return
        # 模型載入、預熱完才給連結，朋友打開就能直接聊，第一則訊息也不會特別慢
        print("模型載入和預熱中（約一兩分鐘）…", end="", flush=True)
        while not ready():
            if app.poll() is not None:
                print(f"\n聊天程式出錯了，記錄在：{PROJECT / 'app.log'}")
                return
            time.sleep(2)
        print(" 好了")
        subprocess.run("clip", input=url.encode(), shell=True)
        print()
        print("  分享這個連結給朋友（已經複製好了）：")
        print(f"\n      {url}\n")
        print("  朋友第一次打開會看到 ngrok 的提示頁，按 Visit Site 就可以。")
        print("  這個視窗要一直開着；關掉它，朋友就連不上了。")
        while app.poll() is None and ngrok.poll() is None:
            time.sleep(2)
        print("聊天程式或 ngrok 停了。" + (f"記錄在：{PROJECT / 'app.log'}" if app.poll() else ""))
    except KeyboardInterrupt:
        pass
    finally:
        for p in started:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)


main()
