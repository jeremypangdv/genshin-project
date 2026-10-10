"""Get a reply from a local model through Ollama's OpenAI-compatible API.

Which one is used is "active" in config/llm.json: "ollama" on this computer
or "server" on the other one, so switching is a config change.
Uses only the standard library.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT / "config" / "llm.json"
THINK = re.compile(r"<think>.*?</think>", re.S)  # Qwen3 等推理模型會先輸出思考過程


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def describe():
    cfg = load_config()
    return f"{cfg['active']} · {cfg['providers'][cfg['active']]['model']}"


def chat(messages, temperature=None):
    return call(load_config()["active"], messages, temperature)


def trim(messages, turns):
    """Keep the system prompt and only the last `turns` turns, for models with a small context."""
    head = [m for m in messages[:1] if m["role"] == "system"]
    tail = messages[len(head):][-(turns * 2 + 1):]
    while len(tail) > 1 and tail[0]["role"] != "user":
        tail = tail[1:]
    return head + tail


def call(name, messages, temperature=None):
    p = load_config()["providers"][name]
    if p.get("history_turns"):
        messages = trim(messages, p["history_turns"])
    body = {
        "model": p["model"],
        "messages": messages,
        "max_tokens": p.get("max_tokens", 300),
    }
    if p.get("no_think"):
        # 讓 qwen3:14b 這類混合模型不思考，不然會花光 max_tokens 回覆變空白。
        # 在提示裏寫 /no_think 實測沒用；2507 版的 qwen3:4b 只會思考，這個也關不掉
        body["reasoning_effort"] = "none"
    if temperature is not None:
        body["temperature"] = temperature  # 查資料這類要穩定的用 0
    elif "temperature" in p:
        body["temperature"] = p["temperature"]
    req = urllib.request.Request(f"{p['base_url'].rstrip('/')}/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{name} 回傳錯誤：{e.read().decode('utf-8', 'replace')}") from None
    except urllib.error.URLError as e:
        hint = {"ollama": "（Ollama 有沒有開？）", "server": "（另一部電腦的 start_server.bat 有沒有開？IP 對不對？）"}.get(name, "")
        raise RuntimeError(f"連不上 {name}：{e.reason}{hint}") from None
    text = data["choices"][0]["message"].get("content") or ""
    return THINK.sub("", text).strip()


def is_local():
    """Whether the active model runs on this computer, so Freminet Chat.exe knows to start Ollama."""
    cfg = load_config()
    url = cfg["providers"][cfg["active"]]["base_url"]
    return any(host in url for host in ("://127.0.0.1", "://localhost"))


if __name__ == "__main__":
    # Freminet Chat.exe（scripts/launcher.py）用：python scripts\llm.py --is-local，本地的話 exit code 0
    if sys.argv[1:] == ["--is-local"]:
        sys.exit(0 if is_local() else 1)
