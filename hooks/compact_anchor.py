"""vibe-flow 压缩后读回（Claude Code SessionStart hook，matcher=compact）。

对话压缩后，摘要会丢细节，丢的常常是最早、最根本的那句意图。讨论中谈定的约定按 vibe-flow §4 记在
HANDOFF.md 的「已谈定」区；本钩子在压缩后把这一区原文注入给模型，并提示去读 NEEDS.md 的当前需求区。

锚点 = 带「已谈定」区的 HANDOFF（项目 docs/HANDOFF.md 或旁挂 <脚本名>.HANDOFF.md），或带「当前需求区」的
docs/NEEDS.md。从某个路径往上找最近一层有锚点的目录，碰到 git 仓库根或家目录就停；两样都没有的仓库（比如
公司代码）一律不管。

会话的 cwd 不等于正在干活的项目（用户常在公司仓里开会话、用绝对路径改个人项目），所以从对话记录里找
本会话碰过的路径（locate.py），按可信度分两档：
- 注入全文：读过或写过 HANDOFF / NEEDS 的项目、写过文件的项目（Write / Edit / esafe-code）、本会话为它开过
  worktree 的项目（主仓和 worktree 都算；python 落盘只能靠这一条认出来），再加 cwd；
- 只列路径：只读过普通文件、或只在 shell 命令里提到过（包括提到 HANDOFF）的项目——读过别的项目不等于在做
  它，不把它的约定当成当前任务的约束。
已删掉的 worktree 里的路径换成主仓里的同一路径（locate.worktree_moves）。
先按项目汇总（一个项目只要有一次上面那档的证据就算注入档），再按该项目最后一次被碰到（任何一种）的先后排，
越近越前——写过 A、又去写 B/C/D、最后回来读 A 的代码，A 排第一。注入的项目超过 MAX_INJECT_PROJECTS 个，
多的降为只列。
多个旁挂文件各自标明约束哪个脚本。区段合计过长时不截断，只列路径并要求读完——截掉一半的约定比没有更危险。

只用 stdlib。内部出错时退出码 1（非阻断、错误可见），绝不因钩子本身的 bug 影响会话。
"""
import json
import os
import re
import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from locate import read_rows, touched, worktree_moves  # noqa: E402

LABEL = re.compile(r"^\*\*[^*]+\*\*")
HEADING = re.compile(r"^(#{1,6})\s")
# 模板写 `**已谈定**：`，AI 自己建的常写成 `## 已谈定`，两种都认
BOLD_ANCHOR = re.compile(r"^\*\*已谈定\*\*")
HEAD_ANCHOR = re.compile(r"^(#{1,6})\s*已谈定")
# clarify-needs 的 NEEDS.md 都有这一节；公司仓里碰巧叫 NEEDS.md 的文件没有它
NEEDS_MARK = "当前需求区"
MAX_INJECT = 4000
MAX_INJECT_PROJECTS = 3
MAX_LISTED = 5
ANCHOR_NAMES = {"handoff.md", "needs.md"}


def agreed_section(path):
    """HANDOFF 里「已谈定」区的原文（含标签行）；没有这一区或内容为空返回 None。

    标题形式到同级或更高一级的标题为止，区内的子标题、粗体事项都算区内；粗体标签形式到下一个
    粗体标签或标题为止（模板里各区都是粗体标签）。
    """
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    out, level = None, None
    for line in lines:
        if out is None:
            if m := HEAD_ANCHOR.match(line):
                out, level = [line], len(m.group(1))
            elif BOLD_ANCHOR.match(line):
                out = [line]
            continue
        h = HEADING.match(line)
        if level is not None:
            if h and len(h.group(1)) <= level:
                break
        elif h or LABEL.match(line):
            break
        out.append(line)
    if not out:
        return None
    body = "\n".join(out[1:]).strip()
    if not body and level is None:
        body = BOLD_ANCHOR.sub("", out[0]).lstrip("（(：:").strip()
    return "\n".join(out).rstrip() if body else None


def _handoffs_in(d):
    cands = [d / "docs" / "HANDOFF.md", *sorted(d.glob("*.HANDOFF.md"))]
    return [p for p in cands if p.is_file()]


def _needs_in(d):
    p = d / "docs" / "NEEDS.md"
    try:
        return p if NEEDS_MARK in p.read_text(encoding="utf-8", errors="replace") else None
    except OSError:
        return None


def anchor_at(start, stop_at=None, _cache=None):
    """从 start（文件或目录）往上找最近一层有锚点的目录。

    返回 (目录, [(HANDOFF 路径, 已谈定区原文)...], NEEDS 路径或 None)；找不到返回 None。
    _cache 按目录记结果，同一会话里碰过的大量路径共用祖先目录时不重复读盘。
    """
    home = os.path.normcase(os.path.abspath(str(stop_at or Path.home())))
    cache = {} if _cache is None else _cache
    d = Path(start).resolve()
    if not d.is_dir():
        d = d.parent
    walked = []
    hit = None
    while True:
        key = os.path.normcase(str(d))
        if key in cache:
            hit = cache[key]
            break
        walked.append(key)
        found = [(p, s) for p in _handoffs_in(d) if (s := agreed_section(p))]
        needs = _needs_in(d)
        if found or needs:
            hit = (d, found, needs)
            break
        if (d / ".git").exists() or key == home or d.parent == d:
            break
        d = d.parent
    for key in walked:
        cache[key] = hit
    return hit


def _is_anchor_file(path):
    name = Path(path).name.lower()
    return name in ANCHOR_NAMES or name.endswith(".handoff.md")


def locate_projects(events, cwd, stop_at=None, opened=()):
    """本会话的锚点项目：返回 (注入全文的 [(目录, 锚点, NEEDS)], 只列路径的 [...])。"""
    cache, projects = {}, {}

    def note(path, strong, at):
        hit = anchor_at(path, stop_at, cache)
        if hit is None:
            return
        entry = projects.setdefault(os.path.normcase(str(hit[0])), {"hit": hit, "strong": False, "last": -1})
        entry["strong"] = entry["strong"] or strong
        entry["last"] = max(entry["last"], at)

    for at, (kind, path) in enumerate(events):
        note(path, kind == "write" or (kind == "read" and _is_anchor_file(path)), at)
    for path in (*opened, cwd):
        if path:
            note(path, True, -1)
    ordered = sorted(projects.values(), key=lambda e: e["last"], reverse=True)
    inject = [e["hit"] for e in ordered if e["strong"]]
    listed = inject[MAX_INJECT_PROJECTS:] + [e["hit"] for e in ordered if not e["strong"]]
    return inject[:MAX_INJECT_PROJECTS], listed[:MAX_LISTED]


def _scope(path):
    p = Path(path)
    return "整个项目" if p.name == "HANDOFF.md" else f"只约束脚本 {p.name[:-len('.HANDOFF.md')]}"


def render(projects, listed=()):
    anchors = [a for _, found, _ in projects for a in found]
    lines = ["[vibe-flow] 对话刚压缩过，摘要会丢细节（vibe-flow §4）。"]
    if len(projects) > 1:
        lines.append("本会话涉及几个项目，最近在做的排在前面：只对照当前任务所属项目的约定，别把别的项目的套过来。")
    elif len(anchors) > 1:
        lines.append("下面几份「已谈定」各自约束标明的对象：只对照当前任务涉及的那份，别把别的脚本的约定套过来。")
    total = sum(len(s) for _, s in anchors)
    if anchors and total <= MAX_INJECT:
        lines.append("讨论中谈定的约定以下面为准：")
        for path, section in anchors:
            lines += ["", f"--- {path}（{_scope(path)}）---", section]
    elif anchors:
        lines.append(f"「已谈定」区合计 {total} 字，没有注入全文。继续之前把当前任务涉及的那几份完整读完，别只读开头：")
        lines += [f"- {path}（{_scope(path)}）" for path, _ in anchors]
    lines.append("")
    for _, _, needs in projects:
        if needs:
            lines.append(f"再读 {needs} 的当前需求区（回看记录不用读）。")
    if listed:
        lines.append("本会话还读过或在命令里提到过下面这些项目，它们也记有约定；只有当前任务属于它们时才去读：")
        for _, found, needs in listed:
            lines += [f"- {path}（{_scope(path)}）" for path, _ in found]
            if needs:
                lines.append(f"- {needs}（当前需求区）")
        lines.append("")
    lines.append("继续之前对照本任务的原始目标和全部仍有效的约定：压缩后没再提到，不等于取消。"
                 "用户最新的明确指示可以更新旧约定（更新后改写那一条）；当前有效约定优先于压缩摘要。")
    return "\n".join(lines)


def main():
    data = json.loads(sys.stdin.read() or "{}")
    if data.get("source") != "compact":
        return 0
    cwd = data.get("cwd")
    if cwd and not os.path.isdir(cwd):
        cwd = None
    transcript = data.get("transcript_path")
    rows = read_rows(transcript) if transcript and os.path.isfile(transcript) else []
    moves = worktree_moves(rows, cwd)
    events = touched(rows, moves=moves, cwd=cwd)
    opened = [str(m) for m in moves.values()] + [wt for wt in moves if os.path.isdir(wt)]
    projects, listed = locate_projects(events, cwd, os.environ.get("VIBE_FLOW_DOC_GATE_HOME"), opened)
    if not projects and not listed:
        return 0
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                        "additionalContext": render(projects, listed)}},
                                ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.exit(main())
    except Exception as e:
        sys.stderr.write(f"vibe-flow compact_anchor 内部错误（已放行）：{e!r}\n")
        sys.exit(1)
