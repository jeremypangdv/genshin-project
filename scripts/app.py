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
import random
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
MAX_FACTS = 400  # 對方的資料超過這麼多字，才請 LLM 合併重複的
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
# 要說忘了時，每次隨機給一個方向（不是句子），不然他每次都套同一個句型
FORGET_STYLES = [
    # 都要合角色：內向、沒自信、會道歉，不開玩笑（見 characters/freminet.md 的個性和說話方式）
    "小聲道歉，怪自己記性不好",
    "說只記得有聊過，但細節想不起來了",
    "先努力回想一下，最後承認想不起來",
    "老實地道歉，說這次會好好記住",
    "有點慌張，怕對方覺得他不在乎",
    "很簡短地說忘了，直接問對方",
    "說最近一直在想發條玩具的事，一時想不起來，覺得很抱歉",
    "平靜地說想不起來，問對方願不願意再說一次",
]
# 對方在問「你記不記得我的…」：有這些字、是問句、還提到「我」，就先查資料（look_up）
RECALL = re.compile(r"記得|记得|記不|忘了|忘記|還知道|我叫什麼|我的名字|說過|講過|告訴過|提過")
QUESTION = re.compile(r"[？?]|嗎|什麼|哪|幾|誰|來着|是不是")
# 說自己忘了的說法（「忘乎所以」「忘記帶傘」這種不算）
FORGOT = re.compile(r"想不起|[記记]不(?:太)?[清起得]|不(?:太)?[記记]得|(?:好像|一時|我)忘(?:了|[記记]了?)")
ASK_ENGLISH = re.compile(r"英文|英語|English", re.I)
CHINESE = re.compile(r"[一-鿿]")
# 開頭的語氣詞。小模型一害羞就每句都用「那個…」開頭，提示裏禁也禁不掉，所以最多每三句用一次
FILLER = re.compile(r"^(?:(?:那個|嗯|唔|呃|啊|欸)[…，,.。？！?!\s]+)+")
# 結巴（「我…我」「能…能」）：角色設定說只在真的緊張時用，最近用過就拿掉
STUTTER = re.compile(r"([一-鿿])…\1")
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


def system_prompt(friend, memory=None, style=None, recall=None):
    """recall is what look_up() found when the message asks whether he remembers something."""
    persona = (CHARACTER_DIR / f"{friend}.md").read_text(encoding="utf-8")
    emotions = "、".join(f"[{e}]（{NAMES.get(e, e)}）" for e in info["refs"])
    facts, summary = (memory or {}).get("facts", ""), (memory or {}).get("summary", "")
    known = "、".join(k for k, v in (("「對方的資料」", facts), ("摘要", summary)) if v)
    style = style or random.choice(FORGET_STYLES)
    return f"""{persona}

## 回覆格式（一定要遵守）
- 這是聊天軟件裏的對話，你的回覆會用你的聲音念出來，變成語音訊息。
- 第一行只寫一個情緒標籤，選最符合這次回覆語氣的：{emotions}
- 第二行開始寫你說出口的話。不要寫動作、表情、旁白（例如「（笑）」「*低頭*」），也不要用表情符號。
- 用繁體中文、口語。這是語音訊息，要像平常講話一樣短：通常一兩句、三十字左右，問什麼答什麼就好。
- 不用每次都補充自己的事，也不用每次都反問對方，大部分回覆說完就停。
- 不要提到自己是 AI 或語言模型。""" + (f"""

## 對方的資料（對方以前親口告訴你的）
{facts}""" if facts else "") + (f"""

## 最近聊過的事（摘要）
{summary}""" if summary else "") + f"""

## 記憶（很重要）
""" + (f"對方問的事你記得，對方說過：「{recall}」（這裏的「我」是對方）。直接肯定地回答，不要說忘了，也不用說「好像」。" if recall else
       f"對方問的事你聽過但忘了（不是不知道），不要猜答案，也不要拿別的事來湊。像人一樣自然地承認忘了，再請對方說一次。方式：{style}。"
       if recall == "" else
       f"""{f"上面{known}寫的事，你都記得很清楚，被問到就肯定地回答，不用說「好像」。" + chr(10) if known else ""}對方問到對方自己的事、但{known + "和" if known else ""}這次對話裏都沒有的，不要猜答案，請對方告訴你。""")
# 放在最後，小模型比較聽；寫了固定例句（連他自己說過的句子也是）的話他會照抄，所以只說要怎樣。
# 「說忘了的方式」只在 look_up 查不到時才給：平常也放的話，8b 會在不相干的回覆後面硬加
# 「我還在想佩伊的事，一時想不起來」（2000 輪測試約 0.5%，而且一段對話裏說過一次就一直套）


def look_up(text, memory, said):
    """When the message asks whether he remembers something, look it up first, without the persona.

    Returns the line that answers it, "" when it isn't there, or None when the message isn't asking.
    With only the memory section saying "admit you forgot", 8b said it forgot about half of
    the facts it had; looking up first fixed most of that and still didn't guess things never
    said (2000-message test, 2026-10-10). A separate 4b checker was too slow on a 6GB card.
    """
    if not (RECALL.search(text) and QUESTION.search(text) and "我" in text):
        return None
    # 試過的寫法（2026-10-10）：
    # - 先叫 8b 判斷「是不是在問記憶」：連真的問題也答「不是」，所以改用上面的規則
    # - 問「資料裏有沒有寫到」：常答「沒有」；叫它照抄能回答的那一行準很多
    # - 不放摘要（常寫「對方資料：無」）和對方問過的問題，8b 看了都會答「沒有」
    lines = "\n".join([memory.get("facts", "")] + [f"- {t}" for t in said]).strip()
    if not lines:
        return ""
    try:
        found = llm.chat([{"role": "user", "content": f"""下面是對方的資料，每行一條，都是對方自己說的（「我」就是對方）：
{lines}

對方問：「{text}」
從上面的資料裏，找出能回答這個問題的那一行，照抄輸出。
問的是資料裏沒有的人或事（例如問媽媽的名字、住哪裏，資料裏沒寫），就只輸出「沒有」。"""}], temperature=0).strip()
    except RuntimeError:
        return None
    return "" if found.startswith(("沒有", "没有")) else found.lstrip("- ")


def vary_opening(reply, messages):
    """Drop the filler at the start of the reply if either of the last two replies started with one."""
    recent = [m["text"] for m in messages if m["role"] == "assistant"][-2:]
    rest = FILLER.sub("", reply, count=1)
    if any(FILLER.match(t) for t in recent) and rest and rest != reply:
        return rest
    return reply


def calm(reply, messages):
    """Drop stutters if either of the last two replies already had one."""
    recent = [m["text"] for m in messages if m["role"] == "assistant"][-2:]
    if any(STUTTER.search(t) for t in recent):
        return STUTTER.sub(r"\1", reply)
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


# 舊對話的記憶：facts 是對方說過自己的事（名字、寵物、生日…），只加不刪；
# summary 概括了聊天記錄裏 upto 之前聊過的話題，舊的會慢慢被擠掉；upto 之後的才原文傳給 LLM
def memory_path(friend):
    return CHAT_DIR / f"{friend}.memory.json"


def load_memory(friend):
    path = memory_path(friend)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"facts": "", "summary": "", "upto": 0}


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
    """Fold old messages into the memory once there are more than history_turns of them.

    It cuts back to half in one go instead of dropping one turn per message, so
    the history sent stays the same for several messages and the API cache hits.
    Facts about the other person are kept apart from the summary, because when
    they were mixed in, the model dropped them as "old" after a few rounds.
    """
    turns = history_turns()
    messages = load_chat(friend)
    memory = {"facts": "", **load_memory(friend)}
    if len(messages) - memory["upto"] <= turns * 2:
        return
    cut = next_user(messages, len(messages) - turns // 2 * 2)
    lines = "\n".join(
        f"{'對方' if m['role'] == 'user' else '菲米尼'}：{m['text']}" for m in messages[memory["upto"]:cut])
    try:
        facts = merge_facts(memory["facts"], "\n".join(
            m["text"] for m in messages[memory["upto"]:cut] if m["role"] == "user"))
        summary = llm.chat([{"role": "user", "content": f"""把菲米尼和對方最近聊的話題整理成摘要，給菲米尼以後記得聊過什麼。
- 寫聊過的話題、約定、對方的心情、兩人關係的變化；對方的個人資料（名字、家人、寵物、生日、喜好…）另外記，這裏一律不寫
- 只寫聊天裏真的出現過的，不要推測或補充
- 和舊摘要合併成一份，舊的不重要的可以刪；用第三人稱，條列，總共不超過 300 字
- 只輸出摘要，不要其他文字

舊摘要：
{memory["summary"] or "（沒有）"}

新的聊天：
{lines}"""}]).strip()
    except RuntimeError as e:
        print(f"整理摘要失敗：{e}")
        return
    memory_path(friend).write_text(json.dumps({"facts": facts, "summary": summary or memory["summary"], "upto": cut},
                                              ensure_ascii=False, indent=1), encoding="utf-8")


def merge_facts(facts, said):
    """Add what the other person said about themself; old facts are only shortened, never dropped.

    said is only their own messages, so Freminet's own likes don't end up in it,
    and repeats are skipped here because the model writes known facts again anyway.
    """
    new = llm.chat([{"role": "user", "content": f"""下面是對方傳的訊息。找出對方說的關於自己的事實：名字、家人、寵物、工作、學校、生日、喜歡和討厭的東西、害怕的東西、計劃。
- 每行一條，用「- 」開頭，用繁體中文，寫具體的名字和數字（例如「- 養了一隻黑貓，叫芝麻」）
- 只寫對方明確說了的，問句和閒聊不算；沒有就只輸出「沒有」
- 每一條只根據一則訊息，不要把不同訊息的內容拼在一起（例如「我生日是三月」和「下個月去旅行」是兩件事）

{said}"""}]).strip()
    lines = facts.splitlines()
    for line in new.splitlines():
        line = line.strip()
        if line.startswith("-") and line.strip(" -。") not in ("沒有", "没有", "無", "无") \
                and not any(similar(line.lstrip("- "), old.lstrip("- ")) for old in lines):
            lines.append(line)
    if len("\n".join(lines)) > MAX_FACTS:
        # 太長才請它合併重複的、刪掉被新資料取代的，但不能少了任何一件事
        short = [l.strip() for l in llm.chat([{"role": "user", "content": f"""把這份關於對方的資料整理得更短：合併重複的，同一件事前後不同的只留後面（較新）的。
其他每一件事都要留着，不能刪；用繁體中文，每行一條，用「- 」開頭，只輸出資料。

{chr(10).join(lines)}"""}]).splitlines() if l.strip().startswith("-")]
        if len(short) >= len(lines) // 2:  # 刪太多的話就不用它的版本
            lines = short
    return "\n".join(lines)


def similar(a, b):
    """True when two lines share most of their two-character pieces."""
    pa, pb = ({t[i:i + 2] for i in range(len(t) - 1)} for t in (a, b))
    return bool(pa and pb) and len(pa & pb) / min(len(pa), len(pb)) > 0.5


def reply_to(friend, messages, text):
    """(raw, emotion, reply) for the last message; retried up to 3 times when it slips into English,
    or says it forgot when it shouldn't (or doesn't when look_up found nothing).

    Retrying replies that repeat an earlier one was tried too (2026-10-10): 8b
    wrote the same sentence pattern again every time, so it only made replies slower.
    """
    memory = load_memory(friend)
    # 還沒整理進資料的最近幾則：只給陳述句，問過的「你記得…嗎」會讓 8b 搞混
    said = [m["text"] for m in messages[history_start(messages, memory):-1]
            if m["role"] == "user" and not QUESTION.search(m["text"])]
    recall = look_up(text, memory, said)
    history = llm_messages(friend, messages, recall=recall)
    for _ in range(3):
        raw = llm.chat(history)
        emotion, reply = parse_reply(raw)
        english = ENGLISH.search(reply) and not wants_english(text)
        # 查不到時要說忘了，其他時候不要說忘了；不對就重新生成。
        # 只靠提示的話，兩邊都會錯：答完問題後面硬加「想不起來」，或者被告知忘了還自己猜一個
        wrong = bool(FORGOT.search(reply)) != (recall == "")
        if not english and not wrong:
            break
    return raw, emotion, reply


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


def history_start(messages, memory):
    # 摘要失敗的話也不要傳太多，最多兩倍 history_turns
    return next_user(messages, max(memory["upto"], len(messages) - history_turns() * 4))


def llm_messages(friend, messages, style=None, recall=None):
    memory = load_memory(friend)
    out = [{"role": "system", "content": system_prompt(friend, memory, style, recall)}]
    for m in messages[history_start(messages, memory):]:
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
            raw, emotion, reply = reply_to(friend, messages, text)
        except RuntimeError as e:
            return jsonify(error=str(e)), 502
        if not reply:
            return jsonify(error=f"模型沒有回覆內容：{raw!r}"), 502
        reply = shorten(calm(vary_opening(reply, messages), messages))

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
