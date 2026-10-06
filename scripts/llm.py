"""Get a reply from any OpenAI-compatible chat API: Ollama, DeepSeek or Claude.

Which one is used is "active" in config/llm.json, so moving from the local
test model to an API is a config change, not a code change. API keys come
from the environment variable named by "api_key_env", never from the file.
If the active one fails (no credit, no network) and "fallback" names another,
the reply comes from that one instead, without the chat noticing.
Uses only the standard library.
"""

import json
import os
import re
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


def chat(messages):
    cfg = load_config()
    name, fallback = cfg["active"], cfg.get("fallback")
    try:
        return call(name, messages)
    except RuntimeError as e:
        if not fallback or fallback == name:
            raise
        # 只在黑色視窗留記錄，聊天介面不會顯示
        print(f"{name} 失敗，這則改用 {fallback}：{e}")
        return call(fallback, messages)


def trim(messages, turns):
    """Keep the system prompt and only the last `turns` turns, for models with a small context."""
    head = [m for m in messages[:1] if m["role"] == "system"]
    tail = messages[len(head):][-(turns * 2 + 1):]
    while len(tail) > 1 and tail[0]["role"] != "user":
        tail = tail[1:]
    return head + tail


def call(name, messages):
    p = load_config()["providers"][name]
    if p.get("history_turns"):
        messages = trim(messages, p["history_turns"])
    if p.get("no_think") and messages and messages[0]["role"] == "system":
        # Qwen3 混合模型看到 /no_think 就不思考，不然會花光 max_tokens 回覆變空白
        messages = [{**messages[0], "content": messages[0]["content"] + "\n/no_think"}] + messages[1:]
    headers = {"Content-Type": "application/json"}
    if p.get("api_key_env"):
        key = os.environ.get(p["api_key_env"])
        if not key:
            raise RuntimeError(f"沒有設定環境變數 {p['api_key_env']}")
        headers["Authorization"] = f"Bearer {key}"
    body = {
        "model": p["model"],
        "messages": messages,
        "max_tokens": p.get("max_tokens", 300),
    }
    # Sonnet 5.5 不接受設定 temperature，所以只在 config 裏有寫的時候才傳
    if "temperature" in p:
        body["temperature"] = p["temperature"]
    req = urllib.request.Request(f"{p['base_url'].rstrip('/')}/chat/completions",
                                 data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{name} 回傳錯誤：{e.read().decode('utf-8', 'replace')}") from None
    except urllib.error.URLError as e:
        hint = {"ollama": "（Ollama 有沒有開？）", "server": "（另一部電腦的 start_server.bat 有沒有開？IP 對不對？）"}.get(name, "")
        raise RuntimeError(f"連不上 {name}：{e.reason}{hint}") from None
    text = data["choices"][0]["message"].get("content") or ""
    return THINK.sub("", text).strip()
