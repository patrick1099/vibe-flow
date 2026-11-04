"""Local, opt-in source / document bindings shared by linked Git worktrees."""
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess

from locate import repo_root


class BindingError(ValueError):
    pass


def config_path():
    override = os.environ.get("VIBE_FLOW_DOC_BINDINGS")
    return Path(override) if override else Path.home() / ".vibe-flow" / "doc-bindings.json"


def _absolute(value, field):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise BindingError(f"{field} 需要本机绝对路径")
    p = Path(value)
    if not p.is_absolute() or ".." in p.parts:
        raise BindingError(f"{field} 需要绝对路径，不能含 ..：{value}")
    try:
        result = p.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise BindingError(f"{field} 路径无法解析：{value}") from exc
    if result == result.parent:
        raise BindingError(f"{field} 不能是文件系统根：{result}")
    return result


def _relative(value):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise BindingError("source 需要仓库内的相对子目录")
    parts = value.replace("\\", "/").split("/")
    if (PureWindowsPath(value).drive or
            any(s in ("", ".", "..") or s.casefold() == ".git" for s in parts)):
        raise BindingError(f"source 必须是仓库内的相对子目录，不能包含盘符、.、.. 或 .git：{value}")
    return Path(*parts)


def _git(*args):
    try:
        return subprocess.run(["git", *map(str, args)], capture_output=True, check=True,
                              timeout=5).stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ""


def _target(value, cwd=None):
    if not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        if cwd is None:
            return None
        p = cwd / p
    try:
        return p.resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _inside(path, root):
    return path == root or root in path.parents


class Registry:
    def __init__(self, rows):
        self._rows = tuple(rows)
        self._repo_cache = {}
        self._trees_cache = {}

    @classmethod
    def load(cls, path=None):
        file = Path(path) if path is not None else config_path()
        try:
            data = json.loads(file.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return cls(())
        except (OSError, ValueError) as exc:
            raise BindingError(f"读不了文档绑定 {file}：{exc}") from exc
        if (not isinstance(data, dict) or type(data.get("version")) is not int or
                data["version"] != 1 or not isinstance(data.get("bindings"), list)):
            raise BindingError(f"文档绑定 {file} 必须是 version=1 与 bindings 数组")
        rows = {}
        for index, item in enumerate(data["bindings"], 1):
            if not isinstance(item, dict) or set(item) != {"git_common_dir", "source", "documents"}:
                raise BindingError(f"第 {index} 条绑定需要 git_common_dir、source、documents")
            common = _absolute(item["git_common_dir"], "git_common_dir")
            source = _relative(item["source"])
            documents = _absolute(item["documents"], "documents")
            if common == documents or _inside(documents, common):
                raise BindingError("不能把 Git 元数据目录当成文档目录")
            key = (common, source)
            if key in rows and rows[key] != documents:
                raise BindingError(f"同一源码目录存在冲突绑定：{source}")
            rows[key] = documents
        return cls((common, source, docs) for (common, source), docs in rows.items())

    def _repo(self, path):
        if path is None or not self._rows:
            return None
        worktree = repo_root(path)
        if worktree is None:
            return None
        if worktree not in self._repo_cache:
            lines = _git("-C", worktree, "rev-parse", "--path-format=absolute",
                         "--show-toplevel", "--git-common-dir").splitlines()
            identity = None
            if len(lines) == 2 and _target(lines[0]) == worktree:
                common = _target(lines[1])
                if common is not None:
                    identity = worktree, common
            self._repo_cache[worktree] = identity
        return self._repo_cache[worktree]

    @staticmethod
    def _project(top, row, existing=False):
        _, sub, docs = row
        path = top / sub
        try:
            if path.resolve() != path or existing and (not path.is_dir() or repo_root(path) != top):
                return None
        except (OSError, RuntimeError, ValueError):
            return None
        return path, docs / "BLUEPRINT.md", docs / "CHANGELOG.md", "external"

    def for_code(self, path):
        """Longest component-wise source match in the actual worktree; a removed file can match."""
        if not self._rows:
            return None
        p = _target(path)
        repo = self._repo(p)
        if not repo:
            return None
        top, common = repo
        hits = [entry for row in self._rows if row[0] == common
                if (entry := self._project(top, row)) and _inside(p, entry[0])]
        return max(hits, key=lambda e: len(e[0].parts), default=None)

    def _for_doc_row(self, row, cwd_repo):
        common, _, _ = row
        if cwd_repo and cwd_repo[1] == common:
            entry = self._project(cwd_repo[0], row, existing=True)
            if entry:
                return entry
        if common not in self._trees_cache:
            raw = _git("--git-dir", common, "worktree", "list", "--porcelain", "-z")
            self._trees_cache[common] = [p for s in raw.split("\0") if s.startswith("worktree ")
                                         if (p := _target(s[9:])) is not None]
        for top in self._trees_cache[common]:
            if ((entry := self._project(top, row, existing=True))
                    and self._repo(top) == (top, common)):
                return entry
        return None

    def for_closeout(self, cwd, targets=()):
        """Explicit HANDOFF/doc directory wins; a foreign HANDOFF suppresses cwd fallback."""
        if not self._rows:
            return []
        here = _target(cwd)
        points = [p for raw in targets if (p := _target(raw, here)) is not None]
        doc_names = {"handoff.md", "blueprint.md", "changelog.md"}
        known_docs = {row[2] for row in self._rows}
        intended = {p.parent if p.name.casefold() in doc_names else p for p in points
                    if p.name.casefold() in doc_names or p in known_docs}
        if not intended and here in known_docs:
            intended = {here}
        if intended:
            if not intended.intersection(known_docs):
                return []
            repo = self._repo(here)
            return list(dict.fromkeys(entry for row in self._rows if row[2] in intended
                                      if (entry := self._for_doc_row(row, repo))))
        code = list(dict.fromkeys(m for p in points if (m := self.for_code(p))))
        if code:
            return code
        if here and (m := self.for_code(here)):
            return [m]
        repo = self._repo(here)
        if not repo or repo[0] != here:
            return []
        remaining = [m for row in self._rows if row[0] == repo[1]
                     if (m := self._project(here, row, existing=True))]
        return remaining if len(remaining) == 1 else []

    def resolve_source(self, source, bp):
        """A receipt must name an exact, existing registered source, never the enclosing repo."""
        root, blueprint = _target(source), _target(bp)
        match = self.for_code(root) if root else None
        if not match or match[0] != root or not root.is_dir() or match[1] != blueprint:
            raise BindingError(f"源码目录与蓝图没有对应的登记：{source} → {bp}")
        return match
