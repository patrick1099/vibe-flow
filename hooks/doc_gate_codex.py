"""Codex 文档闸：UserPromptSubmit 记本轮开始时刻，PostToolUse 收集成功补丁，Stop 复用 doc_gate 判定。

本轮改过的文件 = 成功的 apply_patch ＋ 本轮开始时的 cwd 和补丁所涉路径各自所在 git 仓库里，本轮开始后改过、暂存或
删掉的文件（经 shell / Python 落盘的也算）。原生 shell 输入里的路径只补充候选仓库，仍以实际 git 变动为准。
状态只存文件路径、开始时刻和明确收工标记，按 session / turn / tool_use_id 隔离，不存用户正文。
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

from locate import native_shell_paths

from doc_gate import (changed_in_repos, changed_since, evaluate, model_drift,  # noqa: F401  changed_since 供测试核对共用
                      render_model_reason, render_reason)

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


def closeout_request(prompt, cwd=None):
    """只认整句明确指令；不留用户正文，也不把引述、否定和讨论交接当成收工。"""
    if not isinstance(prompt, str) or len(prompt) > 4096:
        return False, []
    text = prompt.strip().rstrip(".。!！").strip()
    if not text or any(c in text for c in "\r\n?？"):
        return False, []
    text = re.sub(r"^(?:(?:请|麻烦|帮我|你|先|现在)\s*)+|^please\s+", "", text, flags=re.I)
    text = re.sub(r"(?:吧|即可|就好)$|,?\s+please$", "", text, flags=re.I).strip()
    if re.fullmatch(r"(?:(?:我们|咱们)?(?:今天|这轮|这次)?(?:就|先)?(?:收工|收尾|收个尾|到这(?:里|儿)?)(?:了)?|"
                    r"wrap (?:it up|up(?: this (?:task|session))?)|(?:finish|close out) (?:this|the) (?:task|session))",
                    text, re.I):
        return True, []
    verb = r"(?:更新|写|补写|补齐|补|整理|生成|刷新|同步)"
    direct = re.fullmatch(verb + r"(?:一下|下|一份|一个|个|份)?\s*(.+?)", text, re.I)
    reverse = re.fullmatch(r"把\s*(.+?)\s*" + verb + r"(?:一下|下|好)?", text, re.I)
    english = re.fullmatch(r"(?:update|write|prepare|refresh|create)\s+(?:(?:the|a|our)\s+)?(.+)", text, re.I)
    match = direct or reverse or english
    if not match:
        return False, []
    target = match[1].strip()
    for left, right in (("\x60", "\x60"), ('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("<", ">")):
        if len(target) >= 2 and target.startswith(left) and target.endswith(right):
            target = target[1:-1]
            break
    if re.fullmatch(r"handoff(?:\.md)?|交接(?:文档|记录|说明|文件)?", target, re.I):
        return True, []
    if ("\0" not in target and re.match(r"(?:[A-Za-z]:[/\\]|[/\\]|[\w.-]+[/\\])", target)
            and Path(target).name.casefold() == "handoff.md"):
        return True, [os.path.abspath(os.path.join(cwd or os.curdir, target))]
    return False, []


def record_start(data):
    cwd = data.get("cwd")
    closeout, targets = closeout_request(data.get("prompt"), cwd)
    _atomic_write(turn_dir(data) / START, json.dumps({"at": time.time(), "cwd": cwd,
                                                      "closeout": closeout, "targets": targets}, ensure_ascii=False))


def take_start(data):
    """取出并删掉本轮开始记录；兼容未记收工意图的旧记录。"""
    target = turn_dir(data) / START
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None, False, []
    target.unlink()
    if not isinstance(value, dict) or not isinstance(value.get("at"), (int, float)):
        raise ValueError("invalid doc-gate turn-start record")
    return value["at"], value.get("cwd"), value.get("closeout") is True, value.get("targets", [])


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


def record_candidates(data):
    paths = native_shell_paths(data)
    if paths:
        _atomic_write(turn_dir(data) / (_digest(data.get("tool_use_id")) + ".candidates"),
                      json.dumps(paths, ensure_ascii=False))


def take_candidates(data):
    out = []
    for record in turn_dir(data).glob("*.candidates"):
        values = json.loads(record.read_text(encoding="utf-8"))
        if not isinstance(values, list) or not all(isinstance(p, str) for p in values):
            raise ValueError("invalid doc-gate candidate record")
        out += values
        record.unlink()
    return list(dict.fromkeys(out))


def main():
    data = json.loads(sys.stdin.read() or "{}")
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        record_start(data)
    elif event == "PreToolUse":
        record_candidates(data)
    elif event == "PostToolUse":
        record_candidates(data)
        paths = successful_paths(data)
        if paths:
            record_paths(data, paths)
    elif event in {"Stop", "Interrupt"}:
        since, cwd, closeout, targets = take_start(data)
        candidates = take_candidates(data)
        paths = take_paths(data)
        if event == "Stop" and not data.get("stop_hook_active"):
            paths += changed_in_repos([cwd or data.get("cwd"), *paths, *candidates], since)
            stop_at = os.environ.get("VIBE_FLOW_DOC_GATE_HOME")
            if closeout:
                # 明确命令或确证写入优先；shell 只读提及仅在 cwd 无法定位时消歧。
                handoffs = targets or [p for p in paths if Path(p).name.casefold() == "handoff.md"]
                hints = [p for p in candidates if Path(p).name.casefold() == "handoff.md"]
                issues = evaluate(paths, stop_at, closeout_cwd=cwd or data.get("cwd"),
                                  closeout_targets=handoffs, closeout_hints=hints)
            else:
                issues = evaluate(paths, stop_at)
            drift = model_drift(paths, stop_at)
            if issues or drift:
                reasons = ([render_reason(issues)] if issues else []) + ([render_model_reason(drift)] if drift else [])
                sys.stdout.write(json.dumps({"decision": "block", "reason": "\n\n".join(reasons)},
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
