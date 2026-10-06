"""对话记录 → 本会话实际碰过的路径和仓库（doc_gate 与 compact_anchor 共用）。

会话的 cwd 不等于正在干活的项目：用户常在一个仓库里启动会话，再用绝对路径去改别的仓库。所以「这批改动
属于哪个项目」「压缩后该读回哪份约定」都按对话里实际出现的路径判断，cwd 只作补充。

路径按可信度分三级：
- write：有成功结果的 Write / Edit 等；成功的 `esafe-code edit|create ... --apply` 的目标文件（相对 --root
  解析，命令里其余路径不算）；
- read：Read / Grep / Glob 读过的路径；
- shell：Bash / PowerShell 命令里出现的其余绝对路径——只说明提到过。不按修改时间推断 python 落盘：
  文件不在了（worktree 已删）就查不到，碰巧被别处改过又会把只读的路径误升为写入。python 落盘的项目
  靠「本会话为它开过 worktree」（worktree_moves）作证据，由调用方使用。

个人仓库按规矩先开 worktree 再改、合并后删掉 worktree，worktree 常放在仓库外面（`../<仓>-wt-x`、
`~/worktrees/x`）。删掉以后对话里的路径全都不存在了，git 也不再记得它属于哪个主仓；唯一的线索是对话里那条
`git worktree add`。worktree_moves 从成功执行的那条命令解析出「worktree → 主仓」，moved 把已删 worktree
里的路径换成主仓里的同一相对路径；worktree 还在时它本身就是完整副本，不换。执行目录拿不准（cd 的参数认不出、
cd -）时不建映射——错映射会把别的仓库的约定套过来，比找不到更糟。

只用 stdlib。
"""
import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}
SHELL_TOOLS = {"Bash", "PowerShell"}
# Windows 盘符路径、Git Bash 的 /c/ 路径、~/ 开头的家目录路径；遇到空白、引号和 shell 元字符就截断
PATH_HEAD = r"""(?:(?<![\w/])[A-Za-z]:[\\/]|(?<![\w.~/:])/[A-Za-z]/|(?<![\w/])~[\\/])"""
PATH_IN_TEXT = re.compile(PATH_HEAD + r"""[^\s"'`<>|;&*?()\[\]{}$]*""")
# 引号里的路径可以带空格（如 "Obsidian Vault"），整段取
QUOTED_PATH = re.compile(r"""(["'])(""" + PATH_HEAD + r"""[^"'\n]*)\1""")
TRAILING = ".,:;!?，。；：）)】」"
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\n")
CD_COMMANDS = {"cd", "chdir", "pushd", "set-location", "sl"}
# cd 类命令里后面跟目标目录的选项（PowerShell）；bash cd 的 -P/-L/-e/-@ 是开关
CD_PATH_OPTS = {"-path", "-literalpath", "-lp"}
CD_SWITCHES = {"-p", "-l", "-e", "-@"}
# git worktree add 里带参数值的选项；其余以 - 开头的都是开关
WORKTREE_VALUE_OPTS = {"-b", "-B", "--reason"}
ESAFE_NAMES = {"esafe-code", "esafe_code.py", "esafe-code.cmd", "esafe-code.exe"}
ESAFE_WRITE_SUBCMDS = {"edit", "create"}
ESAFE_VALUE_OPTS = {"--expected-sha256", "--edits-file", "--root", "--content-file", "--encoding",
                    "--newline", "--start-line", "--end-line", "--glob"}


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


def is_human_prompt(row):
    if row.get("type") != "user" or row.get("isMeta"):
        return False
    origin = row.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    content = (row.get("message") or {}).get("content")
    return isinstance(content, str) and not content.lstrip().startswith("<")


def content_items(row):
    content = (row.get("message") or {}).get("content")
    return [x for x in content if isinstance(x, dict)] if isinstance(content, list) else []


def last_prompt_index(rows):
    """最后一条人类消息之后的第一行下标；没有人类消息返回 0。"""
    start = 0
    for i, row in enumerate(rows):
        if is_human_prompt(row):
            start = i + 1
    return start


def row_time(row):
    stamp = row.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def tool_results(rows):
    """{tool_use_id: (成功与否, 结果文本, 结果时刻)}。"""
    out = {}
    for row in rows:
        if row.get("type") != "user":
            continue
        for item in content_items(row):
            if item.get("type") != "tool_result":
                continue
            c = item.get("content")
            if isinstance(c, list):
                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
            out[item.get("tool_use_id")] = (not item.get("is_error"), c if isinstance(c, str) else "", row_time(row))
    return out


def normalize(raw, home=None):
    """文本里抠出的路径 → 本机绝对路径字符串；看不出是绝对路径返回 None。"""
    s = raw.rstrip(TRAILING)
    if not s:
        return None
    if s[0] == "~":
        s = str(Path(home or Path.home())) + s[1:]
    elif re.match(r"^/[A-Za-z]/", s) and os.name == "nt":
        s = s[1].upper() + ":" + s[2:]
    if not os.path.isabs(s):
        return None
    return os.path.normpath(s)


def paths_in_text(text, home=None):
    text = text or ""
    found = [m.group(2) for m in QUOTED_PATH.finditer(text)]
    rest = QUOTED_PATH.sub(" ", text)
    found += [m.group(0) for m in PATH_IN_TEXT.finditer(rest)]
    out = [p for raw in found if (p := normalize(raw, home))]
    return list(dict.fromkeys(out))


def _tokens(segment):
    try:
        toks = shlex.split(segment, posix=False)
    except ValueError:
        toks = segment.split()
    return [t.strip("\"'") for t in toks]


def _resolve(raw, base, home):
    """路径原文 → 绝对路径；相对路径按 base 解析，base 未知时返回 None。"""
    if not raw:
        return None
    p = normalize(raw, home)
    if p is None and base:
        p = os.path.normpath(os.path.join(base, raw))
    return p


def _cd_target(toks):
    """cd 类命令的目标原文；认不出（cd -、不认识的选项、没有参数）返回 None。"""
    args = toks[1:]
    i = 0
    while i < len(args):
        a, low = args[i], args[i].lower()
        if low in CD_PATH_OPTS or a == "--":
            return args[i + 1] if i + 1 < len(args) else None
        if a == "-":
            return None
        if a.startswith("-"):
            if low in CD_SWITCHES:
                i += 1
                continue
            return None
        return a
    return None


def _segments(command, cwd, home):
    """把一条 shell 命令按 && ; || 换行拆段，逐段给出 (执行目录, 词)；cd 段只更新执行目录，不产出。

    执行目录认不出时变成 None，此后的相对路径一律不解析。
    """
    base = cwd
    for seg in SEGMENT_SPLIT.split(command or ""):
        toks = _tokens(seg)
        if not toks:
            continue
        if toks[0].lower() in CD_COMMANDS:
            base = _resolve(_cd_target(toks), base, home)
            continue
        yield base, toks


def _positional(args, value_opts):
    i = 0
    while i < len(args):
        a = args[i]
        if a in value_opts:
            i += 2
            continue
        if not a.startswith("-"):
            return a
        i += 1
    return None


def _option(args, name):
    for i, a in enumerate(args[:-1]):
        if a == name:
            return args[i + 1]
    return None


def _esafe_targets(toks, base, home):
    """一段命令里 `esafe-code edit|create <目标> ... --apply` 的目标文件（相对 --root，没有 --root 按执行目录）。"""
    for i, t in enumerate(toks):
        if Path(t.replace("\\", "/")).name.lower() not in ESAFE_NAMES:
            continue
        rest = toks[i + 1:]
        if not rest or rest[0] not in ESAFE_WRITE_SUBCMDS or "--apply" not in rest:
            return []
        target = _positional(rest[1:], ESAFE_VALUE_OPTS)
        root = _resolve(_option(rest, "--root"), base, home) or base
        p = _resolve(target, root, home)
        return [p] if p else []
    return []


def worktree_moves(rows, cwd=None, home=None):
    """从对话里成功执行的 `git worktree add` 解析 {worktree 路径(normcase): 主仓根}。

    主仓 = 那条命令执行时所在目录（同一条命令里前面的 cd，或 git -C 的目录；都没有用会话 cwd）所属的仓库根；
    worktree 路径是 add 后第一个位置参数，相对路径按执行目录解析。工具结果报错、或输出里有 git 的
    `fatal:` 的不算——失败的 add 不能覆盖之前成功的映射。
    """
    results = tool_results(rows)
    moves = {}
    for row in rows:
        if row.get("type") != "assistant":
            continue
        for item in content_items(row):
            if item.get("type") != "tool_use" or item.get("name") not in SHELL_TOOLS:
                continue
            res = results.get(item.get("id"))
            if res is None or not res[0] or "fatal:" in res[1]:
                continue
            for base, toks in _segments((item.get("input") or {}).get("command"), cwd, home):
                # git 必须是这一段的命令本身；echo/printf 等的参数里出现的不算执行过
                head = toks[1:] if toks[0] == "&" else toks
                if not head or Path(head[0].replace("\\", "/")).name.lower() not in ("git", "git.exe"):
                    continue
                rest = head[1:]
                gitbase = base
                while len(rest) >= 2 and rest[0] in ("-C", "-c"):
                    if rest[0] == "-C":
                        gitbase = _resolve(rest[1], gitbase, home)
                    rest = rest[2:]
                if rest[:2] != ["worktree", "add"] or not gitbase:
                    continue
                wt_path = _resolve(_positional(rest[2:], WORKTREE_VALUE_OPTS), gitbase, home)
                main = repo_root(gitbase)
                if main is not None and wt_path:
                    moves[os.path.normcase(wt_path)] = main
    return moves


def moved(path, moves):
    """path 在已删掉的 worktree 里时，返回主仓里的同一相对路径；否则返回 None。"""
    if not moves:
        return None
    key = os.path.normcase(os.path.normpath(str(path)))
    for wt, main in moves.items():
        if key == wt or key.startswith(wt.rstrip(os.sep) + os.sep):
            if os.path.exists(wt):
                return None
            rel = os.path.normpath(str(path))[len(wt.rstrip(os.sep)):].lstrip("\\/")
            return str(Path(main, rel)) if rel else str(main)
    return None


def touched(rows, start=0, home=None, moves=None, cwd=None):
    """rows[start:] 里碰过的路径，按出现顺序返回 [(类别, 路径)]；写入只算有成功结果的调用。

    cwd 用来解析 shell 命令里的相对路径（esafe-code 的目标）；给了 moves 时，已删 worktree 里的路径换成主仓路径。
    """
    rows = rows[start:]
    results = tool_results(rows)
    out = []
    for row in rows:
        if row.get("type") != "assistant":
            continue
        for item in content_items(row):
            if item.get("type") != "tool_use":
                continue
            name, inp = item.get("name"), item.get("input") or {}
            res = results.get(item.get("id"))
            ok = res is not None and res[0]
            if name in WRITE_TOOLS:
                p = inp.get("file_path") or inp.get("notebook_path")
                if p and ok:
                    out.append(("write", os.path.normpath(p)))
            elif name in READ_TOOLS:
                p = inp.get("file_path") or inp.get("path")
                if p and os.path.isabs(p):
                    out.append(("read", os.path.normpath(p)))
            elif name in SHELL_TOOLS:
                cmd = inp.get("command") or ""
                targets = []
                if ok:
                    for base, toks in _segments(cmd, cwd, home):
                        targets += _esafe_targets(toks, base, home)
                keys = {os.path.normcase(t) for t in targets}
                out += [("write", t) for t in dict.fromkeys(targets)]
                out += [("shell", p) for p in paths_in_text(cmd, home) if os.path.normcase(p) not in keys]
    return [(kind, moved(p, moves) or p) for kind, p in out]


def repo_root(path):
    """路径所在 git 工作树的根（有 .git 目录或 .git 文件的那一层）；不在仓库里或路径整个不存在返回 None。"""
    p = Path(path)
    for d in (p, *p.parents):
        try:
            if (d / ".git").exists():
                return d
        except OSError:
            return None
    return None


def repos_of(paths, limit):
    """这些路径所在的 git 仓库根，去重保序，最多 limit 个。"""
    out = []
    seen = set()
    for p in paths:
        root = repo_root(p)
        if root is None:
            continue
        key = os.path.normcase(str(root))
        if key not in seen:
            seen.add(key)
            out.append(root)
            if len(out) >= limit:
                break
    return out

