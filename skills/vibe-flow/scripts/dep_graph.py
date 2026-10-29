"""模块依赖图：列出项目内部模块之间的依赖边和环，可与某个提交对比。

vibe-flow §8：好档里新增、拆分、合并模块或跨模块重构时，交付前跑 --against <开工时的提交>，
新出现的环要消掉或在报告里说明理由。
支持：
- 单 crate 的 Rust 项目：src/ 下的顶层模块；认 use、类型位置和函数体内的 crate:: 全路径调用、
  super::、bin 里的 <crate名>::，#[path] 引入的文件归声明它的模块；#[cfg(test)] 模块不算。
- Python 项目：ast 解析 import（含函数内的 import），节点按 --depth 截断；tests/、test_*.py 不算。默认层数：恰好一个顶层包时 2，否则 1；顶层单文件不算包。
看不到：宏展开、动态导入（importlib、__import__）、经 re-export 转手的间接依赖。
用法：py -3 dep_graph.py [项目目录] [--against REV | --write-snapshot [PATH] | --check-snapshot [PATH]] [--depth N] [--d2 OUT.d2]
退出码：0 正常（check：一致）；1 --against 出现新环或已有环吞进新模块，或 check 不一致；2 快照缺失或损坏、用法或读取错误。
只用 stdlib。
"""
import argparse
import ast
import json
import posixpath
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {"target", ".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}


# ---------- 读文件：工作区或某个提交，都只在内存里 ----------

def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout


def worktree_files(root, suffix):
    try:
        names = _git(root, "ls-files", "-z", "-co", "--exclude-standard").decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError):
        names = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    out = {}
    for rel in names:
        if rel.endswith(suffix) and not SKIP_DIRS & set(rel.split("/")[:-1]):
            path = root / rel
            if path.is_file():
                out[rel] = path.read_text(encoding="utf-8", errors="replace")
    return out


def ref_files(root, rev, suffix):
    prefix = _git(root, "rev-parse", "--show-prefix").decode("utf-8").strip()
    names = _git(root, "ls-tree", "-r", "-z", "--name-only", "--full-name", rev, "--", ".").decode("utf-8").split("\0")
    out = {}
    for full in names:
        rel = full[len(prefix):] if full.startswith(prefix) else full
        if rel.endswith(suffix) and not SKIP_DIRS & set(rel.split("/")[:-1]):
            out[rel] = _git(root, "show", f"{rev}:{full}").decode("utf-8", errors="replace")
    return out


# ---------- Rust ----------

def _rust_clean(src):
    """去掉注释、字符串和字符字面量，保留其余文本（含换行）。"""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        elif m := re.match(r'b?r(#*)"', src[i:i + 300]):
            end = src.find('"' + m.group(1), i + m.end())
            i = n if end < 0 else end + 1 + len(m.group(1))
            out.append('""')
        elif c == '"' or (c == "b" and src.startswith('b"', i) and not (i and (src[i - 1].isalnum() or src[i - 1] == "_"))):
            i += 2 if c == "b" else 1
            while i < n and src[i] != '"':
                i += 2 if src[i] == "\\" else 1
            i += 1
            out.append('""')
        elif c == "'" and (m := re.match(r"'(\\(x..|u\{[0-9a-fA-F]+\}|.)|[^\\'])'", src[i:i + 12])):
            i += m.end()
            out.append("' '")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _block_end(text, open_at):
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def _strip_cfg_test(text):
    while m := re.search(r"#\[cfg\(test\)\](?:\s*#\[[^\]]*\])*\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+\w+\s*\{", text):
        text = text[:m.start()] + text[_block_end(text, m.end() - 1) + 1:]
    return text


def _top_names(body):
    names, depth, cur = [], 0, ""
    for ch in body:
        depth += (ch == "{") - (ch == "}")
        if ch == "," and depth == 0:
            names.append(cur)
            cur = ""
        else:
            cur += ch
    names.append(cur)
    return [m.group(1) for s in names if (m := re.match(r"\s*(\w+)", s))]


def _refs_after(text, pattern):
    """pattern 匹配到路径前缀为止；返回其后的 (顶层名, 下一段) 列表，花括号组展开一层。"""
    found = []
    for m in re.finditer(pattern + r"(\{|\w+)((?:::\w+)?)", text):
        if m.group(1) == "{":
            body = text[m.start(1) + 1:_block_end(text, m.start(1))]
            found += [(name, "use{…}") for name in _top_names(body)]
        else:
            found.append((m.group(1), m.group(2).lstrip(":") or "(模块)"))
    return found


def rust_graph(files, crate):
    src = {k[4:]: _strip_cfg_test(_rust_clean(v)) for k, v in files.items() if k.startswith("src/")}

    def top(rel):
        parts = rel.split("/")
        if parts[0] == "bin":
            return "bin/" + parts[1].removesuffix(".rs")
        return parts[0].removesuffix(".rs")

    def depth(rel):
        parts = rel.split("/")
        return len(parts) - (parts[-1] == "mod.rs")

    owner, test_only = {}, set()
    for rel, text in src.items():
        here = posixpath.dirname(rel)
        # mod x; 的子文件目录：lib.rs / main.rs / mod.rs 在同目录，其他文件在同名子目录
        children = here if rel in ("lib.rs", "main.rs") or rel.endswith("/mod.rs") else rel.removesuffix(".rs")
        raw = files["src/" + rel]
        for m in re.finditer(r'#\[path\s*=\s*"([^"]+)"\]\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+\w+\s*;', raw):
            owner[posixpath.normpath(posixpath.join(here, m.group(1)))] = owner.get(rel, top(rel))
        for m in re.finditer(r"#\[cfg\(test\)\](?:\s*#\[[^\]]*\])*\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;", text):
            for cand in (f"{m.group(1)}.rs", f"{m.group(1)}/mod.rs"):
                test_only.add(posixpath.normpath(posixpath.join(children, cand)))
    roots = {"lib", "main"}
    modules = {top(r) for r in src if r not in owner and r not in test_only and top(r) not in roots and not top(r).startswith("bin/")}
    nodes = set(modules)
    edges = defaultdict(set)
    for rel, text in src.items():
        if rel in test_only:
            continue
        me = owner.get(rel, top(rel))
        nodes.add(me)
        refs = _refs_after(text, r"\bcrate::") + _refs_after(text, rf"\b{crate}::")
        if rel not in owner:
            refs += _refs_after(text, r"(?<!::)\b" + "super::" * depth(rel))
        for name, item in refs:
            if name in modules and name != me:
                edges[(me, name)].add(item)
    return nodes, edges


# ---------- Python ----------

def _is_test(rel):
    parts = rel.split("/")
    name = parts[-1]
    return "tests" in parts[:-1] or "test" in parts[:-1] or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def python_graph(files, depth):
    mods = {}
    for rel, text in files.items():
        if _is_test(rel):
            continue
        parts = rel.removeprefix("src/")[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts and all(p.isidentifier() for p in parts):
            mods[".".join(parts)] = (rel, text)
    if depth is None:
        tops = {m.split(".")[0] for m in mods if "." in m}
        depth = 2 if len(tops) == 1 else 1

    def internal(name):
        while name:
            if name in mods:
                return name
            name = name.rpartition(".")[0]
        return None

    def node(name):
        return ".".join(name.split(".")[:depth])

    nodes = {node(m) for m in mods}
    edges = defaultdict(set)
    for me, (rel, text) in mods.items():
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            raise ValueError(f"{rel} 解析失败：{e}") from e
        package = me if rel.endswith("__init__.py") else me.rpartition(".")[0]
        for n in ast.walk(tree):
            targets = []
            if isinstance(n, ast.Import):
                targets = [(a.name, a.name) for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                if n.level:
                    base = package.split(".") if package else []
                    base = base[:len(base) - (n.level - 1)] if n.level > 1 else base
                    module = ".".join(base + ([n.module] if n.module else []))
                else:
                    module = n.module or ""
                for a in n.names:
                    full = f"{module}.{a.name}" if module else a.name
                    targets.append((full if full in mods else module, a.name))
            for name, item in targets:
                hit = internal(name)
                if hit and node(hit) != node(me):
                    edges[(node(me), node(hit))].add(item)
    return nodes, edges


# ---------- 图 ----------

def cycles(nodes, edges):
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
    index, low, stack, on, found, counter = {}, {}, [], set(), [], [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in sorted(adj[v]):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                found.append(sorted(comp))

    sys.setrecursionlimit(max(1000, 4 * len(nodes) + 100))
    for v in sorted(nodes):
        if v not in index:
            strong(v)
    return sorted(found)


def analyze(root, rev, depth):
    cargo = None
    if rev:
        try:
            cargo = _git(root, "show", f"{rev}:./Cargo.toml").decode("utf-8")
        except subprocess.CalledProcessError:
            cargo = None
    elif (root / "Cargo.toml").is_file():
        cargo = (root / "Cargo.toml").read_text(encoding="utf-8")
    if cargo is not None:
        m = re.search(r'^\s*\[package\][^\[]*?^\s*name\s*=\s*"([^"]+)"', cargo, re.M | re.S)
        if not m:
            raise ValueError("Cargo.toml 没有 [package]；workspace 请对单个成员 crate 运行")
        files = ref_files(root, rev, ".rs") if rev else worktree_files(root, ".rs")
        return "rust", *rust_graph(files, m.group(1).replace("-", "_"))
    files = ref_files(root, rev, ".py") if rev else worktree_files(root, ".py")
    if not files:
        raise ValueError("没有找到 Cargo.toml 或 .py 文件")
    return "python", *python_graph(files, depth)


def write_d2(path, nodes, edges, sccs, added):
    in_cycle = {(a, b) for c in sccs for a in c for b in c if (a, b) in edges}
    lines = ["direction: down", ""] + [f'"{n}"' for n in sorted(nodes)] + [""]
    for a, b in sorted(edges):
        style = []
        if (a, b) in in_cycle:
            style += ['stroke: "#dc2626"', "stroke-width: 3"]
        elif (a, b) in added:
            style += ['stroke: "#2563eb"', "stroke-width: 2"]
        lines.append(f'"{a}" -> "{b}"' + (": {style: {" + "; ".join(style) + "}}" if style else ""))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def snapshot_data(lang, nodes, edges, depth):
    return {
        "version": 1,
        "language": lang,
        "depth": depth,
        "nodes": sorted(nodes),
        "edges": [list(edge) for edge in sorted(edges)],
    }


def read_snapshot(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ValueError(f"快照不存在 {path}，请先用 --write-snapshot 写入") from e
    fields = {"version", "language", "depth", "nodes", "edges"}
    if not isinstance(data, dict) or not fields <= data.keys():
        raise ValueError(f"快照缺字段 {path}")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError(f"快照版本不是 1：{path}")
    if (not isinstance(data["language"], str)
            or (data["depth"] is not None and type(data["depth"]) is not int)
            or not isinstance(data["nodes"], list)
            or not all(isinstance(n, str) for n in data["nodes"])
            or not isinstance(data["edges"], list)
            or not all(isinstance(e, list) and len(e) == 2
                       and all(isinstance(n, str) for n in e) for e in data["edges"])):
        raise ValueError(f"快照字段格式错误 {path}")
    return data


def write_snapshot(path, data):
    content = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        if path.read_bytes() == content:
            return False
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return True


def check_snapshot(path, old, lang, nodes, edges):
    added_nodes = set(nodes) - set(old["nodes"])
    removed_nodes = set(old["nodes"]) - set(nodes)
    old_edges = {tuple(e) for e in old["edges"]}
    added_edges = set(edges) - old_edges
    removed_edges = old_edges - set(edges)
    if lang == old["language"] and not (added_nodes or removed_nodes or added_edges or removed_edges):
        print(f"与快照一致 {path}：模块 {len(nodes)}  边 {len(edges)}")
        return 0
    print(f"与快照 {path} 不一致：模块 +{len(added_nodes)} -{len(removed_nodes)}  边 +{len(added_edges)} -{len(removed_edges)}")
    if lang != old["language"]:
        print(f"  语言 {old['language']} → {lang}")
    for sign, group in (("+", added_nodes), ("-", removed_nodes)):
        for node in sorted(group):
            print(f"  {sign} 模块 {node}")
    for sign, group in (("+", added_edges), ("-", removed_edges)):
        for a, b in sorted(group):
            print(f"  {sign} 边 {a} -> {b}")
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(description="模块依赖图与环；--against 对比某个提交")
    p.add_argument("root", nargs="?", default=".")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--against", metavar="REV", help="与这个提交的依赖图对比")
    mode.add_argument("--write-snapshot", nargs="?", const="", metavar="PATH", help="写模块依赖快照（默认：docs/model/build.deps.json）")
    mode.add_argument("--check-snapshot", nargs="?", const="", metavar="PATH", help="比对模块依赖快照（默认：docs/model/build.deps.json）")
    p.add_argument("--depth", type=int, help="Python 节点按包路径截断的层数（默认层数：恰好一个顶层包时 2，否则 1；顶层单文件不算包）")
    p.add_argument("--d2", metavar="OUT", help="另写一份 D2 图：环里的边红色，相对 --against 新增的边蓝色")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    snapshot_arg = args.check_snapshot if args.check_snapshot is not None else args.write_snapshot
    snapshot_path = Path(snapshot_arg).resolve() if snapshot_arg else root / "docs/model/build.deps.json"
    try:
        snapshot = read_snapshot(snapshot_path) if args.check_snapshot is not None else None
        depth = snapshot["depth"] if snapshot is not None and args.depth is None else args.depth
        lang, nodes, edges = analyze(root, None, depth)
        old = analyze(root, args.against, args.depth) if args.against else None
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        detail = e.stderr.decode("utf-8", "replace").strip() if isinstance(e, subprocess.CalledProcessError) and e.stderr else e
        sys.stderr.write(f"dep_graph: {detail}\n")
        return 2
    sccs = cycles(nodes, edges)
    if snapshot is not None:
        if args.d2:
            write_d2(args.d2, nodes, edges, sccs, set(edges) - {tuple(e) for e in snapshot["edges"]})
        return check_snapshot(snapshot_path, snapshot, lang, nodes, edges)
    print(f"语言 {lang}  模块 {len(nodes)}  边 {len(edges)}  环 {len(sccs)}")
    for c in sccs:
        inner = ", ".join(f"{a}→{b}" for a in c for b in c if (a, b) in edges)
        print(f"  环 {{{', '.join(c)}}}: {inner}")
    for a, b in sorted(edges):
        print(f"  {a} -> {b}: {', '.join(sorted(edges[(a, b)]))[:120]}")
    status, added = 0, set()
    if old:
        _, old_nodes, old_edges = old
        old_sccs = cycles(old_nodes, old_edges)
        added = set(edges) - set(old_edges)
        removed = set(old_edges) - set(edges)
        new_sccs = [c for c in sccs if not any(set(c) <= set(o) for o in old_sccs)]
        gone_sccs = [o for o in old_sccs if not any(set(o) <= set(c) for c in sccs)]
        print(f"\n对比 {args.against}：模块 {len(old_nodes)}→{len(nodes)}  边 {len(old_edges)}→{len(edges)}（+{len(added)} -{len(removed)}）  环 {len(old_sccs)}→{len(sccs)}")
        for a, b in sorted(added):
            print(f"  + {a} -> {b}: {', '.join(sorted(edges[(a, b)]))[:100]}")
        for a, b in sorted(removed):
            print(f"  - {a} -> {b}")
        for c in new_sccs:
            print(f"  新环 {{{', '.join(c)}}}")
        for c in gone_sccs:
            print(f"  消失的环 {{{', '.join(c)}}}")
        status = 1 if new_sccs else 0
    if args.d2:
        write_d2(args.d2, nodes, edges, sccs, added)
    if args.write_snapshot is not None:
        try:
            changed = write_snapshot(snapshot_path, snapshot_data(lang, nodes, edges, args.depth))
        except OSError as e:
            sys.stderr.write(f"dep_graph: {e}\n")
            return 2
        print(f"{'已写快照' if changed else '快照未变'} {snapshot_path}")
    return status


if __name__ == "__main__":
    sys.exit(main())
