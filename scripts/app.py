"""WhatsApp-style chat app: message Freminet, he answers with a voice message.

    python scripts/app.py            then open http://127.0.0.1:5000
    python scripts/app.py --window   open it in its own window instead (used by Freminet Chat.exe)

The reply text comes from the LLM in config/llm.json, in the character set out
in characters/freminet.md, and is read out by GPT-SoVITS with the exported model
in Models/Freminet/. Chats are saved in chats/, audio in tts_output/.
"""

import atexit
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from flask import Flask, abort, jsonify, request, send_from_directory

# GPT-SoVITS 的 Python（給朋友的版本用它跑）不會自動把 scripts/ 加進搜尋路徑
sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402
import tts  # noqa: E402

PROJECT = tts.PROJECT
APP_DIR = PROJECT / "app"
CHAT_DIR = PROJECT / "chats"
CHARACTER_DIR = PROJECT / "characters"
KEEP_VOICES = 50  # 每個角色只留最近 50 則語音（約 25MB），更早的刪掉 wav，只剩文字
# avatar 是沒有頭像圖片時顯示的字；image 放在 characters/ 裏
# backgrounds 是聊天背景圖的資料夾，background 是還沒選過時預設用的那張
# cursor 是跟着滑鼠的小圖；指着可以點的東西時換 cursor_click，指着輸入欄時換 cursor_text
FRIENDS = {"freminet": {"name": "菲米尼", "avatar": "菲", "image": "freminet.jpg",
                        "backgrounds": "freminet profile/Background", "background": "background.png",
                        "peek": "freminet-peek.gif",
                        "cursor": "freminet-cursor.png", "cursor_click": "freminet-cursor-click.png",
                        "cursor_text": "freminet-cursor-text.png",
                        "heart": "freminet-heart.png"}}
NAMES = {v: k for k, v in tts.ALIASES.items()}

# 模型回覆的第一行是情緒標籤，例如 [happy] 或 【開心】
TAG = re.compile(r"^\s*[\[【(（]\s*([A-Za-z一-鿿]+)\s*[\]】)）]\s*")
# 念出來的只能是對白，把（笑）、*低頭* 這種動作描寫拿掉
ACTION = re.compile(r"（[^）]*）|\([^)]*\)|\*[^*]*\*")
# 小模型偶爾在中文裏夾英文（「maybe」「usually」），寫在提示裏也禁不掉，有的話就重新生成
ENGLISH = re.compile(r"[A-Za-z]{2,}")
# 對方說要英文，或整則訊息都是英文時，才不擋英文；中文裏夾個「LOL」這種不算
ASK_ENGLISH = re.compile(r"英文|英語|English", re.I)
CHINESE = re.compile(r"[一-鿿]")
# 開頭的語氣詞。小模型一害羞就每句都用「那個…」開頭，提示裏禁也禁不掉，所以最多每三句用一次
FILLER = re.compile(r"^(?:(?:那個|嗯|唔|呃|啊|欸)[…，,.。？！?!\s]+)+")
# 語音訊息要短，提示裏叫模型一兩句它還是常常寫到七八十字，超過就在句子結尾切掉
SENTENCE = re.compile(r"[^。！？!?.]+[。！？!?….]*|[。！？!?.]+")
MAX_CHARS = 45

IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
# 上傳的背景只收 JPG / PNG，長和寬都至少要和聊天視窗一樣大，鋪滿時才不會被拉大變模糊
UPLOAD_FORMATS = {"JPEG", "PNG"}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
info = json.loads((tts.MODEL_DIR / "model.json").read_text(encoding="utf-8"))
voice = {"state": "loading", "proc": None}
started = threading.Event()  # 模型載入、預熱完了
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
    print(f"預熱 LLM（{llm.load_config()['active']}）…", end="", flush=True)
    try:
        # 用真的系統提示，Ollama 會把這段快取起來，第一則訊息就不用重新讀
        llm.chat(llm_messages("freminet", []) + [{"role": "user", "content": "你好"}])
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
- 用繁體中文、口語。這是語音訊息，要像平常講話一樣短：通常一兩句、三十字左右，問什麼答什麼就好。
- 不用每次都補充自己的事，也不用每次都反問對方，大部分回覆說完就停。
- 不要提到自己是 AI 或語言模型。""" + (f"""

## 你們之前聊過的事（摘要）
{summary}""" if summary else "")


def vary_opening(reply, messages):
    """Drop the filler at the start of the reply if either of the last two replies started with one."""
    recent = [m["text"] for m in messages if m["role"] == "assistant"][-2:]
    rest = FILLER.sub("", reply, count=1)
    if any(FILLER.match(t) for t in recent) and rest and rest != reply:
        return rest
    return reply


def size(text):
    """Length in Chinese characters; an English word counts as two."""
    return len(re.sub(r"[A-Za-z']+", "字字", re.sub(r"\s", "", text)))


def wants_english(text):
    return bool(ASK_ENGLISH.search(text) or (ENGLISH.search(text) and not CHINESE.search(text)))


def shorten(reply):
    """Keep whole sentences up to MAX_CHARS; the first sentence is always kept."""
    out = ""
    for part in SENTENCE.findall(reply):
        if out and size(out + part) > MAX_CHARS:
            break
        out += part
    return out.strip()


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
- 和舊摘要合併成一份，舊的不重要的可以刪；用第三人稱，條列，總共不超過 400 字
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
    # --window 時視窗一開始就打開，模型還在載入就先顯示載入畫面
    return send_from_directory(APP_DIR, "index.html" if started.is_set() else "loading.html")


@app.get("/cursors/<name>")
def cursor(name):
    return send_from_directory(APP_DIR / "cursors", name)


@app.get("/api/ready")
def ready():
    return jsonify(ready=started.is_set())


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
        # 語音檔也一起刪，清空後畫面上已經找不到它們
        for msg in load_chat(friend):
            if msg.get("audio"):
                (tts.OUTPUT_DIR / Path(msg["audio"]).name).unlink(missing_ok=True)
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
            for _ in range(3):
                raw = llm.chat(llm_messages(friend, messages))
                emotion, reply = parse_reply(raw)
                if not ENGLISH.search(reply) or wants_english(text):
                    break
        except RuntimeError as e:
            return jsonify(error=str(e)), 502
        if not reply:
            return jsonify(error=f"模型沒有回覆內容：{raw!r}"), 502
        reply = shorten(vary_opening(reply, messages))

        msg = {"role": "assistant", "text": reply, "emotion": emotion, "time": time.time()}
        if voice["state"] == "ready":
            try:
                msg["audio"] = tts.synthesize(reply, info["refs"][emotion][0]).name
            except Exception as e:
                msg["voice_error"] = str(e)
        else:
            msg["voice_error"] = "語音模型還沒載入" if voice["state"] == "loading" else "語音模型載入失敗"
        messages.append(msg)
        drop_old_voices(messages)
        save_chat(friend, messages)
    # 回覆先送出去，摘要在背景整理；下一則訊息會等它完成（lock）
    threading.Thread(target=locked_summarize, args=(friend,), daemon=True).start()
    return jsonify(msg)


def drop_old_voices(messages):
    """Keep only the last KEEP_VOICES voice messages; older ones lose their wav and show as text."""
    voiced = [m for m in messages if m.get("audio")]
    for m in voiced[:-KEEP_VOICES]:
        (tts.OUTPUT_DIR / Path(m.pop("audio")).name).unlink(missing_ok=True)


def locked_summarize(friend):
    with lock:
        summarize(friend)


@app.get("/avatars/<name>")
def avatar(name):
    return send_from_directory(CHARACTER_DIR, name)


def background_dir(friend):
    if friend not in FRIENDS or "backgrounds" not in FRIENDS[friend]:
        abort(404)
    return PROJECT / FRIENDS[friend]["backgrounds"]


@app.get("/api/backgrounds/<friend>")
def list_backgrounds(friend):
    folder = background_dir(friend)
    files = [f for f in folder.glob("*") if f.suffix.lower() in IMAGE_TYPES] if folder.is_dir() else []
    # 舊的在前，新上傳的排在最後
    return jsonify([f.name for f in sorted(files, key=lambda f: f.stat().st_mtime)])


@app.post("/api/backgrounds/<friend>")
def upload_background(friend):
    folder = background_dir(friend)
    file = request.files.get("file")
    name = Path(file.filename or "").name if file else ""
    if not name or Path(name).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        return jsonify(error="只能上傳 JPG、JPEG 或 PNG"), 400
    try:
        with Image.open(file.stream) as img:
            fmt, (w, h) = img.format, img.size
    except UnidentifiedImageError:
        return jsonify(error="圖片壞了，打不開"), 400
    if fmt not in UPLOAD_FORMATS:
        return jsonify(error=f"只能上傳 JPG、JPEG 或 PNG，這張其實是 {fmt}"), 400
    min_w, min_h = WINDOW_SIZE
    if w < min_w or h < min_h:
        return jsonify(error=f"圖片太小（{w}×{h}），長和寬都要至少 {min_w}×{min_h}"), 400
    file.stream.seek(0)
    folder.mkdir(parents=True, exist_ok=True)
    # 同名就在後面加數字，不蓋掉原本的
    target, n = folder / name, 1
    while target.exists():
        target, n = folder / f"{Path(name).stem} ({n}){Path(name).suffix}", n + 1
    file.save(target)
    return jsonify(name=target.name)


@app.delete("/api/backgrounds/<friend>/<name>")
def delete_background(friend, name):
    target = background_dir(friend) / Path(name).name
    if target.suffix.lower() not in IMAGE_TYPES or not target.is_file():
        return jsonify(error="找不到這張圖"), 404
    target.unlink()
    return jsonify(ok=True)


@app.get("/backgrounds/<friend>/<name>")
def background(friend, name):
    return send_from_directory(background_dir(friend), name)


@app.get("/audio/<name>")
def audio(name):
    return send_from_directory(tts.OUTPUT_DIR, name)


# 聊天視窗的大小，正方形，和電腦版聊天軟件差不多
WINDOW_SIZE = (860, 860)
EDGE = [Path(os.environ.get(k, "")) / "Microsoft/Edge/Application/msedge.exe"
        for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]


def start():
    print(f"LLM：{llm.describe()}")
    # 先把模型載入和預熱好才開聊天，打開時就能直接聊
    load_voice()
    if voice["state"] == "failed":
        print("語音模型載入失敗，聊天只會有文字")
    warm_up()
    print("準備好了，打開 http://127.0.0.1:5000")
    started.set()


def open_window():
    """Open the chat in its own Edge app window (no tabs or address bar)."""
    edge = next((e for e in EDGE if e.is_file()), None)
    if not edge:
        print("找不到 Edge，改用瀏覽器打開")
        webbrowser.open("http://127.0.0.1:5000")
        return
    # 獨立的設定資料夾，不和平常用的 Edge 混在一起；選過的背景也記在這裏
    profile = Path(os.environ["LOCALAPPDATA"]) / "FreminetChat" / "edge"
    subprocess.Popen([str(edge), "--app=http://127.0.0.1:5000", f"--user-data-dir={profile}",
                      "--window-size={},{}".format(*WINDOW_SIZE), "--no-first-run",
                      "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required"])


# --window 時，視窗關掉就關伺服器。Edge 關了視窗程序可能還在背景，所以不看 Edge，
# 改看聊天畫面：開着時每 20 秒會問一次 /api/ping，關掉時送 /api/bye
seen = {"last": time.time(), "bye": None}
IDLE_LIMIT = 150  # 視窗縮到最小時瀏覽器一分鐘才跑一次計時器，要留多一點


@app.before_request
def mark_seen():
    seen["last"] = time.time()


@app.get("/api/ping")
def ping():
    return jsonify(ok=True)


@app.post("/api/bye")
def bye():
    seen["bye"] = time.time()
    return jsonify(ok=True)


@app.post("/api/open")
def open_again():
    # 已經在跑時再雙擊 exe，就多開一個視窗
    open_window()
    return jsonify(ok=True)


def watch_window():
    while True:
        time.sleep(1)
        now = time.time()
        # 送了 bye 之後 5 秒內沒有新的請求（重新整理會馬上有），就是視窗關掉了
        closed = seen["bye"] and seen["last"] <= seen["bye"] and now - seen["bye"] > 5
        if closed or now - seen["last"] > IDLE_LIMIT:
            print("視窗關掉了，關閉伺服器")
            stop_voice()
            os._exit(0)


if __name__ == "__main__":
    # 載入畫面每秒問一次好了沒、聊天畫面定時 ping，不要寫進記錄
    logging.getLogger("werkzeug").addFilter(
        lambda r: not any(a in r.getMessage() for a in ("/api/ready", "/api/ping", "/api/bye")))
    if "--window" in sys.argv:
        threading.Thread(target=start, daemon=True).start()
        threading.Thread(target=watch_window, daemon=True).start()
        threading.Timer(0.5, open_window).start()
    else:
        start()
        threading.Timer(1, webbrowser.open, ["http://127.0.0.1:5000"]).start()
    app.run(host="127.0.0.1", port=5000, threaded=True)
