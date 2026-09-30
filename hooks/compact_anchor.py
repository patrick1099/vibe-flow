"""vibe-flow 压缩后读回（Claude Code SessionStart hook，matcher=compact）。

对话压缩后，摘要会丢细节，丢的常常是最早、最根本的那句意图。讨论中谈定的约定按 vibe-flow §4 记在
HANDOFF.md 的「已谈定」区；本钩子在压缩后把这一区原文注入给模型，并提示去读 NEEDS.md 的当前需求区。

只从 cwd 往上找到最近一层有锚点的目录：带「已谈定」区的 HANDOFF（项目 docs/HANDOFF.md 或旁挂
<脚本名>.HANDOFF.md），或带「当前需求区」的 docs/NEEDS.md；碰到 git 仓库根或家目录就停。两样都没有的
仓库（比如公司代码）一律不管。多个旁挂文件各自标明约束哪个脚本。区段合计过长时不截断，只列路径并
要求读完——截掉一半的约定比没有更危险。

只用 stdlib。内部出错时退出码 1（非阻断、错误可见），绝不因钩子本身的 bug 影响会话。
"""
import json
import os
import re
import sys
from pathlib import Path

LABEL = re.compile(r"^\*\*[^*]+\*\*")
HEADING = re.compile(r"^(#{1,6})\s")
# 模板写 `**已谈定**：`，AI 自己建的常写成 `## 已谈定`，两种都认
BOLD_ANCHOR = re.compile(r"^\*\*已谈定\*\*")
HEAD_ANCHOR = re.compile(r"^(#{1,6})\s*已谈定")
# clarify-needs 的 NEEDS.md 都有这一节；公司仓里碰巧叫 NEEDS.md 的文件没有它
NEEDS_MARK = "当前需求区"
MAX_INJECT = 4000


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


def find_anchors(cwd, stop_at=None):
    """从 cwd 往上找最近一层有锚点的目录，返回 ([(HANDOFF 路径, 已谈定区原文)...], NEEDS 路径或 None)。"""
    home = os.path.normcase(os.path.abspath(str(stop_at or Path.home())))
    d = Path(cwd).resolve()
    while True:
        found = [(p, s) for p in _handoffs_in(d) if (s := agreed_section(p))]
        needs = _needs_in(d)
        if found or needs:
            return found, needs
        if (d / ".git").exists() or os.path.normcase(str(d)) == home or d.parent == d:
            return [], None
        d = d.parent


def _scope(path):
    p = Path(path)
    return "整个项目" if p.name == "HANDOFF.md" else f"只约束脚本 {p.name[:-len('.HANDOFF.md')]}"


def render(anchors, needs):
    lines = ["[vibe-flow] 对话刚压缩过，摘要会丢细节（vibe-flow §4）。"]
    if len(anchors) > 1:
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
    if needs:
        lines.append(f"再读 {needs} 的当前需求区（回看记录不用读）。")
    lines.append("继续之前对照本任务的原始目标和全部仍有效的约定：压缩后没再提到，不等于取消。"
                 "用户最新的明确指示可以更新旧约定（更新后改写那一条）；当前有效约定优先于压缩摘要。")
    return "\n".join(lines)


def main():
    data = json.loads(sys.stdin.read() or "{}")
    if data.get("source") != "compact":
        return 0
    cwd = data.get("cwd")
    if not cwd or not os.path.isdir(cwd):
        return 0
    anchors, needs = find_anchors(cwd, os.environ.get("VIBE_FLOW_DOC_GATE_HOME"))
    if not anchors and not needs:
        return 0
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                        "additionalContext": render(anchors, needs)}},
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
