"""Get a reply from a local model through Ollama, or from an online API like Gemini.

Which one is used is "active" in config/llm.json: "gemini" online (used now),
or "ollama_8b" / "server" through Ollama, so switching is a config change.
An online provider has "api": "openai". With "daily_limit" its requests are counted
per day (the free quota), and once they run out chatting stops until the quota resets.
Without a key in "key_file" the chat page asks for one (save_key).
Uses only the standard library.
"""

import json
import math
import re
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT / "config" / "llm.json"
USAGE = PROJECT / "chats" / "api_usage.json"  # 今天用了幾次，免費額度用
usage_lock = threading.Lock()
THINK = re.compile(r"<(think|thought)>.*?</>", re.S)  # Qwen3、Gemma 等推理模型會先輸出思考過程


class BadKey(RuntimeError):
    """Google says the API key doesn't work (deleted, or copied wrong), so the page asks for a new one."""


bad_keys = set()  # 試過不能用的 key，聊天畫面會再叫你輸入


class QuotaExceeded(RuntimeError):
    """Today's free requests are used up, so chatting stops until reset."""


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def describe():
    cfg = load_config()
    return f"{cfg['active']} · {cfg['providers'][cfg['active']]['model']}"


def online(cfg=None):
    cfg = cfg or load_config()
    return cfg["providers"][cfg["active"]].get("api") == "openai"


def pacific_now():
    """Time in California, where Google resets the free quota at midnight.

    Worked out by hand: zoneinfo needs the tzdata package on Windows.
    Daylight saving runs from the 2nd Sunday of March to the 1st Sunday of November, 2 am.
    """
    utc = datetime.now(timezone.utc)

    def sunday(month, n, hour):
        d = datetime(utc.year, month, 1, hour, tzinfo=timezone.utc)
        return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))

    summer = sunday(3, 2, 10) <= utc < sunday(11, 1, 9)
    return (utc + timedelta(hours=-7 if summer else -8)).replace(tzinfo=None), utc


def used_today():
    try:
        data = json.loads(USAGE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return data["used"] if data.get("day") == pacific_now()[0].date().isoformat() else 0


def set_used(n):
    USAGE.parent.mkdir(exist_ok=True)
    USAGE.write_text(json.dumps({"day": pacific_now()[0].date().isoformat(), "used": n}), encoding="utf-8")


def usage():
    """{"used", "limit", "reset"} for the online model's daily quota, or None without one.

    reset is when it starts again, in seconds since 1970, so the page shows it in local time.
    """
    cfg = load_config()
    limit = cfg["providers"][cfg["active"]].get("daily_limit")
    if not limit or needs_key(cfg):
        return None
    now, utc = pacific_now()
    midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
    reset = utc.replace(tzinfo=None) + (midnight - now)
    return {"used": min(used_today(), limit), "limit": limit,
            "reset": int(reset.replace(tzinfo=timezone.utc).timestamp())}


def key_path(p):
    return PROJECT / p["key_file"]


def has_key(p):
    try:
        return bool(key_path(p).read_text(encoding="utf-8").strip())
    except OSError:
        return False


def needs_key(cfg=None):
    """Whether the online model in use has no API key yet, so the page asks for one."""
    cfg = cfg or load_config()
    p = cfg["providers"][cfg["active"]]
    if not (online(cfg) and "key_file" in p):
        return False
    try:
        return key_path(p).read_text(encoding="utf-8").strip() in bad_keys | {""}
    except OSError:
        return True


def check_key(key, p=None):
    """Raises BadKey if Google rejects the key, RuntimeError if it can't be reached.

    Lists the models instead of chatting, so trying doesn't use up the free requests.
    """
    if p is None:
        cfg = load_config()
        p = cfg["providers"][cfg["active"]]
    req = urllib.request.Request(f"{p['base_url'].rstrip('/')}/models", headers={"Authorization": f"Bearer {key}"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            bad_keys.add(key)
            raise BadKey("這個 API key 不能用，請檢查有沒有複製完整") from None
        raise RuntimeError(f"Google 回傳錯誤 {e.code}，請等一下再試") from None
    except OSError:
        raise RuntimeError("連不上 Google，請檢查網路") from None


def check_saved_key():
    """At start: find out if the saved key was deleted, so the page asks for a new one before chatting."""
    cfg = load_config()
    p = cfg["providers"][cfg["active"]]
    if needs_key(cfg) or "key_file" not in p:
        return
    try:
        check_key(key_path(p).read_text(encoding="utf-8").strip(), p)
    except BadKey:
        print("存着的 API key 不能用了，聊天畫面會叫你重新輸入")
    except RuntimeError as e:
        print(f"沒辦法檢查 API key：{e}")


def save_key(key):
    """Try the key on the online model in use and save it if it works; raises RuntimeError if not."""
    cfg = load_config()
    p = cfg["providers"][cfg["active"]]
    check_key(key, p)
    key_path(p).write_text(key, encoding="utf-8")


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
    if p.get("api") == "openai":
        limit = p.get("daily_limit")
        if limit:
            with usage_lock:
                used = used_today()
                if used >= limit:
                    raise QuotaExceeded("今天的免費次數用完了")
                set_used(used + 1)  # 送出去就算一次，失敗的 Google 也會算
        try:
            return call_openai(name, p, messages, temperature)
        except QuotaExceeded:
            # 這裏數的比 Google 少（例如 key 在別的地方也用了），以 Google 為準
            if limit:
                set_used(limit)
            raise
    # 用 Ollama 原生的 /api/chat：OpenAI 相容的 /v1 不能設 num_ctx，只能用預設的 4096，
    # 角色資料加兩段詳細資料加對話就超過，最前面的提示會被截掉
    options = {"num_predict": p.get("max_tokens", 300), "num_ctx": p.get("num_ctx", 4096)}
    if temperature is not None:
        options["temperature"] = temperature  # 查資料這類要穩定的用 0
    elif "temperature" in p:
        options["temperature"] = p["temperature"]
    body = {"model": p["model"], "messages": messages, "stream": False, "options": options}
    if p.get("no_think"):
        # 讓 qwen3:14b 這類混合模型不思考，不然會花光 max_tokens 回覆變空白。
        # 在提示裏寫 /no_think 實測沒用；2507 版的 qwen3:4b 只會思考，這個也關不掉
        body["think"] = False
    req = urllib.request.Request(f"{ollama_url(p)}/api/chat",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{name} 回傳錯誤：{e.read().decode('utf-8', 'replace')}") from None
    except urllib.error.URLError as e:
        hint = {"ollama": "（Ollama 有沒有開？）", "server": "（另一部電腦的 start_server.bat 有沒有開？IP 對不對？）"}.get(name, "")
        raise RuntimeError(f"連不上 {name}：{e.reason}{hint}") from None
    text = data["message"].get("content") or ""
    return THINK.sub("", text).strip()


def call_openai(name, p, messages, temperature):
    """Reply from an OpenAI-compatible API, e.g. Gemini; the key is in key_file, which is not in git."""
    try:
        key = key_path(p).read_text(encoding="utf-8").strip()
    except OSError:
        raise RuntimeError(f"{name} 找不到 API key（{p['key_file']}）") from None
    body = {"model": p["model"], "messages": messages, "max_tokens": p.get("max_tokens", 300)}
    if temperature is not None:
        body["temperature"] = temperature
    elif "temperature" in p:
        body["temperature"] = p["temperature"]
    req = urllib.request.Request(f"{p['base_url'].rstrip('/')}/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        text = data["choices"][0]["message"].get("content") or ""
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code == 429 and "PerDay" in detail:  # 每天的額度；每分鐘的是 PerMinute
            raise QuotaExceeded("今天的免費次數用完了") from None
        if e.code in (401, 403) or "API_KEY_INVALID" in detail:
            bad_keys.add(key)
            raise BadKey("API key 不能用了（可能被刪掉了），請重新輸入") from None
        raise RuntimeError(f"{name} 回傳錯誤 {e.code}：{detail[:300]}") from None
    except (OSError, KeyError, IndexError, ValueError) as e:
        raise RuntimeError(f"連不上 {name}：{e}") from None
    return THINK.sub("", text).strip()


def ollama_url(p):
    """Ollama's own address from a provider's base_url (config keeps the OpenAI-style .../v1)."""
    return re.sub(r"/v1/?$", "", p["base_url"].rstrip("/"))


def embed(texts):
    """Vectors for texts from the embedding model (embed_model in config/llm.json), or None if it fails.

    With an online model it's that API's /embeddings (gemini-embedding-001; not counted
    in daily_limit, it has its own free quota). With Ollama it runs on the CPU (num_gpu 0):
    the 6GB card is already full with GPT-SoVITS and 8b.
    """
    cfg = load_config()
    if not texts or not cfg.get("embed_model"):
        return None
    p = cfg["providers"][cfg["active"]]
    if online(cfg):
        url = f"{p['base_url'].rstrip('/')}/embeddings"
        body = {"model": cfg["embed_model"], "input": texts}
        try:
            headers = {"Authorization": f"Bearer {key_path(p).read_text(encoding='utf-8').strip()}"}
        except OSError:
            return None
    else:
        url = f"{ollama_url(p)}/api/embed"
        body = {"model": cfg["embed_model"], "input": texts, "options": {"num_gpu": 0}, "keep_alive": -1}
        headers = {}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return [d["embedding"] for d in data["data"]] if online(cfg) else data["embeddings"]
    except (OSError, KeyError, ValueError) as e:
        print(f"embedding 失敗：{e}")
        return None


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a) * sum(y * y for y in b)) or 1)


def is_local():
    """Whether Ollama on this computer is used, so Freminet Chat.exe knows to start it."""
    cfg = load_config()
    url = cfg["providers"][cfg["active"]]["base_url"]
    return any(host in url for host in ("://127.0.0.1", "://localhost"))


if __name__ == "__main__":
    # Freminet Chat.exe（scripts/launcher.py）用：python scripts\llm.py --is-local，本地的話 exit code 0
    if sys.argv[1:] == ["--is-local"]:
        sys.exit(0 if is_local() else 1)
