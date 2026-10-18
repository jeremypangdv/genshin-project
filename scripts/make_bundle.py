"""Make a folder to give to friends: double-click Freminet Chat.exe and chat, nothing to install.

    python scripts/make_bundle.py

Run build_exe.bat first. Puts everything in dist/Freminet Chat/: the app, the
voice model and a trimmed copy of GPT-SoVITS (its runtime also runs the app).
Replies come from Gemini with the friend's own API key, asked for the first time
the chat opens; this computer's key and chats are not included.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "dist" / "Freminet Chat"
GSV = PROJECT / json.loads((PROJECT / "config" / "tts.json").read_text(encoding="utf-8"))["gpt_sovits"]


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
    for name in ("app", "characters", "scripts", "Models", "freminet profile", "tutorial video"):
        robocopy(PROJECT / name, OUT / name, "/XD", "__pycache__")

    cfg = json.loads((PROJECT / "config" / "llm.json").read_text(encoding="utf-8"))
    # 用 Gemini，但不放自己的 key：朋友第一次打開時輸入他自己的
    gemini = cfg["providers"]["gemini"]
    (OUT / "config").mkdir(exist_ok=True)
    (OUT / "config" / gemini["key_file"].split("/")[-1]).unlink(missing_ok=True)
    (OUT / "config" / "llm.json").write_text(json.dumps(
        {"active": "gemini", "providers": {"gemini": gemini}, "history_turns": cfg["history_turns"],
         "embed_model": cfg["embed_model"], "embed_related": cfg["embed_related"]},
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

    if (OUT / "ollama").exists():
        print("以前放的 ollama 資料夾（本地模型，約 6GB）現在用不到，可以刪掉")

    (OUT / "使用說明.txt").write_text(README, encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e9
    print(f"完成：{OUT}（{size:.1f} GB）")


README = """\
Freminet Chat

雙擊「Freminet Chat.exe」就能和菲米尼聊天，不用另外安裝任何東西。

- 第一次打開要等一兩分鐘（載入語音模型），之後會快很多
- 第一次打開會要你輸入 Gemini API key（免費），按「怎麼拿 API key？」照步驟做
- 每天的免費次數用完了，要等重置後才能再聊
- 整個資料夾要放在一起，不要只拿走 exe
- 資料夾路徑最好只有英文和數字，例如 D:\\Freminet Chat
- 最好有 NVIDIA 顯卡，語音會快很多。沒有的話也能用，只是語音要等比較久
- 出錯的話，把資料夾裏的 app.log 傳給我
"""

main()
