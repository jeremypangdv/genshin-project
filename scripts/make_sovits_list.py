"""Build a GPT-SoVITS training list from the extracted speaker archive.

Each line is `wav_path|speaker|language|text`. Clips without a transcription
(combat shouts, breaths) and clips with in-game placeholders such as
{NICKNAME} are skipped, since their text does not match the audio. The audio
files themselves are left untouched.
"""

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "freminet_chinese"
OUT_FILE = DATA_DIR / "freminet.list"
SPEAKER = "Freminet"
LANGUAGE = "zh"

PLACEHOLDER = re.compile(r"\{[^}]*\}|<[^>]*>")


def main():
    with open(DATA_DIR / "metadata.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    lines, no_text, placeholder = [], 0, 0
    for row in rows:
        # A leading '#' marks lines with substitutions; it is never spoken.
        text = row["transcription"].strip().lstrip("#").strip()
        if not text:
            no_text += 1
            continue
        if PLACEHOLDER.search(text):
            placeholder += 1
            continue
        wav = (DATA_DIR / row["file"]).resolve()
        lines.append(f"{wav}|{SPEAKER}|{LANGUAGE}|{text}")

    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} lines to {OUT_FILE}")
    print(f"skipped {no_text} without text, {placeholder} with placeholders")


if __name__ == "__main__":
    main()
