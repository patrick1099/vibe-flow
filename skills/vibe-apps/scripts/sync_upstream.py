"""把 vendor/upstream.json 里登记的上游原文拉到 vendor/ 下，原样存放、一字不改。

skill 正文只指向这些文件、不复述内容，所以上游更新时跑一次本脚本即可，skill 不用改。

用法：
  py -3 sync_upstream.py            拉取全部条目，覆盖本地副本并刷新 upstream.lock.json
  py -3 sync_upstream.py --check    只比对，报告哪些与上游不同，不写文件

输出一行 JSON 信封；退出码 0 成功（有差异也是 0，差异在 data 里），1 联网/读写失败，2 参数错误。
只用 stdlib。
"""
import argparse
import datetime
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor"
MANIFEST = VENDOR / "upstream.json"
LOCK = VENDOR / "upstream.lock.json"
TIMEOUT = 30


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "vibe-flow-sync-upstream"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _commit_sha(repo, ref):
    data = json.loads(_get(f"https://api.github.com/repos/{repo}/commits/{ref}"))
    return data["sha"]


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _emit(ok, data=None, error=None):
    envelope = {"ok": ok, "data": data, "error": error, "meta": {}}
    stream = sys.stdout if ok else sys.stderr
    stream.write(json.dumps(envelope, ensure_ascii=False) + "\n")


def run(check):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    report = []
    for name, entry in manifest.items():
        repo, ref = entry["repo"], entry.get("ref", "main")
        # 先钉住 commit 再按 commit 取文件，保证同一条目的几个文件来自同一版本
        sha = _commit_sha(repo, ref)
        files = {}
        for src, dst in entry["files"].items():
            body = _get(f"https://raw.githubusercontent.com/{repo}/{sha}/{src}")
            target = VENDOR / dst
            local = target.read_bytes() if target.exists() else None
            changed = local is None or _sha256(local) != _sha256(body)
            if changed and not check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
            files[dst] = {"source": src, "sha256": _sha256(body), "changed": changed}
        report.append({"name": name, "repo": repo, "commit": sha,
                       "previous_commit": lock.get(name, {}).get("commit"),
                       "files": files})
        if not check:
            lock[name] = {"repo": repo, "ref": ref, "commit": sha,
                          "synced_at": datetime.date.today().isoformat(),
                          "files": {d: f["sha256"] for d, f in files.items()}}
    if not check:
        LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                        newline="\n")
    outdated = [f"{e['name']}:{d}" for e in report for d, f in e["files"].items() if f["changed"]]
    return {"mode": "check" if check else "sync", "outdated" if check else "updated": outdated,
            "entries": report}


def main():
    # Windows 控制台默认 GBK，信封里的中文会乱码，统一按 UTF-8 输出
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="拉取 vendor/ 下登记的上游原文")
    parser.add_argument("--check", action="store_true", help="只比对不写文件")
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code:
            _emit(False, error={"code": "E_VALIDATION", "message": "参数错误", "details": {},
                                "retryable": False, "suggestion": "用 --help 看用法"})
            sys.exit(2)
        raise
    try:
        _emit(True, run(args.check))
    except (urllib.error.URLError, TimeoutError) as exc:
        _emit(False, error={"code": "E_IO", "message": f"联网失败: {exc}", "details": {},
                            "retryable": True, "suggestion": "检查网络或代理后重试"})
        sys.exit(1)
    except (OSError, ValueError, KeyError) as exc:
        _emit(False, error={"code": "E_IO", "message": f"读写或解析失败: {exc}", "details": {},
                            "retryable": False, "suggestion": "检查 vendor/upstream.json 格式"})
        sys.exit(1)


if __name__ == "__main__":
    main()
