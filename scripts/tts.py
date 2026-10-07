"""Type text, hear it in Freminet's voice.

Starts GPT-SoVITS api_v2.py in the background with the exported model in
Models/Freminet/, then reads lines from the keyboard and plays each one.
Lines starting with / are commands (/help lists them): pick an emotion,
switch to another training epoch, or try another reference clip.
Uses only the standard library; playback uses winsound, so Windows only.
"""

import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import winsound
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT / "Models" / "Freminet"
OUTPUT_DIR = PROJECT / "tts_output"
# GPT-SoVITS 整合包放在哪裏，每部電腦不同，寫在 config/tts.json
GSV = Path(json.loads((PROJECT / "config" / "tts.json").read_text(encoding="utf-8"))["gpt_sovits"])
PYTHON = GSV / "runtime" / "python.exe"
API = "http://127.0.0.1:9880"
EXP_NAME = "Freminet"

ALIASES = {
    "平靜": "calm", "開心": "happy", "溫柔": "gentle", "難過": "sad", "害羞": "shy",
    "驚訝": "surprised", "嚴肅": "serious", "生氣": "angry", "緊急": "urgent",
}

HELP = """\
打字按 Enter 就念出來。指令：
  /情緒 文字        用某種情緒念，例如「/angry 你怎么能这样！」或「/生氣 你怎么能这样！」
  /gpt              列出可用的 GPT 模型；/gpt e10 換成第 10 輪
  /sovits           列出可用的 SoVITS 模型；/sovits e4 換成第 4 輪
  /ref              顯示每種情緒目前用哪段參考音頻
  /ref angry        列出生氣組的候選；/ref angry 2 改用第 2 段
  /help             顯示這個說明
  q                 離開（會顯示目前的選擇，方便記下來）"""


def api_up():
    try:
        urllib.request.urlopen(f"{API}/docs", timeout=2)
        return True
    except (urllib.error.URLError, OSError):
        return False


def has_cuda():
    """Ask GPT-SoVITS's own torch whether there is an NVIDIA GPU it can use."""
    result = subprocess.run([str(PYTHON), "-s", "-c", "import torch; print(torch.cuda.is_available())"],
                            cwd=GSV, capture_output=True, text=True)
    return result.stdout.strip() == "True"


def start_api(info):
    if not PYTHON.exists():
        print(f"找不到 GPT-SoVITS：{GSV}\n請把 config/tts.json 的 gpt_sovits 改成整合包的資料夾")
        sys.exit(1)
    cuda = has_cuda()
    if not cuda:
        print("找不到 NVIDIA 顯卡，改用 CPU（每句會慢很多）")
    config = {"custom": {
        "bert_base_path": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
        "cnhuhbert_base_path": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
        "device": "cuda" if cuda else "cpu",
        "is_half": cuda,  # CPU 不支援半精度
        "version": info["version"],
        "t2s_weights_path": str(MODEL_DIR / info["gpt"]),
        "vits_weights_path": str(MODEL_DIR / info["sovits"]),
    }}
    config_path = GSV / "TEMP" / "freminet_tts.yaml"
    config_path.parent.mkdir(exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")  # JSON 也是合法的 YAML

    log = open(GSV / "TEMP" / "freminet_tts_api.log", "w", encoding="utf-8")
    env = {**os.environ, "PATH": f"{GSV / 'runtime'}{os.pathsep}{os.environ['PATH']}", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [str(PYTHON), "-s", "api_v2.py", "-a", "127.0.0.1", "-p", "9880", "-c", str(config_path)],
        cwd=GSV, stdout=log, stderr=subprocess.STDOUT, env=env,
    )
    print("正在載入模型，大約要半分鐘…", end="", flush=True)
    for _ in range(180 if cuda else 600):
        if proc.poll() is not None:
            print(f"\nAPI 啟動失敗，記錄在 {log.name}")
            sys.exit(1)
        if api_up():
            print(" 完成")
            return proc
        time.sleep(1)
        print(".", end="", flush=True)
    proc.terminate()
    print(f"\nAPI 太久沒有啟動，記錄在 {log.name}")
    sys.exit(1)


def set_weights(route, path):
    query = urllib.parse.urlencode({"weights_path": str(path)})
    try:
        urllib.request.urlopen(f"{API}/{route}?{query}", timeout=120)
        return True
    except urllib.error.HTTPError as e:
        print("換模型失敗：", e.read().decode("utf-8", "replace"))
        return False


def find_weights(version):
    """All saved epochs in the GPT-SoVITS weight folders, as {"e10": path}."""
    gpt = {p.stem.split("-")[-1]: p for p in (GSV / f"GPT_weights_{version}").glob(f"{EXP_NAME}-e*.ckpt")}
    sovits = {p.stem.split("_")[1]: p for p in (GSV / f"SoVITS_weights_{version}").glob(f"{EXP_NAME}_e*_s*.pth")}
    by_epoch = lambda d: dict(sorted(d.items(), key=lambda kv: int(kv[0][1:])))
    return by_epoch(gpt), by_epoch(sovits)


# 吞字檢查：訓練資料裏菲米尼最快大約每字 0.19 秒，比這更短就是有字被跳過了
MIN_SECONDS_PER_CHAR = 0.2
RETRIES = 3
SENTENCE = re.compile(r"[^。！？!?\n]+[。！？!?]*")
SPOKEN = re.compile(r"[一-鿿A-Za-z0-9]")


def split_sentences(text):
    """Split into sentences; very short ones like 「唔…」 are joined to the next."""
    out, carry = [], ""
    for s in SENTENCE.findall(text):
        s = carry + s.strip()
        carry = ""
        if len(SPOKEN.findall(s)) < 4:
            carry = s
        elif s:
            out.append(s)
    if carry:
        if out:
            out[-1] += carry
        else:
            out.append(carry)
    return out


def request_wav(text, ref):
    body = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": str(MODEL_DIR / ref["audio"]),
        "prompt_text": ref["text"],
        "prompt_lang": "zh",
        "text_split_method": "cut1",
        "media_type": "wav",
    }
    req = urllib.request.Request(f"{API}/tts", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        data = urllib.request.urlopen(req, timeout=300).read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", "replace")) from None
    with wave.open(io.BytesIO(data)) as w:
        return w.getparams(), w.readframes(w.getnframes())


def synthesize(text, ref):
    """Make a wav in tts_output/ and return its path; raises RuntimeError on failure.

    Each sentence is made on its own; one that comes out too short for its
    length has skipped words, so it is made again (keeping the longest try).
    """
    params, parts = None, []
    for sentence in split_sentences(text):
        # 「…」很容易讓模型提早結束，念的時候換成逗號（字幕不受影響）
        spoken = re.sub(r"[…]+|\.{3,}", "，", sentence).strip("，")
        need = len(SPOKEN.findall(spoken)) * MIN_SECONDS_PER_CHAR
        best = b""
        for _ in range(RETRIES):
            params, frames = request_wav(spoken, ref)
            if len(frames) > len(best):
                best = frames
            if len(best) / (params.framerate * params.sampwidth * params.nchannels) >= need:
                break
        parts.append(best)
    if not parts:
        raise RuntimeError("沒有可以念的文字")
    gap = b"\0" * int(params.framerate * 0.3) * params.sampwidth * params.nchannels
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S-%f}.wav"
    with wave.open(str(path), "wb") as w:
        w.setparams(params)
        w.writeframes(gap.join(parts))
    return path


def speak(text, ref):
    try:
        path = synthesize(text, ref)
    except RuntimeError as e:
        print("合成失敗：", e)
        return
    winsound.PlaySound(str(path), winsound.SND_FILENAME)


class Session:
    def __init__(self, info):
        self.refs = info["refs"]
        self.default = info["default_emotion"]
        self.gpt_all, self.sovits_all = find_weights(info["version"])
        # 開始時用的是匯出的模型，從檔名找出是第幾輪
        self.gpt = info["gpt"].rsplit("-", 1)[-1].removesuffix(".ckpt")
        self.sovits = info["sovits"].split("_")[1]
        self.pick = {emotion: 0 for emotion in self.refs}

    def emotion_names(self):
        return "、".join(f"{k}（{a}）" for a, k in ALIASES.items() if k in self.refs)

    def cmd_weights(self, kind, arg):
        options = self.gpt_all if kind == "gpt" else self.sovits_all
        current = self.gpt if kind == "gpt" else self.sovits
        if not arg:
            label = "GPT" if kind == "gpt" else "SoVITS"
            print(f"可用的 {label} 模型：" + "、".join(
                f"{e}{'（目前）' if e == current else ''}" for e in options))
            return
        epoch = arg if arg.startswith("e") else f"e{arg}"
        if epoch not in options:
            print(f"沒有 {epoch}，可用：{'、'.join(options)}")
            return
        print(f"換成 {options[epoch].name}…", end="", flush=True)
        route = "set_gpt_weights" if kind == "gpt" else "set_sovits_weights"
        if set_weights(route, options[epoch]):
            if kind == "gpt":
                self.gpt = epoch
            else:
                self.sovits = epoch
            print(" 完成")

    def cmd_ref(self, args):
        if not args:
            for emotion, items in self.refs.items():
                i = self.pick[emotion]
                print(f"  {emotion}：第 {i + 1} 段 {Path(items[i]['audio']).stem}  {items[i]['text']}")
            return
        emotion = ALIASES.get(args[0], args[0])
        if emotion not in self.refs:
            print(f"沒有這種情緒，可用：{self.emotion_names()}")
            return
        items = self.refs[emotion]
        if len(args) == 1:
            for i, item in enumerate(items):
                mark = "（目前）" if i == self.pick[emotion] else ""
                print(f"  {i + 1}. {Path(item['audio']).stem}  {item['text']}{mark}")
            return
        if not args[1].isdigit() or not 1 <= int(args[1]) <= len(items):
            print(f"請輸入 1 到 {len(items)}")
            return
        self.pick[emotion] = int(args[1]) - 1
        print(f"{emotion} 改用第 {args[1]} 段：{items[self.pick[emotion]]['text']}")

    def say(self, emotion, text):
        t0 = time.time()
        speak(text, self.refs[emotion][self.pick[emotion]])
        print(f"  [{emotion} 第 {self.pick[emotion] + 1} 段 / GPT {self.gpt} / SoVITS {self.sovits}] {time.time() - t0:.1f}s")

    def handle(self, line):
        if not line.startswith("/"):
            self.say(self.default, line)
            return
        word, _, rest = line[1:].partition(" ")
        args = rest.split()
        if word == "help":
            print(HELP)
        elif word in ("gpt", "sovits"):
            self.cmd_weights(word, args[0] if args else "")
        elif word == "ref":
            self.cmd_ref(args)
        elif ALIASES.get(word, word) in self.refs:
            if rest.strip():
                self.say(ALIASES.get(word, word), rest.strip())
        else:
            print(f"不認識的指令 /{word}，輸入 /help 看說明")

    def summary(self):
        print("\n目前的選擇：")
        print(f"  GPT：{self.gpt}　SoVITS：{self.sovits}")
        for emotion, items in self.refs.items():
            print(f"  {emotion}：{Path(items[self.pick[emotion]]['audio']).stem}")


def main():
    info = json.loads((MODEL_DIR / "model.json").read_text(encoding="utf-8"))
    session = Session(info)

    proc = None
    if api_up():
        print("API 已經在執行，換成 Freminet 的模型…")
        set_weights("set_gpt_weights", MODEL_DIR / info["gpt"])
        set_weights("set_sovits_weights", MODEL_DIR / info["sovits"])
    else:
        proc = start_api(info)

    print(f"\n{HELP}")
    print(f"\n可用情緒：{session.emotion_names()}，預設 {session.default}")
    print(f"音頻存在 {OUTPUT_DIR.name}/\n")
    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line.lower() in ("q", "quit", "exit"):
                break
            session.handle(line)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        session.summary()
        if proc:
            proc.terminate()
            print("已關閉 API")


if __name__ == "__main__":
    main()
