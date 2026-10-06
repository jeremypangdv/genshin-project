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
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

import llm
import tts

PROJECT = tts.PROJECT
APP_DIR = PROJECT / "app"
CHAT_DIR = PROJECT / "chats"
CHARACTER_DIR = PROJECT / "characters"
# avatar 是沒有頭像圖片時顯示的字；image 放在 characters/ 裏
FRIENDS = {"freminet": {"name": "菲米尼", "avatar": "菲", "image": "freminet.jpg"}}
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


def warm_up():
    """Run one throwaway voice line and one throwaway LLM reply before the chat opens.

    The first request to each is much slower (CUDA, BERT, loading the Ollama
    model), so this makes the first real message as fast as the rest.
    Nothing here is saved to the chat.
    """
    if voice["state"] == "ready":
        print("預熱語音模型…", end="", flush=True)
        try:
            tts.synthesize("你好，我是菲米尼。", info["refs"][info["default_emotion"]][0]).unlink()
            print(" 完成")
        except Exception as e:
            print(f" 失敗：{e}")
    cfg = llm.load_config()
    # 後備的 LLM 也預熱，額度用完要切換時不用等它載入
    for name in dict.fromkeys(filter(None, [cfg["active"], cfg.get("fallback")])):
        print(f"預熱 LLM（{name}）…", end="", flush=True)
        try:
            # 用真的系統提示，Ollama 會把這段快取起來，第一則訊息就不用重新讀
            llm.call(name, llm_messages("freminet", []) + [{"role": "user", "content": "你好"}])
            print(" 完成")
        except RuntimeError as e:
            print(f" 失敗：{e}")


@atexit.register
def stop_voice():
    if voice["proc"]:
        voice["proc"].terminate()


def system_prompt(friend, summary=""):
    persona = (CHARACTER_DIR / f"{friend}.md").read_text(encoding="utf-8")
    emotions = "、".join(f"[{e}]（{NAMES.get(e, e)}）" for e in info["refs"])
    return f"""{persona}

## 回覆格式（一定要遵守）
- 這是聊天軟件裏的對話，你的回覆會用你的聲音念出來，變成語音訊息。
- 第一行只寫一個情緒標籤，選最符合這次回覆語氣的：{emotions}
- 第二行開始寫你說出口的話。不要寫動作、表情、旁白（例如「（笑）」「*低頭*」），也不要用表情符號。
- 用繁體中文、口語，一般一到三句，不要長篇大論。
- 不要提到自己是 AI 或語言模型。""" + (f"""

## 你們之前聊過的事（摘要）
{summary}""" if summary else "")


def chat_path(friend):
    return CHAT_DIR / f"{friend}.json"


def load_chat(friend):
    path = chat_path(friend)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_chat(friend, messages):
    CHAT_DIR.mkdir(exist_ok=True)
    chat_path(friend).write_text(json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8")


# 舊對話的摘要：summary 概括了聊天記錄裏 upto 之前的訊息，之後的才原文傳給 LLM
def memory_path(friend):
    return CHAT_DIR / f"{friend}.memory.json"


def load_memory(friend):
    path = memory_path(friend)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"summary": "", "upto": 0}


def history_turns():
    cfg = llm.load_config()
    # Ollama 的上下文只有 4096，角色資料就佔了一半多，所以可以按模型設定記住幾輪
    return cfg["providers"][cfg["active"]].get("history_turns", cfg.get("history_turns", 20))


def next_user(messages, i):
    """First user message at or after i, so the history sent never starts with a reply."""
    while i < len(messages) and messages[i]["role"] != "user":
        i += 1
    return i


def summarize(friend):
    """Fold old messages into the summary once there are more than history_turns of them.

    It cuts back to half in one go instead of dropping one turn per message, so
    the history sent stays the same for several messages and the API cache hits.
    """
    turns = history_turns()
    messages = load_chat(friend)
    memory = load_memory(friend)
    if len(messages) - memory["upto"] <= turns * 2:
        return
    cut = next_user(messages, len(messages) - turns // 2 * 2)
    lines = "\n".join(
        f"{'對方' if m['role'] == 'user' else '菲米尼'}：{m['text']}" for m in messages[memory["upto"]:cut])
    prompt = f"""把菲米尼和對方（旅行者）的聊天整理成摘要，給菲米尼以後記得聊過什麼。
- 寫重要的：對方說過自己的事（喜好、經歷、心情）、約定、聊過的話題、兩人關係的變化
- 和舊摘要合併成一份，舊的不重要的可以刪；用第三人稱，條列，總共不超過 200 字
- 只輸出摘要，不要其他文字

舊摘要：
{memory["summary"] or "（沒有）"}

新的聊天：
{lines}"""
    try:
        summary = llm.chat([{"role": "user", "content": prompt}]).strip()
    except RuntimeError as e:
        print(f"整理摘要失敗：{e}")
        return
    if summary:
        memory_path(friend).write_text(json.dumps({"summary": summary, "upto": cut}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


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
    memory = load_memory(friend)
    # 摘要失敗的話也不要傳太多，最多兩倍 history_turns
    start = next_user(messages, max(memory["upto"], len(messages) - history_turns() * 4))
    out = [{"role": "system", "content": system_prompt(friend, memory["summary"])}]
    for m in messages[start:]:
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
    with lock:
        chat_path(friend).unlink(missing_ok=True)
        memory_path(friend).unlink(missing_ok=True)
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
    # 回覆先送出去，摘要在背景整理；下一則訊息會等它完成（lock）
    threading.Thread(target=locked_summarize, args=(friend,), daemon=True).start()
    return jsonify(msg)


def locked_summarize(friend):
    with lock:
        summarize(friend)


@app.get("/avatars/<name>")
def avatar(name):
    return send_from_directory(CHARACTER_DIR, name)


@app.get("/audio/<name>")
def audio(name):
    return send_from_directory(tts.OUTPUT_DIR, name)


if __name__ == "__main__":
    print(f"LLM：{llm.describe()}")
    # 先把模型載入和預熱好才開聊天，打開時就能直接聊
    load_voice()
    if voice["state"] == "failed":
        print("語音模型載入失敗，聊天只會有文字")
    warm_up()
    print("準備好了，打開 http://127.0.0.1:5000")
    threading.Timer(1, webbrowser.open, ["http://127.0.0.1:5000"]).start()
    app.run(host="127.0.0.1", port=5000, threaded=True)
