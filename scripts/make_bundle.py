"""Make a folder to give to friends: double-click Freminet Chat.exe and chat, nothing to install.

    python scripts/make_bundle.py

Run build_exe.bat first. Puts everything in dist/Freminet Chat/ (about 22GB):
the app, the voice model, a trimmed copy of GPT-SoVITS (its runtime also runs
the app), and Ollama with qwen3:8b and the embedding model for memory.
Chats on this computer are not included.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "dist" / "Freminet Chat"
GSV = PROJECT / json.loads((PROJECT / "config" / "tts.json").read_text(encoding="utf-8"))["gpt_sovits"]
OLLAMA_APP = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama"
OLLAMA_MODELS = Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")
MODELS = [("qwen3", "8b"), ("qwen3-embedding", "0.6b")]  # 聊天模型、記憶用的 embedding 模型
PORT = 11435  # 和 launcher.py 一樣，不和朋友自己的 Ollama 撞


def robocopy(src, dst, *args):
    """Copy a folder (robocopy is much faster than shutil for GB-sized trees)."""
    code = subprocess.run(["robocopy", str(src), str(dst), "/E", "/MT:16", "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
                           *args]).returncode
    if code >= 8:
        sys.exit(f"複製失敗：{src}")


def main():
    exe = PROJECT / "Freminet Chat.exe"
    if not exe.is_file():
        sys.exit("先執行 build_exe.bat")
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, OUT)

    print("程式和角色資料…")
    for name in ("app", "characters", "scripts", "Models", "freminet profile"):
        robocopy(PROJECT / name, OUT / name, "/XD", "__pycache__")

    cfg = json.loads((PROJECT / "config" / "llm.json").read_text(encoding="utf-8"))
    provider = {**cfg["providers"]["ollama_8b"], "base_url": f"http://127.0.0.1:{PORT}/v1"}
    (OUT / "config").mkdir(exist_ok=True)
    (OUT / "config" / "llm.json").write_text(json.dumps(
        {"active": "ollama_8b", "providers": {"ollama_8b": provider}, "history_turns": cfg["history_turns"],
         "embed_model": cfg["embed_model"]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "config" / "tts.json").write_text(json.dumps({"gpt_sovits": "GPT-SoVITS"}, indent=2), encoding="utf-8")

    print("GPT-SoVITS（不要訓練用的東西）…")
    robocopy(GSV, OUT / "GPT-SoVITS", "/XD", "logs", "TEMP", "output", "uvr5", "asr", "__pycache__",
             *[d.name for d in GSV.glob("*_weights*")])
    for d in GSV.glob("*_weights*"):  # 留空資料夾，免得有程式找不到
        (OUT / "GPT-SoVITS" / d.name).mkdir(exist_ok=True)
    # users.pth 寫死了 D: 的整合包路徑，換成相對 site-packages 的路徑，放哪裏都能用
    (OUT / "GPT-SoVITS" / "runtime" / "Lib" / "site-packages" / "users.pth").write_text("".join(
        f"../../../{d}\n" for d in ("", "GPT_SoVITS/BigVGAN", "tools", "tools/asr", "GPT_SoVITS", "tools/uvr5")),
        encoding="utf-8")
    # 聊天程式用 GPT-SoVITS 的 Python 跑，只差 Flask（配合裏面的 Werkzeug 2.2）
    subprocess.run([str(OUT / "GPT-SoVITS" / "runtime" / "python.exe"), "-m", "pip", "install", "-q",
                    "--disable-pip-version-check", "flask==2.2.5"], check=True)

    print("Ollama（不要 AMD 的 rocm）…")
    (OUT / "ollama").mkdir(exist_ok=True)
    shutil.copy2(OLLAMA_APP / "ollama.exe", OUT / "ollama")
    robocopy(OLLAMA_APP / "lib", OUT / "ollama" / "lib", "/XD", "rocm")
    (OUT / "ollama" / "models" / "blobs").mkdir(parents=True, exist_ok=True)
    for name, tag in MODELS:
        manifest = OLLAMA_MODELS / "manifests" / "registry.ollama.ai" / "library" / name / tag
        if not manifest.is_file():
            sys.exit(f"先下載模型：ollama pull {name}:{tag}")
        target = OUT / "ollama" / "models" / manifest.relative_to(OLLAMA_MODELS)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, target)
        info = json.loads(manifest.read_text(encoding="utf-8"))
        for layer in [info["config"], *info["layers"]]:
            blob = layer["digest"].replace(":", "-")
            dst = OUT / "ollama" / "models" / "blobs" / blob
            if not dst.exists() or dst.stat().st_size != layer["size"]:
                shutil.copy2(OLLAMA_MODELS / "blobs" / blob, dst)

    (OUT / "使用說明.txt").write_text(README, encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e9
    print(f"完成：{OUT}（{size:.1f} GB）")


README = """\
Freminet Chat

雙擊「Freminet Chat.exe」就能和菲米尼聊天，不用另外安裝任何東西。

- 第一次打開要等一兩分鐘（載入語音和聊天模型），之後會快很多
- 整個資料夾要放在一起，不要只拿走 exe
- 資料夾路徑最好只有英文和數字，例如 D:\\Freminet Chat
- 最好有 NVIDIA 顯卡（6GB 顯存以上）。沒有的話也能用，但每句回覆要等很久
- 出錯的話，把資料夾裏的 app.log 傳給我
"""

main()
