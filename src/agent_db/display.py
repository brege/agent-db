from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_db.schema import LoadTiming, LoadedContext, Scope, SourceType


def loaded_context_data(ctx: LoadedContext) -> dict[str, Any]:
    return {
        "agent": ctx.agent.value,
        "cwd": str(ctx.cwd),
        "project_root": str(ctx.project_root) if ctx.project_root else None,
        "files": [
            {
                "section": source.load_timing.value,
                "scope": source.scope.value,
                "type": source.source_type.value,
                "path": str(source.output_path),
                "requires_trust": source.requires_trust,
                "path_globs": list(source.path_globs or ()),
            }
            for source in ctx.sources
        ],
        "config": [
            {
                "scope": setting.scope.value,
                "format": setting.format,
                "path": str(setting.source_path),
                "requires_trust": setting.requires_trust,
            }
            for setting in ctx.settings_sources
        ],
    }


def format_loaded_context(data: dict[str, Any]) -> str:
    if not data["files"] and not data["config"]:
        return "\n".join([
            f"{data['agent'].upper()} {data['cwd']}",
            f"root {data['project_root'] or '(none)'}",
            "no files",
        ])

    lines = []
    lines.append(f"{data['agent'].upper()} {data['cwd']}")
    lines.append(f"root {data['project_root'] or '(none)'}")

    by_timing = {}
    for item in data["files"]:
        by_timing.setdefault(item["section"], []).append(item)

    timing_order = [
        LoadTiming.STARTUP.value,
        LoadTiming.ON_READ_MATCH.value,
        LoadTiming.ON_DEMAND.value,
        LoadTiming.ON_DELEGATE.value,
        LoadTiming.REQUIRES_APPROVAL.value,
    ]

    for timing in timing_order:
        if timing not in by_timing:
            continue

        label = {
            LoadTiming.STARTUP.value: "startup",
            LoadTiming.ON_READ_MATCH.value: "on read",
            LoadTiming.ON_DEMAND.value: "on demand",
            LoadTiming.ON_DELEGATE.value: "on delegate",
            LoadTiming.REQUIRES_APPROVAL.value: "approval",
        }[timing]

        lines.append("")
        lines.append(label)

        for item in by_timing[timing]:
            scope = scope_label(item["scope"])
            kind = type_label(item["type"])
            trust_note = " [!trust]" if item["requires_trust"] else ""
            glob_note = f" (paths: {', '.join(item['path_globs'])})" if item["path_globs"] else ""
            lines.append(
                f"  {scope:7} {kind:8} "
                f"{display_path(item['path'], data)}{trust_note}{glob_note}"
            )

    if data["config"]:
        lines.append("")
        lines.append("config")
        for item in data["config"]:
            scope = scope_label(item["scope"])
            trust_note = " [!trust]" if item["requires_trust"] else ""
            lines.append(
                f"  {scope:7} {item['format']:8} "
                f"{display_path(item['path'], data)}{trust_note}"
            )

    return "\n".join(lines)


def scope_label(value: str) -> str:
    return {
        Scope.MANAGED.value: "managed",
        Scope.USER.value: "user",
        Scope.PROJECT.value: "project",
        Scope.LOCAL.value: "local",
        Scope.ADDITIONAL.value: "added",
    }[value]


def type_label(value: str) -> str:
    return {
        SourceType.MEMORY.value: "memory",
        SourceType.RULES.value: "rules",
        SourceType.CONFIG.value: "config",
        SourceType.SKILLS.value: "skills",
        SourceType.AGENTS.value: "agents",
        SourceType.PLUGINS.value: "plugins",
        SourceType.MCP.value: "mcp",
    }[value]


def display_path(path: str, data: dict[str, Any]) -> str:
    resolved = Path(path)
    project_root = data["project_root"]
    if project_root:
        project_root_path = Path(project_root)
        if resolved.is_relative_to(project_root_path):
            return "./" + str(resolved.relative_to(project_root_path))
    if resolved.is_relative_to(Path.home()):
        return "~/" + str(resolved.relative_to(Path.home()))
    return path


def format_summary(ctx: LoadedContext) -> str:
    startup_count = len(ctx.startup_sources)
    on_demand_count = len(ctx.on_demand_sources)
    on_read_count = len(ctx.on_read_match_sources)

    parts = [
        f"{ctx.agent.upper()}:",
        f"{startup_count} startup",
    ]
    if on_demand_count:
        parts.append(f"{on_demand_count} on-demand")
    if on_read_count:
        parts.append(f"{on_read_count} on-read-match")
    parts.append(f"from {len(set(s.scope for s in ctx.sources))} scopes")

    return ", ".join(parts)
