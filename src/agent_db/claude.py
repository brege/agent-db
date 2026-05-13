from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_db import files
from agent_db.source import AgentSource, assemble_sections, merged_agents, merged_settings, merged_skills


def write_global(source: AgentSource, claude_home: Path) -> list[Path]:
    home = claude_home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    sections = assemble_sections(source)

    rules_dir = home / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    for section in sections:
        path = rules_dir / f"{section.key}.md"
        if files.write_text(path, section.body):
            written.append(path)

    claude_md = home / "CLAUDE.md"
    if files.write_text(claude_md, render_claude_md(sections)):
        written.append(claude_md)

    settings = home / "settings.json"
    if files.write_text(settings, render_settings(merged_settings(source))):
        written.append(settings)

    written.extend(copy_assets(merged_skills(source), home / "skills"))
    written.extend(copy_agents(merged_agents(source), home / "agents"))
    return written


def render_claude_md(sections: Any) -> str:
    blocks = ["# CLAUDE.md"]
    for section in sections:
        blocks.append(f"## {section.title}\n\n@rules/{section.key}.md")
    return "\n\n".join(blocks).strip() + "\n"


def render_settings(settings: dict[str, Any]) -> str:
    return json.dumps(claude_settings(settings), indent=2) + "\n"


def claude_settings(settings: dict[str, Any]) -> dict[str, Any]:
    output = {
        key: value
        for key, value in settings.items()
        if key != "permissions"
    }
    permissions = claude_permissions(settings.get("permissions", {}))
    if permissions:
        output["permissions"] = permissions
    return output


def claude_permissions(permissions: Any) -> dict[str, list[str]]:
    if not isinstance(permissions, dict):
        return {}

    output: dict[str, list[str]] = {}
    commands = permissions.get("commands", {})
    if isinstance(commands, dict):
        for action, patterns in commands.items():
            for pattern in patterns:
                append_unique(output.setdefault(action, []), f"Bash({claude_command(pattern)})")

    paths = permissions.get("paths", {})
    if isinstance(paths, dict):
        for action, rules in paths.items():
            for rule in rules:
                path = rule.get("path")
                for tool in claude_path_tools(rule.get("permissions", [])):
                    append_unique(output.setdefault(action, []), f"{tool}({path})")

    return output


def claude_path_tools(permissions: list[str]) -> list[str]:
    tools: list[str] = []
    if "read" in permissions or "glob" in permissions:
        tools.append("Read")
    if "edit" in permissions or "write" in permissions:
        tools.append("Edit")
    return tools


def claude_command(pattern: str) -> str:
    if pattern.endswith(" *"):
        return f"{pattern[:-2]}:*"
    return pattern


def append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def copy_assets(assets: Any, target_root: Path) -> list[Path]:
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


def copy_agents(agents: Any, target_root: Path) -> list[Path]:
    written: list[Path] = []
    for agent in agents:
        source = agent.path / f"{agent.name}.md"
        if not source.is_file():
            continue
        target = target_root / source.name
        if files.copy_file(source, target):
            written.append(target)
    return written
