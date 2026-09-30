"""Codex 文档闸：UserPromptSubmit 记本轮开始时刻，PostToolUse 收集成功补丁，Stop 复用 doc_gate 判定。

本轮改过的文件 = 成功的 apply_patch ＋ git 仓库里本轮开始后改过、暂存或删掉的文件（经 shell / Python 落盘的也算）。
状态只存文件路径和开始时刻，按 session / turn / tool_use_id 隔离；不解析不稳定的 transcript。
内部错误退出 1、提示后放行，与原入口一致。Windows 用 py -3 调用。
"""
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import time
import uuid

from doc_gate import changed_since, evaluate, render_reason

SUCCESS = "Success. Updated the following files:"
PATCH_HEADERS = ("*** Add File: ", "*** Update File: ", "*** Delete File: ", "*** Move to: ")
# 不带 .json 后缀，take_paths 按 *.json 收路径记录时不会把它当成路径清单
START = "turn-start"


def successful_paths(data):
    """只认 apply_patch 的成功结果；输入补上移动前的路径。"""
    if data.get("tool_name") != "apply_patch":
        return []
    response = data.get("tool_response")
    if isinstance(response, str) and response.lstrip().startswith("{"):
        try:
            response = json.loads(response)
        except ValueError:
            return []
    if isinstance(response, dict):
        metadata = response.get("metadata") or {}
        if response.get("is_error") or response.get("isError"):
            return []
        if response.get("exit_code", metadata.get("exit_code", 0)) != 0:
            return []
        response = response.get("stdout", response.get("output"))
    lines = response.splitlines() if isinstance(response, str) else []
    try:
        success_at = lines.index(SUCCESS)
    except ValueError:
        return []
    for line in lines[:success_at]:
        status = re.fullmatch(r"Exit code:\s*(-?\d+)", line)
        if status and int(status.group(1)) != 0:
            return []
    names = [line[2:] for line in lines[success_at + 1:]
             if len(line) > 2 and line[:2] in {"A ", "M ", "D "}]
    if not names:
        return []
    inp = data.get("tool_input") or {}
    patch = inp.get("command", "") if isinstance(inp, dict) else ""
    for line in patch.splitlines():
        for prefix in PATCH_HEADERS:
            if line.startswith(prefix):
                names.append(line[len(prefix):])
                break
    cwd = Path(data["cwd"])
    return sorted({str((cwd / name).resolve()) for name in names if name})


def _digest(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing session_id / turn_id / tool_use_id")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def turn_dir(data):
    base = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not base:
        raise ValueError("plugin data directory is unavailable")
    return Path(base) / "doc-gate" / _digest(data.get("session_id")) / _digest(data.get("turn_id"))


def _atomic_write(target, text):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.parent / (uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def record_start(data):
    _atomic_write(turn_dir(data) / START, json.dumps({"at": time.time(), "cwd": data.get("cwd")},
                                                      ensure_ascii=False))


def take_start(data):
    """取出并删掉本轮开始记录，返回 (开始时刻, cwd)；没记录（钩子装在回合中途等）返回 (None, None)。"""
    target = turn_dir(data) / START
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    target.unlink()
    if not isinstance(value, dict) or not isinstance(value.get("at"), (int, float)):
        raise ValueError("invalid doc-gate turn-start record")
    return value["at"], value.get("cwd")


def record_paths(data, paths):
    _atomic_write(turn_dir(data) / (_digest(data.get("tool_use_id")) + ".json"),
                  json.dumps(paths, ensure_ascii=False))


def take_paths(data):
    directory = turn_dir(data)
    paths = set()
    for record in directory.glob("*.json"):
        values = json.loads(record.read_text(encoding="utf-8"))
        if not isinstance(values, list) or not all(isinstance(p, str) for p in values):
            raise ValueError("invalid doc-gate path record")
        paths.update(values)
        record.unlink()
    for parent in (directory, directory.parent):
        try:
            parent.rmdir()
        except OSError:
            pass
    return sorted(paths)


def main():
    data = json.loads(sys.stdin.read() or "{}")
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        record_start(data)
    elif event == "PostToolUse":
        paths = successful_paths(data)
        if paths:
            record_paths(data, paths)
    elif event in {"Stop", "Interrupt"}:
        since, cwd = take_start(data)
        paths = take_paths(data)
        if event == "Stop" and not data.get("stop_hook_active"):
            paths += changed_since(cwd or data.get("cwd"), since)
            issues = evaluate(paths, os.environ.get("VIBE_FLOW_DOC_GATE_HOME"))
            if issues:
                sys.stdout.write(json.dumps({"decision": "block", "reason": render_reason(issues)},
                                            ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.exit(main())
    except Exception as e:
        sys.stderr.write(f"vibe-flow codex doc_gate 内部错误（已放行）：{e!r}\n")
        sys.exit(1)
