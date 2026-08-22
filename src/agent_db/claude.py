"""Claude emitter: project merged settings into ~/.claude/.

Pass-through for all keys under claude: in the authored YAML. The only
derived output is the permissions block, translated from the shared
permissions: namespace into Claude's Bash()/Read()/Edit() rule format.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent_db import files
from agent_db.source import (
    AgentSource,
    assemble,
    render_instruction_file,
    validate_namespaces,
)

AGENT_NAMESPACES = {"claude", "codex"}
OUTPUT_STYLE_FILE = "agent-db.md"
OUTPUT_STYLE_NAME = "Agent DB"


def write_global(source: AgentSource, claude_home: Path) -> list[Path]:
    home = claude_home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)

    assembly = assemble(source)

    written: list[Path] = []
    sections = assembly.sections
    output_style_sections = tuple(section for section in sections if section.claude_output_style)

    claude_md = home / "CLAUDE.md"
    rendered = render_instruction_file(claude_md.name, sections, assembly.settings)
    if files.write_text(claude_md, rendered):
        written.append(claude_md)

    output_style = output_style_name(output_style_sections)
    if output_style is not None:
        path = home / "output-styles" / OUTPUT_STYLE_FILE
        if files.write_text(path, render_output_style(output_style_sections)):
            written.append(path)

    settings = home / "settings.json"
    if write_settings(settings, assembly.settings, output_style=output_style):
        written.append(settings)

    written.extend(files.copy_assets(assembly.skills, home / "skills"))
    written.extend(copy_agents(assembly.agents, home / "agents"))
    return written


def render_output_style(sections: Any) -> str:
    blocks = [
        "---",
        f"name: {OUTPUT_STYLE_NAME}",
        "description: Generated communication defaults from agent-db",
        "keep-coding-instructions: true",
        "---",
    ]
    for section in sections:
        blocks.append(section.body.strip())
    return "\n\n".join(blocks).strip() + "\n"


def output_style_name(sections: Any) -> str | None:
    return OUTPUT_STYLE_NAME if sections else None


def render_settings(settings: dict[str, Any], output_style: str | None = None) -> str:
    return json.dumps(claude_settings(settings, output_style=output_style), indent=2) + "\n"


def write_settings(path: Path, settings: dict[str, Any], output_style: str | None = None) -> bool:
    existing = read_settings(path)
    layered = layer_settings(existing, claude_settings(settings, output_style=output_style))
    return files.write_text(path, json.dumps(layered, indent=2) + "\n")


def read_settings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Claude settings must be a JSON object: {path}")
    return data


def layer_settings(existing: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    output = {
        key: deepcopy(value)
        for key, value in existing.items()
        if key not in AGENT_NAMESPACES and key != "permissions"
    }
    for key, value in generated.items():
        output[key] = deepcopy(value)
    return output


def claude_settings(settings: dict[str, Any], output_style: str | None = None) -> dict[str, Any]:
    validate_namespaces(settings)
    claude = settings.get("claude", {})
    if not isinstance(claude, dict):
        raise TypeError("claude settings must be a mapping")
    output = deepcopy(claude)
    if output_style is not None and "outputStyle" not in output:
        output["outputStyle"] = output_style
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
