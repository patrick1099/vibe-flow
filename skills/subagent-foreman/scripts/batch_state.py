"""Persist one supervisor batch inside HANDOFF; this is not an agent scheduler.

Structure: validation -> HANDOFF parsing -> guarded atomic save -> CLI.
Usage: python batch_state.py --ai-help
Original need: keep execution detail out of the main conversation and recover batches.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

START = "<!-- vibe-flow:batch:start -->"
END = "<!-- vibe-flow:batch:end -->"
TASK_STATES = {"pending", "running", "implemented", "verified", "blocked"}
WORKER_STATES = {"running", "done", "stopped"}


class StateError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise StateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise StateError(f"invalid JSON constant: {value}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def text_field(value, label):
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{label} must be a nonempty string")


def evidence_file(workspace, value):
    text_field(value, "evidence")
    relative = Path(value)
    target = (workspace / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(workspace) or not target.is_file():
        raise StateError(f"evidence must be an existing file inside workspace: {value}")


def validate(record, workspace, batch):
    if not isinstance(record, dict) or type(record.get("schema")) is not int or record["schema"] != 1:
        raise StateError("expected schema 1 object")
    for key in ("workspace", "batch", "supervisor", "baseline"):
        text_field(record.get(key), key)
    if not Path(record["workspace"]).is_absolute() or Path(record["workspace"]).resolve() != workspace:
        raise StateError("workspace mismatch")
    if record["batch"] != batch:
        raise StateError("batch mismatch")
    if record.get("outcome") not in {"active", "complete", "blocked"}:
        raise StateError("invalid outcome")
    if record.get("docs") not in {"pending", "done", "not-needed"}:
        raise StateError("invalid docs state")
    for group, states in (("tasks", TASK_STATES), ("workers", WORKER_STATES)):
        items = record.get(group)
        if not isinstance(items, list) or (group == "tasks" and not items):
            raise StateError(f"invalid {group}")
        ids = set()
        for item in items:
            if not isinstance(item, dict):
                raise StateError(f"invalid {group} item")
            text_field(item.get("id"), "id")
            if item["id"] in ids:
                raise StateError(f"duplicate {group} id")
            ids.add(item["id"])
            if item.get("state") not in states:
                raise StateError(f"invalid {group} state")
            if group == "tasks":
                text_field(item.get("acceptance"), "acceptance")
                evidence = item.get("evidence")
                if not isinstance(evidence, list):
                    raise StateError("evidence must be a list")
                if item["state"] == "verified" and not evidence:
                    raise StateError("verified task needs evidence")
                for value in evidence:
                    evidence_file(workspace, value)
        if sum(item["state"] == "running" for item in items) > 1:
            raise StateError(f"serial batch allows at most one running {group} item")
    if not isinstance(record.get("next"), list):
        raise StateError("next must be a list")
    for item in record["next"]:
        text_field(item, "next")
    if record["outcome"] != "active" and running(record):
        raise StateError("cannot close a batch with recorded running work")
    if record["outcome"] == "complete":
        if any(t["state"] != "verified" for t in record["tasks"]) or record["docs"] == "pending":
            raise StateError("complete requires verified tasks and finished documentation")
    return record


def running(record):
    return any(item["state"] == "running" for group in ("tasks", "workers") for item in record[group])


def ready(record):
    if running(record) or record["outcome"] == "active" or record["docs"] == "pending":
        raise StateError("handoff not ready: settle work and documentation first")


def read_handoff(path):
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if START not in text and END not in text:
        return text, None, "missing"
    if text.count(START) != 1 or text.count(END) != 1 or text.index(END) < text.index(START):
        raise StateError("malformed batch markers; do not silently overwrite")
    body = text.split(START, 1)[1].split(END, 1)[0].strip()
    if not body.startswith("```json\n") or not body.endswith("\n```"):
        raise StateError("batch must contain one JSON fence")
    record = parse_json(body[len("```json\n"):-len("\n```")])
    return text, record, hashlib.sha256(text.encode("utf-8")).hexdigest()


def summary(record, revision):
    return {
        "batch": record["batch"][:120], "supervisor": record["supervisor"][:120],
        "outcome": record["outcome"], "docs": record["docs"],
        "tasks": dict(Counter(t["state"] for t in record["tasks"])),
        "running_workers": sum(w["state"] == "running" for w in record["workers"]),
        "next": [s[:240] for s in record["next"][:2]],
        "evidence": [s[:240] for t in record["tasks"] for s in t["evidence"]][:3],
        "revision": revision, "host_lifecycle_checked": False,
    }


def save(path, record, workspace, batch, expected, dry_run=False, initialize=False):
    validate(record, workspace, batch)
    # Both preview and execution take the same lock and inspect the latest disk state.
    lock = path.with_name(path.name + ".batch.lock")
    with lock.open("x", encoding="utf-8") as guard:
        try:
            original, previous, revision = read_handoff(path)
            if previous is None and not initialize:
                raise StateError("batch record missing; resume must not reinitialize lost state")
            if previous is not None and initialize:
                raise StateError("--init only allowed before the first batch")
            if expected != revision:
                raise StateError("revision conflict; reread status before saving")
            if previous is not None:
                validate(previous, workspace, previous.get("batch") if isinstance(previous, dict) else None)
                if previous["batch"] != batch:
                    ready(previous)
                elif previous["supervisor"] != record["supervisor"] and running(previous):
                    raise StateError("settle recorded workers before changing supervisor")
            block = START + "\n```json\n" + json.dumps(record, ensure_ascii=False, indent=2) + "\n```\n" + END
            if previous is None:
                updated = original.rstrip() + "\n\n# 批次状态\n\n" + block + "\n"
            else:
                before, tail = original.split(START, 1)
                if "# 批次状态" not in before:
                    before = before.rstrip() + "\n\n# 批次状态\n\n"
                updated = before + block + tail.split(END, 1)[1]
            if not dry_run:
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(updated)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if temporary.read_text(encoding="utf-8") != updated:
                        raise OSError("temporary handoff failed readback")
                    os.replace(temporary, path)
                    if path.read_text(encoding="utf-8") != updated:
                        raise OSError("saved handoff failed readback")
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
            return {"dry_run": dry_run, "revision": revision if dry_run else hashlib.sha256(updated.encode("utf-8")).hexdigest()}
        finally:
            guard.close()
            lock.unlink(missing_ok=True)


AI_HELP = """---
name: batch-state
description: Persist and check one supervisor batch in an existing HANDOFF.
ai_help_version: 1
---
## Quick Reference
Use subprocess.run([python, script, ...]) with list argv, never a shell-built string.
- status --handoff FILE --workspace DIR --batch ID --json
- save --handoff FILE --workspace DIR --batch ID --input-file JSON --expect REV --json
- check --handoff FILE --workspace DIR --batch ID --ready --json
## When to Use
Keep the main conversation on short outcomes; recover execution from disk.
## Command Reference
All commands require --handoff, --workspace, --batch. save additionally requires
--input-file (UTF-8, or - for stdin), --expect (status revision).
Only the first batch uses --init --expect missing. A missing record during recovery
is damage, never an invitation to initialize. To switch b1 to b2, read status with
--batch b1, then save the b2 record with --batch b2 --expect <b1 revision>.
--dry-run validates the identical save path without replacing HANDOFF.
--json and --format json are equivalent; output always uses a JSON envelope.
## Side Effects & Safety
status/check are read-only and offline. save atomically replaces only the machine
section, preserving other text. Its parent directory must already exist. Save takes
an exclusive sibling lock, including dry-run; a stale lock requires checking the
previous process before removal. Never clears a lock held by another save.
No command spawns, terminates, authenticates, or revokes an agent. check --ready
checks recorded state only; separately confirm actual host processes are stopped.
## Exit Codes
0 success; 1 state/IO/verification failure; 2 invalid command arguments/input JSON.
## Errors & Recovery
E_VERIFICATION_FAILED: fix records/evidence or settle work; do not pretend complete.
E_IO/E_PERMISSION: preserve the old handoff, fix storage. Revision conflict: reread.
E_NOT_FOUND: check the paths. E_VALIDATION: use --help and correct input.
"""


def emit(ok, data=None, code=None, message=None):
    error = None if ok else {"code": code, "message": message, "details": {}, "retryable": False,
                              "suggestion": "Run --ai-help; reconcile records and host state before retrying."}
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {}}, ensure_ascii=False),
          file=sys.stdout if ok else sys.stderr)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    options = argv[:argv.index("--")] if "--" in argv else argv
    if "--ai-help" in options:
        print(AI_HELP)
        return 0
    parser = Parser(description="Supervisor HANDOFF records. LLMs/agents: run 'batch_state.py --ai-help' for usage guidance.")
    parser.add_argument("command", choices=("status", "check", "save"))
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--input-file")
    parser.add_argument("--expect")
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=("json",))
    try:
        args = parser.parse_args(argv)
        workspace = args.workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("workspace must be a directory")
        if (args.ready and args.command != "check") or (args.dry_run and args.command != "save"):
            raise ValueError("--ready only for check; --dry-run only for save")
        if args.command != "save" and (args.input_file is not None or args.expect is not None or args.init):
            raise ValueError("--input-file/--expect only for save")
        if args.command == "save":
            if args.input_file is None or args.expect is None:
                raise ValueError("save needs --input-file and --expect")
            if args.input_file == "-":
                if sys.stdin.isatty():
                    raise ValueError("pipe JSON through stdin or pass --input-file FILE")
                body = sys.stdin.read()
            else:
                body = Path(args.input_file).read_text(encoding="utf-8")
            record = parse_json(body)
            data = save(args.handoff, record, workspace, args.batch, args.expect, args.dry_run, args.init)
        else:
            _, record, revision = read_handoff(args.handoff)
            if record is None:
                raise StateError("batch record missing")
            validate(record, workspace, args.batch)
            if args.ready:
                ready(record)
            data = summary(record, revision)
        emit(True, data)
        return 0
    except (ValueError, UnicodeError) as exc:
        emit(False, code="E_VALIDATION", message=str(exc))
        return 2
    except StateError as exc:
        emit(False, code="E_VERIFICATION_FAILED", message=str(exc))
    except FileNotFoundError as exc:
        emit(False, code="E_NOT_FOUND", message=str(exc))
    except PermissionError as exc:
        emit(False, code="E_PERMISSION", message=str(exc))
    except OSError as exc:
        emit(False, code="E_IO", message=str(exc))
    except Exception as exc:
        emit(False, code="E_INTERNAL", message=str(exc))
    return 1


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        output.reconfigure(encoding="utf-8")
    raise SystemExit(main())
