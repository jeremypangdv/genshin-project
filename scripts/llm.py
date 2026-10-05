"""Get a reply from any OpenAI-compatible chat API: Ollama, DeepSeek or Claude.

Which one is used is "active" in config/llm.json, so moving from the local
test model to an API is a config change, not a code change. API keys come
from the environment variable named by "api_key_env", never from the file.
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
    name = cfg["active"]
    p = cfg["providers"][name]
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
        "temperature": p.get("temperature", 0.8),
    }
    req = urllib.request.Request(f"{p['base_url'].rstrip('/')}/chat/completions",
                                 data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{name} 回傳錯誤：{e.read().decode('utf-8', 'replace')}") from None
    except urllib.error.URLError as e:
        hint = "（Ollama 有沒有開？）" if name == "ollama" else ""
        raise RuntimeError(f"連不上 {name}：{e.reason}{hint}") from None
    text = data["choices"][0]["message"].get("content") or ""
    return THINK.sub("", text).strip()
