"""WhatsApp-style chat app: message Freminet, he answers with a voice message.

    python scripts/app.py      then open http://127.0.0.1:5000

The reply text comes from the LLM in config/llm.json, in the character set out
in characters/freminet.md, and is read out by GPT-SoVITS with the exported model
in Models/Freminet/. Chats are saved in chats/, audio in tts_output/.
"""

import atexit
import json
import re
import threading
import time
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

import llm
import tts

PROJECT = tts.PROJECT
APP_DIR = PROJECT / "app"
CHAT_DIR = PROJECT / "chats"
CHARACTER_DIR = PROJECT / "characters"
FRIENDS = {"freminet": {"name": "菲米尼", "avatar": "菲"}}
NAMES = {v: k for k, v in tts.ALIASES.items()}

# 模型回覆的第一行是情緒標籤，例如 [happy] 或 【開心】
TAG = re.compile(r"^\s*[\[【(（]\s*([A-Za-z一-鿿]+)\s*[\]】)）]\s*")
# 念出來的只能是對白，把（笑）、*低頭* 這種動作描寫拿掉
ACTION = re.compile(r"（[^）]*）|\([^)]*\)|\*[^*]*\*")

app = Flask(__name__, static_folder=None)
info = json.loads((tts.MODEL_DIR / "model.json").read_text(encoding="utf-8"))
voice = {"state": "loading", "proc": None}
lock = threading.Lock()  # 一次只處理一則訊息，顯卡只有一張


def load_voice():
    try:
        if tts.api_up():
            tts.set_weights("set_gpt_weights", tts.MODEL_DIR / info["gpt"])
            tts.set_weights("set_sovits_weights", tts.MODEL_DIR / info["sovits"])
        else:
            voice["proc"] = tts.start_api(info)
        voice["state"] = "ready"
    except (Exception, SystemExit):
        voice["state"] = "failed"


@atexit.register
def stop_voice():
    if voice["proc"]:
        voice["proc"].terminate()


def system_prompt(friend):
    persona = (CHARACTER_DIR / f"{friend}.md").read_text(encoding="utf-8")
    emotions = "、".join(f"[{e}]（{NAMES.get(e, e)}）" for e in info["refs"])
    return f"""{persona}

## 回覆格式（一定要遵守）
- 這是聊天軟件裏的對話，你的回覆會用你的聲音念出來，變成語音訊息。
- 第一行只寫一個情緒標籤，選最符合這次回覆語氣的：{emotions}
- 第二行開始寫你說出口的話。不要寫動作、表情、旁白（例如「（笑）」「*低頭*」），也不要用表情符號。
- 用繁體中文、口語，一般一到三句，不要長篇大論。
- 不要提到自己是 AI 或語言模型。"""


def chat_path(friend):
    return CHAT_DIR / f"{friend}.json"


def load_chat(friend):
    path = chat_path(friend)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_chat(friend, messages):
    CHAT_DIR.mkdir(exist_ok=True)
    chat_path(friend).write_text(json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8")


def parse_reply(raw):
    emotion = info["default_emotion"]
    m = TAG.match(raw)
    if m:
        tag = m.group(1).lower()
        tag = tts.ALIASES.get(m.group(1), tag)
        if tag in info["refs"]:
            emotion = tag
        raw = raw[m.end():]
    text = ACTION.sub("", raw)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return emotion, text


def llm_messages(friend, messages):
    cfg = llm.load_config()
    # Ollama 的上下文只有 4096，角色資料就佔了一半多，所以可以按模型設定記住幾輪
    turns = cfg["providers"][cfg["active"]].get("history_turns", cfg.get("history_turns", 20))
    out = [{"role": "system", "content": system_prompt(friend)}]
    for m in messages[-turns * 2:]:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["text"]})
        else:
            out.append({"role": "assistant", "content": f"[{m['emotion']}]\n{m['text']}"})
    return out


@app.get("/")
def index():
    return send_from_directory(APP_DIR, "index.html")


@app.get("/api/status")
def status():
    return jsonify(voice=voice["state"], llm=llm.describe())


@app.get("/api/friends")
def friends():
    return jsonify([{"id": k, **v, "last": (load_chat(k) or [None])[-1]} for k, v in FRIENDS.items()])


@app.get("/api/chats/<friend>")
def get_chat(friend):
    if friend not in FRIENDS:
        abort(404)
    return jsonify(load_chat(friend))


@app.delete("/api/chats/<friend>")
def clear_chat(friend):
    if friend not in FRIENDS:
        abort(404)
    chat_path(friend).unlink(missing_ok=True)
    return jsonify(ok=True)


@app.post("/api/chats/<friend>")
def send(friend):
    if friend not in FRIENDS:
        abort(404)
    text = (request.json or {}).get("text", "").strip()
    if not text:
        abort(400)
    with lock:
        messages = load_chat(friend)
        messages.append({"role": "user", "text": text, "time": time.time()})
        save_chat(friend, messages)
        try:
            raw = llm.chat(llm_messages(friend, messages))
        except RuntimeError as e:
            return jsonify(error=str(e)), 502
        emotion, reply = parse_reply(raw)
        if not reply:
            return jsonify(error=f"模型沒有回覆內容：{raw!r}"), 502

        msg = {"role": "assistant", "text": reply, "emotion": emotion, "time": time.time()}
        if voice["state"] == "ready":
            try:
                msg["audio"] = tts.synthesize(reply, info["refs"][emotion][0]).name
            except Exception as e:
                msg["voice_error"] = str(e)
        else:
            msg["voice_error"] = "語音模型還沒載入" if voice["state"] == "loading" else "語音模型載入失敗"
        messages.append(msg)
        save_chat(friend, messages)
    return jsonify(msg)


@app.get("/audio/<name>")
def audio(name):
    return send_from_directory(tts.OUTPUT_DIR, name)


if __name__ == "__main__":
    threading.Thread(target=load_voice, daemon=True).start()
    print(f"LLM：{llm.describe()}")
    print("打開 http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, threaded=True)
