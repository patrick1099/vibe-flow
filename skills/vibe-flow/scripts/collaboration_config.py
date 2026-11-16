"""Read collaboration suggestions; never start agents or write task agreements."""

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SUGGESTIONS = PLUGIN_ROOT / "skills/vibe-flow/config/collaboration.json"


class ConfigError(ValueError):
    pass


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label}: expected nonempty string")
    return value


def mapping(value, label):
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"{label}: expected nonempty object")
    return value


def resolve_path(value, config_dir, *, plugin_root=PLUGIN_ROOT):
    value = nonempty(value, "path")
    def symbol(match):
        key = match.group(1)
        if key == "PLUGIN_ROOT":
            return str(plugin_root)
        if key == "CONFIG_DIR":
            return str(config_dir)
        if key.startswith("ENV:") and os.environ.get(key[4:]):
            return os.environ[key[4:]]
        raise ConfigError(f"unknown or unset path symbol: {key}")
    expanded = re.sub(r"\$\{([^}]+)\}", symbol, value)
    if "$" in expanded or "%" in expanded:
        raise ConfigError(f"unsupported path expression: {value}")
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def validate(raw, config_dir):
    cfg = copy.deepcopy(mapping(raw, "config"))
    if type(cfg.get("version")) is not int or cfg["version"] != 1:
        raise ConfigError("version: expected 1")
    for section in ("tools", "agents", "roles", "organizations"):
        mapping(cfg.get(section), section)
    for key, tool in cfg["tools"].items():
        mapping(tool, f"tools.{key}")
        for field in ("executable", "version", "docs"):
            nonempty(tool.get(field), f"tools.{key}.{field}")
        executable = tool["executable"]
        if any(marker in executable for marker in ("/", "\\", "$", "%", "~")):
            tool["executable"] = str(resolve_path(executable, config_dir))
        elif any(char.isspace() for char in executable):
            raise ConfigError(f"tools.{key}.executable: expected bare command or path, not shell text")
        docs = resolve_path(tool["docs"], config_dir)
        tool["docs"] = str(docs)
        tool["available"] = docs.is_file()
        tool["unavailable_reason"] = None if tool["available"] else f"missing documentation: {docs}"
    for key, agent in cfg["agents"].items():
        mapping(agent, f"agents.{key}")
        for field in ("tool", "selector", "model", "effort", "mode"):
            nonempty(agent.get(field), f"agents.{key}.{field}")
        if agent["tool"] not in cfg["tools"]:
            raise ConfigError(f"agents.{key}.tool: unknown tool")
    for key, role in cfg["roles"].items():
        mapping(role, f"roles.{key}")
        if role.get("agent") not in cfg["agents"]:
            raise ConfigError(f"roles.{key}.agent: unknown agent")
    for key, org in cfg["organizations"].items():
        mapping(org, f"organizations.{key}")
        if org.get("mode") not in ("single", "serial", "parallel"):
            raise ConfigError(f"organizations.{key}.mode: expected single, serial or parallel")
        members = org.get("roles")
        if not isinstance(members, list) or not members:
            raise ConfigError(f"organizations.{key}.roles: expected nonempty list")
        if any(not isinstance(role, str) or role not in cfg["roles"] for role in members):
            raise ConfigError(f"organizations.{key}.roles: unknown role")
        if "chair" in org and org["chair"] not in members:
            raise ConfigError(f"organizations.{key}.chair: must reference a member role")
    return cfg


def load_config(explicit=None):
    # Explicit/env selection is strict. Only absent optional user override uses the bundle.
    if explicit is not None:
        path = resolve_path(explicit, Path.cwd())
    elif "VIBE_FLOW_COLLABORATION_CONFIG" in os.environ:
        path = resolve_path(os.environ["VIBE_FLOW_COLLABORATION_CONFIG"], Path.cwd())
    else:
        override = Path.home() / ".vibe-flow/collaboration.json"
        path = override if override.exists() else SUGGESTIONS
    with path.open(encoding="utf-8-sig") as stream:
        cfg = validate(json.load(stream), path.parent)
    return path, cfg


def describe(cfg, organization):
    if organization not in cfg["organizations"]:
        raise ConfigError(f"unknown organization: {organization}")
    org = cfg["organizations"][organization]
    members = {}
    for name in org["roles"]:
        agent_id = cfg["roles"][name]["agent"]
        agent = cfg["agents"][agent_id]
        tool = cfg["tools"][agent["tool"]]
        if not tool["available"]:
            raise ConfigError(f"roles.{name}: {tool['unavailable_reason']}")
        members[name] = {"agent": agent_id, **agent, "tool_info": cfg["tools"][agent["tool"]]}
    return {"organization": organization, **org, "members": members}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="explicit config path (strict, no fallback)")
    parser.add_argument("--organization", help="describe one suggested organization")
    args = parser.parse_args(argv)
    try:
        path, cfg = load_config(args.config)
        result = describe(cfg, args.organization) if args.organization else cfg
        print(json.dumps({"source": str(path), "suggestion_only": True, "data": result}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"collaboration config: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
