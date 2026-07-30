"""在剪贴板历史里搜关键词。"""
import json
import sys
from pathlib import Path

HISTORY = Path(__file__).with_name("history.jsonl")


def search(keyword):
    if not HISTORY.exists():
        print("还没有历史记录。")
        return
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if keyword in rec["text"]:
            print(f'{rec["ts"]}  {rec["text"][:60]}')


if __name__ == "__main__":
    search(sys.argv[1] if len(sys.argv) > 1 else "")
