"""vibe-flow 文档闸（Claude Code Stop hook）。

本轮用 Write / Edit 改了 vibe 项目的代码时，检查 BLUEPRINT.md / CHANGELOG.md：
- 缺文档 → 拦下，要求补齐；
- 两份都没动 → 拦一次，让 AI 明确判断“要不要记”，回应后放行。
同一轮只拦一次（stop_hook_active），判断权留给 AI。非 vibe 项目（无标记）一律不管。

只用 stdlib。内部出错时退出码 1（非阻断、错误可见），绝不因闸本身的 bug 卡住会话。
"""
import json
import os
import re
import sys
from pathlib import Path

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
DOC_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}
SCRIPT_MARK = re.compile(r"结构:\s*vibe-scripts/(standard|toolkit)\b")
APPS_MARK = "架构约束（vibe-apps）"
HEADER_LINES = 15
MAX_PY_SCAN = 60


# ---------- 对话记录 → 本轮写过的文件 ----------

def _is_human_prompt(row):
    if row.get("type") != "user" or row.get("isMeta"):
        return False
    origin = row.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    content = (row.get("message") or {}).get("content")
    return isinstance(content, str) and not content.lstrip().startswith("<")


def _content_items(row):
    content = (row.get("message") or {}).get("content")
    return [x for x in content if isinstance(x, dict)] if isinstance(content, list) else []


def turn_written_paths(rows):
    """本轮成功写过的文件：失败的调用（is_error）和没有结果的调用都不算。"""
    start = 0
    for i, row in enumerate(rows):
        if _is_human_prompt(row):
            start = i + 1
    calls = []
    ok_ids = set()
    for row in rows[start:]:
        for item in _content_items(row):
            kind = item.get("type")
            if row.get("type") == "assistant" and kind == "tool_use" and item.get("name") in WRITE_TOOLS:
                inp = item.get("input") or {}
                p = inp.get("file_path") or inp.get("notebook_path")
                if p:
                    calls.append((item.get("id"), p))
            elif row.get("type") == "user" and kind == "tool_result" and not item.get("is_error"):
                ok_ids.add(item.get("tool_use_id"))
    return [p for tool_id, p in calls if tool_id in ok_ids]


def read_rows(transcript_path):
    rows = []
    with open(transcript_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


# ---------- 文件 → 所属 vibe 项目 ----------

def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def header_marker(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = "".join(f.readline() for _ in range(HEADER_LINES))
    except OSError:
        return None
    m = SCRIPT_MARK.search(head)
    return m.group(1) if m else None


def _dir_is_project_root(d):
    # 只认 BLUEPRINT.md：CHANGELOG.md 太常见，公司仓也可能有，不能当 vibe 标记
    if (d / "docs" / "BLUEPRINT.md").exists():
        return True
    for name in ("AGENTS.md", "CLAUDE.md"):  # CLAUDE.md 兼容 0.9.0 之前建的应用
        f = d / name
        if f.is_file():
            try:
                if APPS_MARK in f.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                pass
    pys = sorted(d.glob("*.py"))[:MAX_PY_SCAN]
    return any(header_marker(p) == "toolkit" for p in pys)


def find_project(file_path, stop_at=None):
    """返回 (项目根, BLUEPRINT 路径, CHANGELOG 路径)；不是 vibe 项目返回 None。"""
    p = Path(file_path)
    home = _norm(stop_at or Path.home())
    d = p.parent
    while True:
        if d.is_dir() and _dir_is_project_root(d):
            return d, d / "docs" / "BLUEPRINT.md", d / "docs" / "CHANGELOG.md"
        if (d / ".git").exists() or _norm(d) == home or d.parent == d:
            break
        d = d.parent
    if header_marker(p) == "standard":
        # 同目录没有别的 .py = 独占目录，文档进 docs/；否则和别的脚本挤在一起，用旁挂文件
        if not any(q.name != p.name for q in p.parent.glob("*.py")):
            return p.parent, p.parent / "docs" / "BLUEPRINT.md", p.parent / "docs" / "CHANGELOG.md"
        return (p.parent,
                p.with_name(p.stem + ".BLUEPRINT.md"),
                p.with_name(p.stem + ".CHANGELOG.md"))
    return None


# ---------- 判定 ----------

def evaluate(paths, stop_at=None):
    written = {_norm(p) for p in paths}
    projects = {}
    for raw in paths:
        if Path(raw).suffix.lower() in DOC_SUFFIXES:
            continue
        found = find_project(raw, stop_at)
        if not found:
            continue
        root, bp, cl = found
        key = (_norm(bp), _norm(cl))
        projects.setdefault(key, {"root": root, "bp": bp, "cl": cl, "code": []})
        projects[key]["code"].append(raw)

    issues = []
    for proj in projects.values():
        bp, cl = proj["bp"], proj["cl"]
        missing = [x.name for x in (bp, cl) if not x.exists()]
        if missing:
            issues.append(("missing", proj, missing))
        elif _norm(bp) not in written and _norm(cl) not in written:
            issues.append(("untouched", proj, []))
    return issues


def render_reason(issues):
    lines = ["[vibe-flow 文档闸] 本轮改了下面这些 vibe 项目的代码："]
    for kind, proj, missing in issues:
        where = proj["root"]
        if kind == "missing":
            lines.append(f"- {where}：缺 {' / '.join(missing)}。按 living-blueprint 补齐"
                         f"（应在 {proj['bp'].parent}），出生时两份一起建，CHANGELOG 第一条记为什么要做它。")
        else:
            lines.append(f"- {where}：BLUEPRINT 和 CHANGELOG 都没动。判断一次：")
    if any(k == "untouched" for k, _, _ in issues):
        lines += [
            "  · 功能、I/O 契约或硬约束变了 → 覆盖蓝图对应小节，并在 CHANGELOG 顶部加一条；",
            "  · 修了用户碰到过的 bug、改了用户嫌弃的体验，蓝图本来就对 → 只在 CHANGELOG 顶部加一条；",
            "  · 纯内部重构、用户没感知过 → 不用记，在回复里用一句话说明为什么不用记。",
        ]
    lines.append("本提醒每轮只出现一次；判断权在你，别为过闸写假条目。")
    return "\n".join(lines)


def main():
    data = json.loads(sys.stdin.read() or "{}")
    if data.get("stop_hook_active"):
        return 0
    transcript = data.get("transcript_path")
    if not transcript or not os.path.isfile(transcript):
        return 0
    paths = turn_written_paths(read_rows(transcript))
    if not paths:
        return 0
    stop_at = os.environ.get("VIBE_FLOW_DOC_GATE_HOME")
    issues = evaluate(paths, stop_at)
    if issues:
        sys.stdout.write(json.dumps({"decision": "block", "reason": render_reason(issues)},
                                    ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.exit(main())
    except Exception as e:
        sys.stderr.write(f"vibe-flow doc_gate 内部错误（已放行）：{e!r}\n")
        sys.exit(1)
