"""Codex emitter: project merged settings into ~/.codex/.

Pass-through for all keys under codex: except two derived meta-keys:
  - permissions_profile: controls whether a permissions block is emitted
  - network: translated into [permissions.agent_db.network] entries

All other codex: keys are serialized as native TOML via the generic
codex_passthrough() serializer. Adding a new Codex config key is a
YAML-only change; no Python edit needed.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_db import files
from agent_db.source import (
    AgentSource,
    assemble_sections,
    doc_settings,
    merged_agents,
    merged_settings,
    merged_skills,
    render_restrictions,
    validate_namespaces,
)

DECISION = {
    "allow": "allow",
    "ask": "prompt",
    "deny": "forbidden",
}
GLOB_SCAN_MAX_DEPTH = 3
HEADING = re.compile(r"^(#{1,6})(?=\s)", re.MULTILINE)
MANAGED_BEGIN = "# agent-db begin"
MANAGED_END = "# agent-db end"
CODEX_PROFILE_ADVISORY = "advisory"
CODEX_PROFILE_ENFORCE = "enforce"
CODEX_DERIVED_KEYS = frozenset({"permissions_profile", "network"})
CODEX_SANDBOX_KEYS = frozenset({"sandbox_mode", "sandbox_workspace_write"})
BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
TABLE = re.compile(r"^\s*\[", re.MULTILINE)
TOP_LEVEL_ASSIGN = re.compile(r"(?m)^([A-Za-z0-9_-]+)\s*=")
DEFAULT_PERMISSIONS = re.compile(r'(?m)^default_permissions\s*=\s*"agent_db"\s*\n(?:\n)?')
ANY_DEFAULT_PERMISSIONS = re.compile(r'(?m)^default_permissions\s*=\s*".*?"\s*$')
AGENT_DB_TABLE = re.compile(r"(?ms)^\[permissions\.agent_db(?:\.[^\]]+)?\]\n.*?(?=^\[|\Z)")


def write_global(source: AgentSource, codex_home: Path) -> list[Path]:
    home = codex_home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)

    settings = merged_settings(source)
    validate_namespaces(settings)

    written: list[Path] = []
    agents_md = home / "AGENTS.md"
    if files.write_text(agents_md, render_agents_md(source, settings)):
        written.append(agents_md)

    config = home / "config.toml"
    if write_config(config, render_config(settings)):
        written.append(config)

    written.extend(write_rules(source, home / "rules"))
    written.extend(copy_assets(merged_skills(source), home / "skills"))
    written.extend(write_agents(merged_agents(source), home / "agents"))
    return written


def render_agents_md(source: AgentSource, settings: dict[str, Any]) -> str:
    blocks = [render_agents_section(section) for section in assemble_sections(source)]
    restrictions = render_restrictions(settings)
    if restrictions:
        blocks.append(restrictions)
    return "# AGENTS.md\n\n" + "\n\n".join(blocks).strip() + "\n"


def render_agents_section(section: Any) -> str:
    body = demote_headings(section.body.strip())
    if first_content_line(body).startswith("## "):
        return body
    return f"## {section.title}\n\n{body}".strip()


def demote_headings(markdown: str) -> str:
    return HEADING.sub(lambda match: "#" + match.group(1), markdown)


def first_content_line(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.strip():
            return line
    return ""


def render_config(settings: dict[str, Any]) -> str:
    codex = codex_settings(settings)
    lines = codex_passthrough(codex)
    profile = codex_permissions_profile(codex)
    check_sandbox_profile_conflict(codex, profile)

    if profile == CODEX_PROFILE_ADVISORY:
        if "network" in codex:
            raise ValueError("codex.network requires codex.permissions_profile enforce")
        return render_lines(lines)

    network = codex_network(codex)
    filesystem = codex_filesystem(settings.get("permissions", {}))
    if not filesystem and not network:
        return render_lines(lines)

    if lines:
        lines.append("")
    lines.append('default_permissions = "agent_db"')
    lines.extend(
        [
            "",
            "[permissions.agent_db.filesystem]",
            f"glob_scan_max_depth = {GLOB_SCAN_MAX_DEPTH}",
            '":minimal" = "read"',
            '":project_roots" = { "." = "write" }',
        ]
    )
    if filesystem:
        for path, value in filesystem.items():
            lines.append(f"{toml_string(codex_path(path))} = {toml_string(value)}")
    if network:
        lines.extend(["", "[permissions.agent_db.network]"])
        lines.extend(f"{key} = {value}" for key, value in network.items())
    return render_lines(lines)


def write_config(path: Path, generated: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    layered = layer_config(existing, generated)
    if existing == layered:
        return False
    if path.is_file():
        backup_config(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layered, encoding="utf-8")
    return True


def backup_config(path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.name}.agent-db-{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def layer_config(existing: str, generated: str) -> str:
    generated = generated.strip()
    if not generated:
        return remove_agent_db_config(existing)

    if MANAGED_BEGIN in existing and MANAGED_END in existing:
        before, rest = existing.split(MANAGED_BEGIN, 1)
        _, after = rest.split(MANAGED_END, 1)
        existing = clean_blank_lines(before.rstrip(), after.lstrip())
    else:
        existing = remove_legacy_agent_db_config(existing)

    if generated_uses_agent_db_permissions(generated):
        check_default_permissions_conflict(existing)
    existing = remove_generated_top_level_keys(existing, generated)

    return insert_managed_config(existing, generated)


def insert_managed_config(existing: str, generated: str) -> str:
    managed = f"{MANAGED_BEGIN}\n{generated}\n{MANAGED_END}"

    match = TABLE.search(existing)
    if match is None:
        return clean_blank_lines(existing.rstrip(), managed, "")

    before = existing[: match.start()].rstrip()
    after = existing[match.start() :].lstrip()
    return clean_blank_lines(before, managed, after)


def remove_legacy_agent_db_config(config: str) -> str:
    config = DEFAULT_PERMISSIONS.sub("", config)
    config = AGENT_DB_TABLE.sub("", config)
    return config.strip() + "\n" if config.strip() else ""


def remove_agent_db_config(config: str) -> str:
    if MANAGED_BEGIN in config and MANAGED_END in config:
        before, rest = config.split(MANAGED_BEGIN, 1)
        _, after = rest.split(MANAGED_END, 1)
        config = clean_blank_lines(before.rstrip(), after.lstrip())
    return remove_legacy_agent_db_config(config)


def has_existing_default_permissions(config: str) -> bool:
    match = TABLE.search(config)
    top_level = config[: match.start()] if match is not None else config
    return ANY_DEFAULT_PERMISSIONS.search(top_level) is not None


def generated_uses_agent_db_permissions(generated: str) -> bool:
    return DEFAULT_PERMISSIONS.search(generated + "\n") is not None


def check_default_permissions_conflict(config: str) -> None:
    if has_existing_default_permissions(config):
        raise ValueError(
            "codex.permissions_profile enforce cannot be used while config.toml already "
            "sets default_permissions outside the agent-db managed block"
        )


def clean_blank_lines(*parts: str) -> str:
    blocks = [part.strip() for part in parts if part.strip()]
    return "\n\n".join(blocks) + "\n"


TABLE_HEADER = re.compile(r"(?m)^\[([^\]]+)\]")


def remove_generated_top_level_keys(config: str, generated: str) -> str:
    scalar_keys = generated_top_level_scalar_keys(generated)
    table_headers = generated_table_headers(generated)
    if not scalar_keys and not table_headers:
        return config

    match = TABLE.search(config)
    top_level = config[: match.start()] if match is not None else config
    rest = config[match.start() :] if match is not None else ""
    for key in scalar_keys:
        top_level = re.sub(rf"(?m)^{re.escape(key)}\s*=.*\n?", "", top_level)
    for header in table_headers:
        rest = remove_table_section(rest, header)
    return clean_blank_lines(top_level.rstrip(), rest.lstrip())


def generated_top_level_scalar_keys(config: str) -> set[str]:
    match = TABLE.search(config)
    top_level = config[: match.start()] if match is not None else config
    return {m.group(1) for m in TOP_LEVEL_ASSIGN.finditer(top_level)}


def generated_table_headers(config: str) -> set[str]:
    return {m.group(1) for m in TABLE_HEADER.finditer(config)}


def remove_table_section(config: str, header: str) -> str:
    # (?m)^\[header\]\n...until next [header] or end
    pattern = re.compile(rf"(?m)^\[{re.escape(header)}\]\n(?:(?!\[).*\n?)*")
    return pattern.sub("", config)


def codex_settings(settings: dict[str, Any]) -> dict[str, Any]:
    validate_namespaces(settings)
    codex = settings.get("codex", {})
    if not isinstance(codex, dict):
        raise ValueError("codex settings must be a mapping")
    return codex


def codex_passthrough(codex: dict[str, Any]) -> list[str]:
    scalars: list[str] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    for key in codex:
        if key in CODEX_DERIVED_KEYS:
            continue
        value = codex[key]
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            scalars.append(f"{toml_key(key)} = {toml_scalar(value)}")
    lines = list(scalars)
    for table_key, table_value in tables:
        if lines:
            lines.append("")
        lines.extend(toml_section(table_key, table_value))
    return lines


def toml_section(prefix: str, data: dict[str, Any]) -> list[str]:
    lines = [f"[{prefix}]"]
    subtables: list[tuple[str, dict[str, Any]]] = []
    for key, value in data.items():
        if isinstance(value, dict):
            subtables.append((f"{prefix}.{toml_key(key)}", value))
        else:
            lines.append(f"{toml_key(key)} = {toml_scalar(value)}")
    for sub_prefix, sub_value in subtables:
        lines.append("")
        lines.extend(toml_section(sub_prefix, sub_value))
    return lines


def toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return toml_bool(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        return toml_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_scalar(item) for item in value) + "]"
    raise ValueError(f"unsupported TOML value: {type(value).__name__}")


def toml_key(key: str) -> str:
    if BARE_KEY.match(key):
        return key
    return toml_string(key)


def render_lines(lines: list[str]) -> str:
    return "\n".join(lines) + "\n" if lines else ""


def codex_permissions_profile(codex: dict[str, Any]) -> str:
    profile = codex.get("permissions_profile", CODEX_PROFILE_ADVISORY)
    if profile not in {CODEX_PROFILE_ADVISORY, CODEX_PROFILE_ENFORCE}:
        raise ValueError("codex.permissions_profile must be advisory or enforce")
    return profile


def check_sandbox_profile_conflict(codex: dict[str, Any], profile: str) -> None:
    if profile != CODEX_PROFILE_ENFORCE:
        return
    conflict = CODEX_SANDBOX_KEYS & set(codex)
    if conflict:
        names = ", ".join(sorted(conflict))
        raise ValueError(
            f"codex.permissions_profile enforce conflicts with sandbox-era keys: {names}"
            " (configure either default_permissions/[permissions] or"
            " sandbox_mode/sandbox_workspace_write, not both)"
        )


def codex_network(codex: dict[str, Any]) -> dict[str, str]:
    network = codex.get("network")
    if network is None:
        return {}
    if not isinstance(network, dict):
        raise ValueError("codex.network must be a mapping")

    output: dict[str, str] = {}
    if "enabled" in network:
        enabled = network["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError("codex.network.enabled must be a boolean")
        output["enabled"] = toml_bool(enabled)

    if "mode" in network:
        mode = network["mode"]
        if not isinstance(mode, str):
            raise ValueError("codex.network.mode must be a string")
        output["mode"] = toml_string(mode)
    return output


def codex_filesystem(permissions: Any) -> dict[str, str]:
    if not isinstance(permissions, dict):
        return {}

    paths = permissions.get("paths", {})
    if not isinstance(paths, dict):
        return {}

    output: dict[str, str] = {}
    for rule in paths.get("allow", []):
        output[rule["path"]] = codex_path_level(rule.get("permissions", []))
    for rule in paths.get("deny", []):
        output[rule["path"]] = "none"
    return output


def codex_path_level(permissions: list[str]) -> str:
    if "write" in permissions or "edit" in permissions:
        return "write"
    return "read"


def codex_path(path: str) -> str:
    if path.endswith("/**"):
        path = path[:-3]
    if path.startswith("~/"):
        return str(Path(path).expanduser())
    return path


def toml_bool(value: bool) -> str:
    return "true" if value else "false"


def write_rules(source: AgentSource, rules_dir: Path) -> list[Path]:
    written: list[Path] = []
    for layer in source.layers:
        for doc in layer.settings:
            rules = render_rules(doc_settings(doc).get("permissions", {}))
            if not rules:
                continue
            rules_dir.mkdir(parents=True, exist_ok=True)
            path = rules_dir / f"{doc.name}.rules"
            if files.write_text(path, rules):
                written.append(path)
    return written


def render_rules(permissions: Any) -> str:
    if not isinstance(permissions, dict):
        return ""

    commands = permissions.get("commands", {})
    if not isinstance(commands, dict):
        return ""

    blocks: list[str] = []
    skipped: list[str] = []
    for action, patterns in commands.items():
        decision = DECISION.get(action)
        if decision is None:
            continue
        for pattern in patterns:
            prefix = command_prefix(pattern)
            if prefix is None:
                skipped.append(pattern)
                continue
            blocks.append(render_prefix_rule(prefix, decision))

    if skipped:
        blocks.append(render_skipped_rules(skipped))
    return "\n\n".join(blocks).strip() + "\n" if blocks else ""


def render_prefix_rule(pattern: list[str], decision: str) -> str:
    return "\n".join(
        [
            "prefix_rule(",
            f"    pattern = {json.dumps(pattern)},",
            f"    decision = {json.dumps(decision)},",
            ")",
        ]
    )


def command_prefix(pattern: str) -> list[str] | None:
    parts = shlex.split(pattern)
    if "<<" in parts or "<<<" in parts:
        return None
    if parts and parts[-1] == "*":
        parts = parts[:-1]
    return parts or [pattern]


def render_skipped_rules(patterns: list[str]) -> str:
    lines = [
        "# Not emitted as prefix_rule entries:",
        "# Codex rules match argv prefixes, while heredocs are shell syntax.",
    ]
    lines.extend(f"# - {pattern}" for pattern in patterns)
    return "\n".join(lines)


def toml_string(value: str) -> str:
    return json.dumps(value)


def copy_assets(assets: tuple[Any, ...], target_root: Path) -> list[Path]:
    written: list[Path] = []
    for asset in assets:
        target = target_root / asset.name
        for source_file in sorted(asset.path.rglob("*")):
            if not source_file.is_file():
                continue
            relative = source_file.relative_to(asset.path)
            target_file = target / relative
            if files.copy_file(source_file, target_file):
                written.append(target_file)
    return written


def write_agents(agents: tuple[Any, ...], target_root: Path) -> list[Path]:
    written: list[Path] = []
    for agent in agents:
        source = agent.path / f"{agent.name}.md"
        if not source.is_file():
            continue
        target = target_root / f"{agent.name}.toml"
        content = render_agent_toml(agent.name, source.read_text(encoding="utf-8"))
        if files.write_text(target, content):
            written.append(target)
    return written


def render_agent_toml(name: str, instructions: str) -> str:
    return "\n".join(
        [
            f"name = {toml_string(name)}",
            'instructions = """',
            instructions.rstrip(),
            '"""',
            "",
        ]
    )
