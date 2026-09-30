"""代码现状指纹：打印一个哈希，只随非文档文件的内容变化。

vibe-flow §8 在派 fork 维护文档前后各跑一次，哈希不变才说明 fork 没碰代码。
覆盖：相对 HEAD 的已跟踪改动（含暂存、删除）＋ 未跟踪文件的路径和内容；*.md 一律不算。
用法：py -3 code_state.py [仓库内任一目录，默认当前目录]
只用 stdlib。不是 git 仓库或 git 不可用时退出码 1。
"""
import hashlib
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
EXCLUDE = ":(exclude)*.md"


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=True).stdout


def fingerprint(cwd):
    top = Path(_git(cwd, "rev-parse", "--show-toplevel").decode("utf-8").strip())
    try:
        base = _git(top, "rev-parse", "--verify", "-q", "HEAD").decode("utf-8").strip()
    except subprocess.CalledProcessError:
        base = EMPTY_TREE  # 还没有提交的新仓库
    h = hashlib.sha256()
    h.update(_git(top, "diff", "--binary", base, "--", ".", EXCLUDE))
    # 未跟踪文件 git diff 看不到，名字和内容都要算进去：只收名字的话，fork 改了已有新文件的内容也发现不了
    untracked = _git(top, "ls-files", "-z", "-o", "--exclude-standard", "--", ".", EXCLUDE)
    for name in sorted(n for n in untracked.decode("utf-8").split("\0") if n):
        h.update(b"\0" + name.encode("utf-8") + b"\0")
        try:
            h.update((top / name).read_bytes())
        except OSError:
            h.update(b"<unreadable>")
    return h.hexdigest()


def main(argv):
    try:
        print(fingerprint(argv[1] if len(argv) > 1 else "."))
    except (OSError, subprocess.CalledProcessError) as e:
        sys.stderr.write(f"code_state: 不是 git 仓库或 git 不可用：{e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
