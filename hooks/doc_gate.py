"""vibe-flow 文档闸（Claude Code Stop hook）。

本轮改了 vibe 项目的代码时，检查 BLUEPRINT.md / CHANGELOG.md：
- 缺文档 → 拦下，要求补齐；
- 两份都早于这批代码的最后一次修改 → 拦一次，让 AI 派 fork 维护文档，或说明为什么不用记。
本轮改过的文件 = 对话记录里成功的 Write / Edit ＋ 本轮涉及的 git 仓库里本轮开始后改过、暂存或删掉的文件
（经 shell / Python 落盘的也算）。涉及的仓库 = 会话 cwd 所在仓库，加本轮写过、或在 shell 命令里写出来的
路径所在仓库（见 locate.py）：用户常在一个仓库里开会话、用绝对路径改别的仓库，只扫 cwd 会漏。
文档是否跟上只看磁盘 mtime，所以 fork 写的文档也认得出。
还有后台子 agent 在跑时先不拦：它完成后主 agent 会被唤醒，本轮再结束时重判。常驻的 shell 后台任务
（开发服务器、tail -f）不算，否则闸会一直不响。
在 worktree（`.worktrees/<名>/`、`.claude/worktrees/<名>/`）里改、本轮内合并回主仓并删掉 worktree 的，
按主仓里同一相对路径判，见 merged_worktree_path。
同一轮只拦一次（stop_hook_active，只防循环）。AI 判断这批不用记时跑提示里的回执命令（receipt.py），
之后同一份代码快照不再提醒——后台任务完成把 AI 唤醒、本轮再结束时也不会重复拦。判断权留给 AI。
非 vibe 项目（无标记）一律不管。

只用 stdlib。内部出错时退出码 1（非阻断、错误可见），绝不因闸本身的 bug 卡住会话。
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path

# session-sweep 等按文件路径加载本模块时，hooks 目录不在 sys.path 里
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import receipt  # noqa: E402
from locate import (WRITE_TOOLS, content_items, is_human_prompt, last_prompt_index, moved,  # noqa: E402,F401
                    read_rows, repos_of, touched, worktree_moves)

DOC_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}
# git 扫描里未跟踪的新文件只认这些后缀：跑工具产生的数据、日志不算代码改动
SCAN_SUFFIXES = {".py", ".pyw", ".js", ".mjs", ".ts", ".html", ".css", ".ps1", ".sh", ".bat", ".cmd", ".toml"}
SCRIPT_MARK = re.compile(r"结构:\s*vibe-scripts/(standard|toolkit)\b")
APPS_MARK = "架构约束（vibe-apps）"
HEADER_LINES = 15
MAX_PY_SCAN = 60
GIT_TIMEOUT = 8
# 一轮里补扫的 git 仓库上限：每个仓库要跑几次 git，Stop 钩子不能拖太久
MAX_SCAN_REPOS = 6
# 一次合并（checkout）把代码和文档写回主仓，前后差不过几秒；文档在这个窗口内就算和代码同批
MERGE_SLACK = 5


# ---------- 对话记录 → 本轮写过的文件 ----------

def turn_written_paths(rows):
    """本轮成功写过的文件：失败的调用（is_error）和没有结果的调用都不算。"""
    calls = []
    ok_ids = set()
    for row in rows[last_prompt_index(rows):]:
        for item in content_items(row):
            kind = item.get("type")
            if row.get("type") == "assistant" and kind == "tool_use" and item.get("name") in WRITE_TOOLS:
                inp = item.get("input") or {}
                p = inp.get("file_path") or inp.get("notebook_path")
                if p:
                    calls.append((item.get("id"), p))
            elif row.get("type") == "user" and kind == "tool_result" and not item.get("is_error"):
                ok_ids.add(item.get("tool_use_id"))
    return [p for tool_id, p in calls if tool_id in ok_ids]


def turn_start(rows):
    """本轮开始时刻：最后一条人类消息的 timestamp（epoch 秒），拿不到返回 None。

    后台任务完成的通知 origin 是 task-notification，不算人类消息，所以 fork 回来后本轮范围不变。
    """
    stamp = None
    for row in rows:
        if is_human_prompt(row):
            stamp = row.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ---------- 文件 → 最后一次变动的时刻 ----------

def changed_at(path):
    """文件最后一次变动的时刻；已删除的按最近一层还在的目录的 mtime 算。

    删除条目会刷新所在目录的 mtime，所以这个值只会不早于删除那一刻：拿它判「文档是否晚于删除」
    宁可多拦一次，不会放过「先改文档、后删代码」。什么都不在了返回 None。
    """
    p = Path(path)
    for q in (p, *p.parents):
        try:
            return q.stat().st_mtime
        except OSError:
            continue
    return None


# ---------- worktree → 主仓 ----------

def merged_worktree_path(path):
    """worktree 里的路径在 worktree 已删时，换成主仓里的同一相对路径；否则返回 None。

    worktree 还在时它自己就是完整的项目副本（带 docs/），照常按它判。删掉了说明已合并回主仓
    （或放弃了），这时对话记录里的路径全都不存在：往上找项目会落到主仓，却拿主仓文档去比
    worktree 里写过的文档，必然误报。认 `.worktrees/<名>/` 和 Claude Code 的 `.claude/worktrees/<名>/`。
    """
    parts = Path(path).parts
    for i, part in enumerate(parts[:-2]):
        low = part.lower()
        if low == ".worktrees":
            main = parts[:i]
        elif low == "worktrees" and i and parts[i - 1].lower() == ".claude":
            main = parts[:i - 1]
        else:
            continue
        if not main or Path(*parts[:i + 2]).exists():
            return None
        return Path(*main, *parts[i + 2:])
    return None


# ---------- git 仓库 → 本轮开始后改过的文件 ----------

def _git_names(cwd, *args):
    out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                         timeout=GIT_TIMEOUT, check=True).stdout
    return [n for n in out.decode("utf-8").split("\0") if n]


def changed_since(cwd, since):
    """cwd 所在 git 仓库里 since 之后变动的文件：未暂存和已暂存的改动（含删除），加新建的代码文件。

    补上工具记录看不到的写入（shell / Python 落盘、git add 过的、rm 掉的）。变动时刻早于本轮开始的
    旧改动不算；不是 git 仓库、git 不可用或超时就返回空，不影响工具记录那一路。
    """
    if not cwd or since is None:
        return []
    try:
        top = Path(subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True,
                                  timeout=GIT_TIMEOUT, check=True).stdout.decode("utf-8").strip())
        names = _git_names(top, "ls-files", "-z", "-m")
        names += _git_names(top, "diff", "--cached", "--name-only", "-z")
        names += [n for n in _git_names(top, "ls-files", "-z", "-o", "--exclude-standard")
                  if Path(n).suffix.lower() in SCAN_SUFFIXES]
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return []
    out = []
    for name in dict.fromkeys(names):
        at = changed_at(top / name)
        if at is not None and at >= since:
            out.append(str(top / name))
    return out


def changed_in_repos(dirs, since):
    """dirs 所在的各 git 仓库里 since 之后变动的文件；同一仓库只扫一次，最多 MAX_SCAN_REPOS 个，按 dirs 的顺序取。"""
    out = []
    for root in repos_of([d for d in dirs if d], MAX_SCAN_REPOS):
        out += changed_since(root, since)
    return list(dict.fromkeys(out))


# ---------- 文件 → 所属 vibe 项目 ----------

def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def header_marker(path):
    return _header_marker(str(path))


# 一次 Stop 里几十个路径常落在同几个目录：文件头和「是不是项目根」按路径缓存，避免反复 glob、读文件头
@lru_cache(maxsize=None)
def _header_marker(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = "".join(f.readline() for _ in range(HEADER_LINES))
    except OSError:
        return None
    m = SCRIPT_MARK.search(head)
    return m.group(1) if m else None


def _dir_is_project_root(d):
    return _is_project_root(str(d))


@lru_cache(maxsize=None)
def _is_project_root(d):
    d = Path(d)
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


def _docs_in(d):
    return d / "docs" / "BLUEPRINT.md", d / "docs" / "CHANGELOG.md"


def find_project(file_path, stop_at=None):
    """返回 (项目根, BLUEPRINT 路径, CHANGELOG 路径, 布局)；不是 vibe 项目返回 None。

    布局：project = 项目根 docs/；sibling = 脚本旁挂文件；unknown = 标准级脚本还没文档、
    也看不出归属——不猜，让提醒把两个位置都列出来。
    """
    p = Path(file_path)
    marker = header_marker(p)
    if marker == "standard":
        # 已有布局优先：旁挂文档在就沿用；目录有 AGENTS.md 或 docs/ 文档就是独占目录
        sib_bp, sib_cl = p.with_name(p.stem + ".BLUEPRINT.md"), p.with_name(p.stem + ".CHANGELOG.md")
        if sib_bp.exists() or sib_cl.exists():
            return p.parent, sib_bp, sib_cl, "sibling"
        doc_bp, doc_cl = _docs_in(p.parent)
        if doc_bp.exists() or doc_cl.exists() or (p.parent / "AGENTS.md").is_file():
            return p.parent, doc_bp, doc_cl, "project"
    home = _norm(stop_at or Path.home())
    d = p.parent
    while True:
        if d.is_dir() and _dir_is_project_root(d):
            return (d, *_docs_in(d), "project")
        if (d / ".git").exists() or _norm(d) == home or d.parent == d:
            break
        d = d.parent
    if marker == "standard":
        return p.parent, p.with_name(p.stem + ".BLUEPRINT.md"), p.with_name(p.stem + ".CHANGELOG.md"), "unknown"
    return None


# ---------- 判定 ----------

def _mtime(p):
    try:
        return Path(p).stat().st_mtime
    except OSError:
        return None


def evaluate(paths, stop_at=None, moves=None):
    """文档要晚于这批代码的最后一次变动才算跟上。

    只看磁盘 mtime、不看是谁写的，所以子 agent（fork）写的文档同样算数。删掉的代码按 changed_at
    取所在目录的 mtime；连目录都不在了就按现在，即这批改动必须重判一次。
    已删 worktree 里的代码换成主仓同一路径，按合并写回的 mtime 判，放宽 MERGE_SLACK：worktree 里改过的
    文档随同一次合并写回，时刻与代码只差几秒；没改的文档还是旧 mtime，照样拦。仓库里的 `.worktrees/` 按
    路径认（merged_worktree_path），放在仓库外的按 moves（locate.worktree_moves 从对话里解析）认。
    stale 的项目若有与当前代码快照一致的回执（receipt.covers）就不报；缺文档一律照报。
    """
    projects = {}
    for raw in dict.fromkeys(paths):
        if Path(raw).suffix.lower() in DOC_SUFFIXES:
            continue
        merged = merged_worktree_path(raw)
        if merged is None and (m := moved(raw, moves)):
            merged = Path(m)
        path, slack = (merged, MERGE_SLACK) if merged is not None else (raw, 0)
        found = find_project(path, stop_at)
        if not found:
            continue
        root, bp, cl, layout = found
        key = (_norm(bp), _norm(cl))
        projects.setdefault(key, {"root": root, "bp": bp, "cl": cl, "layout": layout, "code": []})
        projects[key]["code"].append((path, slack))

    now = time.time()
    issues = []
    for proj in projects.values():
        bp, cl = proj["bp"], proj["cl"]
        missing = [x.name for x in (bp, cl) if not x.exists()]
        if missing:
            issues.append(("missing", proj, missing))
            continue
        code_at = max((at if (at := changed_at(c)) is not None else now) - slack for c, slack in proj["code"])
        docs_at = max(_mtime(bp) or 0, _mtime(cl) or 0)
        if docs_at < code_at and not receipt.covers(bp, cl, [c for c, _ in proj["code"]],
                                                    DOC_SUFFIXES, SCAN_SUFFIXES):
            issues.append(("stale", proj, []))
    return issues


def receipt_command(bp):
    return (f'"{sys.executable}" "{Path(__file__).resolve()}" receipt --blueprint "{bp}" '
            '--reason "<一句话：为什么这批不用记>"')


def render_reason(issues):
    lines = ["[vibe-flow 文档闸] 本轮改了下面这些 vibe 项目的代码，文档还没跟上："]
    for kind, proj, missing in issues:
        where = proj["root"]
        if kind == "missing" and proj["layout"] == "unknown":
            script = Path(proj["code"][0][0])
            lines.append(f"- {script}：还没有 BLUEPRINT / CHANGELOG，位置看不出来，按这个脚本的实际归属选（vibe-flow §6）："
                         f"独占这个目录 → 建 {where / 'AGENTS.md'} 和 {where / 'docs'} 下的两份；"
                         f"和别的脚本共处 → 建旁挂 {script.stem}.BLUEPRINT.md / {script.stem}.CHANGELOG.md。"
                         "出生时两份一起建，CHANGELOG 第一条记为什么要做它。")
        elif kind == "missing":
            lines.append(f"- {where}：缺 {' / '.join(missing)}（应在 {proj['bp'].parent}）。"
                         "出生时两份一起建，CHANGELOG 第一条记为什么要做它。")
        else:
            lines.append(f"- {where}：BLUEPRINT 和 CHANGELOG 都还停在这批代码改动之前。"
                         f"判断不用记时跑：{receipt_command(proj['bp'])}")
    lines += [
        "按 vibe-flow §8 收工：派一个继承本会话上下文的子 agent 维护文档（Claude Code 用 Agent 工具、"
        "subagent_type 为 fork；Codex 用 spawn_agent 并继承全部历史），任务写：加载 living-blueprint，"
        "按它更新本项目文档、覆盖这批改动，只改文档不碰代码，汇报不超过三行。等它完成再汇报或提交。"
        "没有这类子 agent 可用时，自己按 living-blueprint 改。",
        "纯内部重构、用户没感知过 → 不用派，跑上面那条回执命令写明理由，并在回复里说一句。回执确认的是"
        "「这对文档管的全部代码在当前状态下都不用更新文档」，不只是本轮那几个文件；之后代码或这两份文档"
        "再变，回执自动失效。文档还没建的不能用回执，要先建。",
        "本提醒每轮只出现一次；判断权在你，别为过闸写假条目，也别为过闸写假回执。",
    ]
    return "\n".join(lines)


def subagent_running(tasks):
    """后台还有子 agent 在跑（多半就是维护文档的 fork）。它总会结束、结束时主 agent 被唤醒重判，
    所以暂缓是安全的；shell 类后台任务可能永不结束，不能让它们暂缓闸。"""
    return any(isinstance(t, dict) and (t.get("task_type") or t.get("type")) == "subagent"
               for t in tasks or [])


def receipt_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="doc_gate.py receipt",
                                 description="写一条「这批不用记」回执（见 receipt.py）")
    ap.add_argument("--blueprint", required=True, help="闸提示里给出的 BLUEPRINT 路径")
    ap.add_argument("--reason", required=True, help="一句话：为什么这批不用记")
    args = ap.parse_args(argv)
    try:
        record = receipt.write(args.blueprint, args.reason, DOC_SUFFIXES, SCAN_SUFFIXES)
    except (ValueError, receipt.Unverifiable) as e:
        sys.stderr.write(f"回执没写：{e}\n")
        return 2
    sys.stdout.write(f"回执已写：{record['root']}（{record['layout']}，快照 {record['files']} 个文件）\n")
    return 0


def main():
    data = json.loads(sys.stdin.read() or "{}")
    if data.get("stop_hook_active"):
        return 0
    transcript = data.get("transcript_path")
    if not transcript or not os.path.isfile(transcript):
        return 0
    rows = read_rows(transcript)
    moves = worktree_moves(rows, data.get("cwd"))
    turn = touched(rows, last_prompt_index(rows), moves=moves, cwd=data.get("cwd"))
    dirs = [data.get("cwd")] + [p for kind, p in turn if kind != "read"]
    paths = turn_written_paths(rows) + changed_in_repos(dirs, turn_start(rows))
    if not paths:
        return 0
    stop_at = os.environ.get("VIBE_FLOW_DOC_GATE_HOME")
    issues = evaluate(paths, stop_at, moves)
    if issues and not subagent_running(data.get("background_tasks")):
        sys.stdout.write(json.dumps({"decision": "block", "reason": render_reason(issues)},
                                    ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        if sys.argv[1:2] == ["receipt"]:
            sys.exit(receipt_main(sys.argv[2:]))
        sys.exit(main())
    except Exception as e:
        sys.stderr.write(f"vibe-flow doc_gate 内部错误（已放行）：{e!r}\n")
        sys.exit(1)
