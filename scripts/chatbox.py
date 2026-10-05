"""Chat-style window: type a line, hear it in Freminet's voice.

Uses the exported model in Models/Freminet/ through scripts/tts.py.
Start a line with an emotion in brackets, e.g. "（生氣）你怎么能这样！",
"(angry) ..." or "/angry ...", to pick that emotion's reference clip.
"""

import json
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

import tts

EMOTION = re.compile(r"^\s*(?:[（(]\s*([^）)]+?)\s*[）)]|/(\S+))\s*")
NAMES = {v: k for k, v in tts.ALIASES.items()}


def parse(line, refs, default):
    m = EMOTION.match(line)
    if not m:
        return default, line
    tag = m.group(1) or m.group(2)
    emotion = tts.ALIASES.get(tag, tag)
    if emotion not in refs:
        return None, tag
    return emotion, line[m.end():].strip()


class ChatBox:
    def __init__(self, root):
        self.info = json.loads((tts.MODEL_DIR / "model.json").read_text(encoding="utf-8"))
        self.refs = self.info["refs"]
        self.default = self.info["default_emotion"]
        self.proc = None
        self.busy = False
        self.events = queue.Queue()  # 背景執行緒不能直接改視窗，交給主執行緒做

        root.title("Freminet")
        root.geometry("520x600")
        self.root = root

        self.log = scrolledtext.ScrolledText(root, wrap=tk.WORD, state=tk.DISABLED, font=("Microsoft JhengHei", 11))
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        self.log.tag_config("me", foreground="#1a5fb4")
        self.log.tag_config("info", foreground="#777777")
        self.log.tag_config("error", foreground="#c01c28")

        bar = tk.Frame(root)
        bar.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.entry = tk.Entry(bar, font=("Microsoft JhengHei", 12))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.entry.bind("<Return>", lambda _: self.send())
        self.button = tk.Button(bar, text="說", width=6, command=self.send)
        self.button.pack(side=tk.LEFT, padx=(6, 0))

        emotions = "、".join(f"（{NAMES[e]}）" for e in self.refs if e in NAMES)
        self.write(f"模型：GPT {self.info['gpt']}　SoVITS {self.info['sovits']}\n", "info")
        self.write(f"在句子前面加情緒，例如「（生氣）你怎么能这样！」\n可用：{emotions}\n不加就是（平靜）\n\n", "info")
        self.set_ready(False, "載入模型中，大約半分鐘…")
        threading.Thread(target=self.load, daemon=True).start()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll()

    def poll(self):
        while not self.events.empty():
            self.events.get()()
        self.root.after(100, self.poll)

    def write(self, text, tag=None):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, text, tag)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def set_ready(self, ready, status=""):
        self.busy = not ready
        self.button.config(state=tk.NORMAL if ready else tk.DISABLED)
        self.root.title(f"Freminet　{status}" if status else "Freminet")
        if ready:
            self.entry.focus_set()

    def load(self):
        try:
            if tts.api_up():
                tts.set_weights("set_gpt_weights", tts.MODEL_DIR / self.info["gpt"])
                tts.set_weights("set_sovits_weights", tts.MODEL_DIR / self.info["sovits"])
            else:
                self.proc = tts.start_api(self.info)
        except (Exception, SystemExit):
            log = tts.GSV / "TEMP" / "freminet_tts_api.log"
            self.events.put(lambda: (self.write(f"模型載入失敗，記錄在 {log}\n", "error"),
                                        self.set_ready(False, "載入失敗")))
            return
        self.events.put(lambda: (self.write("可以開始打字了\n\n", "info"), self.set_ready(True)))

    def send(self):
        line = self.entry.get().strip()
        if not line or self.busy:
            return
        emotion, text = parse(line, self.refs, self.default)
        if emotion is None:
            self.write(f"沒有（{text}）這種情緒\n", "error")
            return
        if not text:
            return
        self.entry.delete(0, tk.END)
        self.write(f"（{NAMES.get(emotion, emotion)}）{text}\n", "me")
        self.set_ready(False, "說話中…")
        threading.Thread(target=self.speak, args=(emotion, text), daemon=True).start()

    def speak(self, emotion, text):
        t0 = time.time()
        try:
            tts.speak(text, self.refs[emotion][0])
            msg, tag = f"  {time.time() - t0:.1f} 秒\n\n", "info"
        except Exception as e:
            msg, tag = f"  失敗：{e}\n\n", "error"
        self.events.put(lambda: (self.write(msg, tag), self.set_ready(True)))

    def close(self):
        if self.proc:
            self.proc.terminate()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ChatBox(root)
    root.mainloop()
