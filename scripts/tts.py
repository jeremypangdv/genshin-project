"""Type text, hear it in Freminet's voice.

Starts GPT-SoVITS api_v2.py in the background with the exported model in
Models/Freminet/, then reads lines from the keyboard and plays each one.
Prefix a line with /<emotion> to pick a reference clip, e.g. "/angry ...".
Uses only the standard library; playback uses winsound, so Windows only.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import winsound
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT / "Models" / "Freminet"
OUTPUT_DIR = PROJECT / "tts_output"
GSV = Path(r"D:\characters\GPT-SoVITS-Rin\GPT-SoVITS-v2pro-20250604")
PYTHON = GSV / "runtime" / "python.exe"
API = "http://127.0.0.1:9880"

ALIASES = {
    "平靜": "calm", "開心": "happy", "溫柔": "gentle", "難過": "sad", "害羞": "shy",
    "驚訝": "surprised", "嚴肅": "serious", "生氣": "angry", "緊急": "urgent",
}


def api_up():
    try:
        urllib.request.urlopen(f"{API}/docs", timeout=2)
        return True
    except (urllib.error.URLError, OSError):
        return False


def start_api(info):
    config = {"custom": {
        "bert_base_path": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
        "cnhuhbert_base_path": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
        "device": "cuda",
        "is_half": True,
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
    for _ in range(180):
        if proc.poll() is not None:
            print(f"\nAPI 啟動失敗，記錄在 {log.name}")
            sys.exit(1)
        if api_up():
            print(" 完成")
            return proc
        time.sleep(1)
        print(".", end="", flush=True)
    proc.terminate()
    print(f"\nAPI 三分鐘內沒有啟動，記錄在 {log.name}")
    sys.exit(1)


def use_weights(info):
    # 9880 已經有 API 在跑時，換成我們的模型
    for route, name in [("set_gpt_weights", info["gpt"]), ("set_sovits_weights", info["sovits"])]:
        query = urllib.parse.urlencode({"weights_path": str(MODEL_DIR / name)})
        urllib.request.urlopen(f"{API}/{route}?{query}", timeout=120)


def speak(text, ref):
    body = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": str(MODEL_DIR / ref["audio"]),
        "prompt_text": ref["text"],
        "prompt_lang": "zh",
        "text_split_method": "cut5",
        "media_type": "wav",
    }
    req = urllib.request.Request(f"{API}/tts", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        wav = urllib.request.urlopen(req, timeout=300).read()
    except urllib.error.HTTPError as e:
        print("合成失敗：", e.read().decode("utf-8", "replace"))
        return
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.wav"
    path.write_bytes(wav)
    winsound.PlaySound(str(path), winsound.SND_FILENAME)


def parse(line, refs, default):
    if line.startswith("/"):
        tag, _, text = line[1:].partition(" ")
        emotion = ALIASES.get(tag, tag)
        if emotion not in refs:
            return None, line
        return emotion, text.strip()
    return default, line


def main():
    info = json.loads((MODEL_DIR / "model.json").read_text(encoding="utf-8"))
    refs = info["refs"]
    default = info["default_emotion"]

    proc = None
    if api_up():
        print("API 已經在執行，換成 Freminet 的模型…")
        use_weights(info)
    else:
        proc = start_api(info)

    names = "、".join(f"{k}（{a}）" for a, k in ALIASES.items() if k in refs)
    print(f"\n輸入文字後按 Enter 就會念出來，音頻存在 {OUTPUT_DIR.name}/")
    print("指定情緒：在前面加 /情緒，例如「/angry 你怎么能这样！」或「/生氣 你怎么能这样！」")
    print(f"可用情緒：{names}，預設 {default}")
    print("離開：輸入 q 或按 Ctrl+C\n")
    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line.lower() in ("q", "quit", "exit"):
                break
            emotion, text = parse(line, refs, default)
            if emotion is None:
                print(f"沒有這種情緒，可用：{names}")
                continue
            if not text:
                continue
            t0 = time.time()
            speak(text, refs[emotion][0])
            print(f"  [{emotion}] {time.time() - t0:.1f}s")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        if proc:
            proc.terminate()
            print("已關閉 API")


if __name__ == "__main__":
    main()
