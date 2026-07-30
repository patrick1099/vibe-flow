"""写 / 翻本地日记，存到本机 diary.jsonl。"""
import json
import sys
from datetime import datetime
from pathlib import Path

import telemetry

STORE = Path(__file__).with_name("diary.jsonl")


def add(text):
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "text": text}
    with STORE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    telemetry.report("add", len(text))


def show():
    if not STORE.exists():
        print("还没有日记。")
        return
    for line in STORE.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        print(f'{rec["ts"]}  {rec["text"]}')
    telemetry.report("show", 0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        show()
    else:
        add(" ".join(sys.argv[1:]))
