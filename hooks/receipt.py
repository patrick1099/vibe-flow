"""文档闸的「这批不用记」回执。

被闸拦下、AI 判断这批改动不用记文档时，跑闸提示里给出的命令写一条回执；之后同一状态再被判 stale
（典型是后台任务完成把 AI 唤醒，本轮范围不变、又结束一次）就不再提醒。回执是 AI 显式写的结构化记录，
闸不去解析回复措辞。

一条回执管一对文档（BLUEPRINT + CHANGELOG），不是一个目录：同目录几个旁挂脚本各有各的。它确认的是
「这对文档管的全部代码，在当前状态下都不需要更新这对文档」，不只是本轮那几个文件——所以指纹按整份
代码快照算，与调用方传进来哪些路径无关（session-sweep 只传每目录最新的一个文件，也能认出同一条回执）。
指纹同时绑定这对文档的内容：代码改回旧状态而文档已经描述了新状态时，旧回执不会重新生效。

快照：project 布局 = 项目根下 git 跟踪的非文档文件 ＋ 未跟踪且未被忽略的代码文件（不在 git 里就遍历目录）；
sibling 布局 = 同名脚本本身。删掉的文件不在快照里，删除因此也会改变指纹。待判定的代码不在快照里
（比如被 gitignore 的文件）、文件太多、读不了、git 超时，都算「回执无法验证」，照常提醒，绝不按部分快照放行。

存放：每对文档一个 JSON 文件，放在 ~/.vibe-flow/doc-receipts/（环境变量 VIBE_FLOW_RECEIPTS 可改），
写入走临时文件 + os.replace，两个 worktree 同时写也不会互相覆盖。Claude、Codex 两个闸和 session-sweep
都经 doc_gate.evaluate 读同一处。
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

GIT_TIMEOUT = 8
MAX_FILES = 3000
# 遍历非 git 项目时跳过的目录：虚拟环境、依赖、缓存、worktree
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
             ".worktrees", ".claude", ".vibe-flow"}


class Unverifiable(Exception):
    """快照拿不全，回执无法验证。"""


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def store_dir():
    return Path(os.environ.get("VIBE_FLOW_RECEIPTS") or Path.home() / ".vibe-flow" / "doc-receipts")


def _store_file(bp, cl):
    key = f"{_norm(bp)}|{_norm(cl)}"
    return store_dir() / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:24] + ".json")


def layout_of(bp):
    """由 BLUEPRINT 路径反推 (根, CHANGELOG, 布局)：docs/BLUEPRINT.md → project；<脚本名>.BLUEPRINT.md → sibling。"""
    bp = Path(bp)
    if bp.name == "BLUEPRINT.md" and bp.parent.name == "docs":
        return bp.parent.parent, bp.parent / "CHANGELOG.md", "project"
    if bp.name.endswith(".BLUEPRINT.md"):
        stem = bp.name[: -len(".BLUEPRINT.md")]
        return bp.parent, bp.with_name(stem + ".CHANGELOG.md"), "sibling"
    raise ValueError(f"看不出这是哪种布局的 BLUEPRINT：{bp}")


def _git_list(root, *args):
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                         timeout=GIT_TIMEOUT, check=True).stdout
    return [n for n in out.decode("utf-8").split("\0") if n]


def _git_files(root, doc_suffixes, scan_suffixes):
    """git 仓库里 root 子树的代码文件；root 不在 git 仓库里返回 None。"""
    try:
        subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True,
                       timeout=GIT_TIMEOUT, check=True)
    except subprocess.CalledProcessError:
        return None
    except (OSError, subprocess.SubprocessError) as e:
        raise Unverifiable(f"git 不可用：{e!r}")
    try:
        tracked = _git_list(root, "ls-files", "-z", "--cached", "--", ".")
        untracked = [n for n in _git_list(root, "ls-files", "-z", "-o", "--exclude-standard", "--", ".")
                     if Path(n).suffix.lower() in scan_suffixes]
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as e:
        raise Unverifiable(f"git 列文件失败：{e!r}")
    names = [n for n in dict.fromkeys(tracked + untracked) if Path(n).suffix.lower() not in doc_suffixes]
    return [root / n for n in names if (root / n).is_file()]


def _walk_files(root, doc_suffixes):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() not in doc_suffixes:
                out.append(Path(dirpath) / name)
                if len(out) > MAX_FILES:
                    raise Unverifiable(f"{root} 下文件超过 {MAX_FILES} 个")
    return out


def code_files(bp, doc_suffixes, scan_suffixes):
    root, _, layout = layout_of(bp)
    if layout == "sibling":
        stem = Path(bp).name[: -len(".BLUEPRINT.md")]
        return [p for p in root.iterdir()
                if p.is_file() and p.stem == stem and p.suffix.lower() not in doc_suffixes]
    files = _git_files(root, doc_suffixes, scan_suffixes)
    if files is None:
        files = _walk_files(root, doc_suffixes)
    if len(files) > MAX_FILES:
        raise Unverifiable(f"{root} 下文件超过 {MAX_FILES} 个")
    return files


def _digest(p):
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except FileNotFoundError:
        return "<missing>"
    except OSError as e:
        raise Unverifiable(f"读不了 {p}：{e!r}")


def snapshot(bp, doc_suffixes, scan_suffixes):
    """返回 (指纹, 快照覆盖的规范化路径集合)。"""
    root, cl, _ = layout_of(bp)
    files = code_files(bp, doc_suffixes, scan_suffixes)
    h = hashlib.sha256()
    for p in sorted(files, key=lambda q: Path(q).relative_to(root).as_posix()):
        h.update(Path(p).relative_to(root).as_posix().encode("utf-8") + b"\0")
        h.update(_digest(p).encode("ascii") + b"\0")
    for doc in (bp, cl):
        h.update(b"doc\0" + _digest(doc).encode("ascii") + b"\0")
    return h.hexdigest(), {_norm(p) for p in files}


def write(bp, reason, doc_suffixes, scan_suffixes):
    """写回执：现算快照，按这对文档存一份。文档缺失时不写（缺文档不能被回执豁免）。"""
    bp = Path(bp)
    root, cl, layout = layout_of(bp)
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("回执必须写理由")
    missing = [x.name for x in (bp, cl) if not x.exists()]
    if missing:
        raise ValueError(f"缺 {' / '.join(missing)}，缺文档不能用回执豁免，先建文档")
    fp, files = snapshot(bp, doc_suffixes, scan_suffixes)
    record = {"blueprint": str(bp), "changelog": str(cl), "root": str(root), "layout": layout,
              "fingerprint": fp, "files": len(files), "reason": reason,
              "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    dest = _store_file(bp, cl)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.stem}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, dest)
    return record


def covers(bp, cl, code_paths, doc_suffixes, scan_suffixes):
    """这对文档有回执、快照与回执一致、且待判定的代码都在快照里时返回 True；其余一律 False。"""
    try:
        record = json.loads(_store_file(bp, cl).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    try:
        fp, files = snapshot(bp, doc_suffixes, scan_suffixes)
    except (Unverifiable, ValueError, OSError):
        return False
    if fp != record.get("fingerprint"):
        return False
    return all(_norm(c) in files for c in code_paths if Path(c).exists())
