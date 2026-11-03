"""Codex 原生工具路径记录与压缩读回；内容选择和渲染与 Claude 共用。"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from compact_anchor import restore_context
from doc_gate_codex import _atomic_write, successful_paths
from locate import native_tool_rows, touched, worktree_moves


def session_dir(data):
    base = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    sid = data.get("session_id")
    if not base or not isinstance(sid, str) or not sid:
        raise ValueError("plugin data directory or session_id is unavailable")
    return Path(base) / "compact-anchor" / hashlib.sha256(sid.encode()).hexdigest()


def record(data):
    rows = native_tool_rows(data, successful_paths(data))
    cwd = data.get("cwd")
    events = touched(rows, cwd=cwd)
    moves = {key: str(value) for key, value in worktree_moves(rows, cwd).items()}
    if not events and not moves:
        return
    call_id = data.get("tool_use_id")
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("missing tool_use_id")
    key = str(data.get("turn_id", "")) + ":" + call_id
    path = session_dir(data) / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    _atomic_write(path, json.dumps({"at": time.time_ns(), "events": events, "moves": moves},
                                  ensure_ascii=False))


def saved_context(data):
    records = []
    for path in session_dir(data).glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("at"), int):
            raise ValueError("invalid compact-anchor record")
        events, moves = value.get("events"), value.get("moves")
        if not isinstance(events, list) or not all(isinstance(e, list) and len(e) == 2 and
                e[0] in {"read", "write", "shell"} and isinstance(e[1], str) for e in events):
            raise ValueError("invalid compact-anchor events")
        if not isinstance(moves, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                 for k, v in moves.items()):
            raise ValueError("invalid compact-anchor worktrees")
        records.append(value)
    events, moves = [], {}
    for value in sorted(records, key=lambda r: r["at"]):
        events += value["events"]
        moves.update(value["moves"])
    return events, moves


def clear(data):
    directory = session_dir(data)
    for path in directory.glob("*.json"):
        path.unlink()
    try:
        directory.rmdir()
    except FileNotFoundError:
        pass


def main():
    data = json.loads(sys.stdin.read() or "{}")
    event = data.get("hook_event_name")
    if event == "PostToolUse":
        record(data)
    elif event == "SessionEnd":
        clear(data)
    elif event == "SessionStart" and data.get("source") == "compact":
        events, moves = saved_context(data)
        return restore_context(data, [], events, moves)
    return 0


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"vibe-flow compact restore failed: {exc!r}\n")
        sys.exit(1)
