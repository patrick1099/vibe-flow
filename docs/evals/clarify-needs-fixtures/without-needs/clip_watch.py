"""后台盯着剪贴板，内容一变就追加进本地 history.jsonl。

存本地、不联网（对话里说了里面可能有密码）。
"""
import json
import time
from datetime import datetime
from pathlib import Path

try:
    import pyperclip
except ImportError:
    pyperclip = None

HISTORY = Path(__file__).with_name("history.jsonl")


def watch(interval=1.0):
    last = None
    while True:
        cur = pyperclip.paste() if pyperclip else ""
        if cur and cur != last:
            rec = {"ts": datetime.now().isoformat(timespec="seconds"), "text": cur}
            with HISTORY.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            last = cur
        time.sleep(interval)


if __name__ == "__main__":
    watch()
