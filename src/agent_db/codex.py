from __future__ import annotations

from datetime import UTC, datetime
import json
import re
import shlex
import shutil
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
TABLE = re.compile(r"^\s*\[", re.MULTILINE)
DEFAULT_PERMISSIONS = re.compile(r'(?m)^default_permissions\s*=\s*"agent_db"\s*\n(?:\n)?')
ANY_DEFAULT_PERMISSIONS = re.compile(r'(?m)^default_permissions\s*=\s*".*?"\s*$')
AGENT_DB_TABLE = re.compile(
    r'(?ms)^\[permissions\.agent_db(?:\.[^\]]+)?\]\n.*?(?=^\[|\Z)'
)


def write_global(source: AgentSource, codex_home: Path) -> list[Path]:
    home = codex_home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    agents_md = home / "AGENTS.md"
    if files.write_text(agents_md, render_agents_md(source)):
        written.append(agents_md)

    config = home / "config.toml"
    if write_config(config, render_config(merged_settings(source))):
        written.append(config)

    written.extend(write_rules(source, home / "rules"))
    written.extend(copy_assets(merged_skills(source), home / "skills"))
    written.extend(write_agents(merged_agents(source), home / "agents"))
    return written


def render_agents_md(source: AgentSource) -> str:
    blocks = [render_agents_section(section) for section in assemble_sections(source)]
    restrictions = render_restrictions(merged_settings(source))
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
    filesystem = codex_filesystem(settings.get("permissions", {}))
    if not filesystem:
        return ""

    lines = [
        'default_permissions = "agent_db"',
        "",
        "[permissions.agent_db.filesystem]",
        f"glob_scan_max_depth = {GLOB_SCAN_MAX_DEPTH}",
    ]
    for path, value in filesystem.items():
        lines.append(f"{toml_string(codex_path(path))} = {toml_string(value)}")
    return "\n".join(lines) + "\n"


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
        return existing

    if MANAGED_BEGIN in existing and MANAGED_END in existing:
        before, rest = existing.split(MANAGED_BEGIN, 1)
        _, after = rest.split(MANAGED_END, 1)
        if has_existing_default_permissions(f"{before}\n{after}"):
            generated = DEFAULT_PERMISSIONS.sub("", generated + "\n").strip()
        managed = f"{MANAGED_BEGIN}\n{generated}\n{MANAGED_END}"
        return clean_blank_lines(before.rstrip(), managed, after.lstrip())

    existing = remove_legacy_agent_db_config(existing)
    if has_existing_default_permissions(existing):
        generated = DEFAULT_PERMISSIONS.sub("", generated + "\n").strip()

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


def has_existing_default_permissions(config: str) -> bool:
    match = TABLE.search(config)
    top_level = config[: match.start()] if match is not None else config
    return ANY_DEFAULT_PERMISSIONS.search(top_level) is not None


def clean_blank_lines(*parts: str) -> str:
    blocks = [part.strip() for part in parts if part.strip()]
    return "\n\n".join(blocks) + "\n"


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
