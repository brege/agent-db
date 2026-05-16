from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent_db.schema import Agent, LoadedContext, LoadTiming, Scope, SourceType

TIMING_ORDER = [
    LoadTiming.STARTUP.value,
    LoadTiming.ON_READ_MATCH.value,
    LoadTiming.ON_DEMAND.value,
    LoadTiming.ON_DELEGATE.value,
    LoadTiming.REQUIRES_APPROVAL.value,
]

SECTION_LABELS = {
    LoadTiming.STARTUP.value: "startup",
    LoadTiming.ON_READ_MATCH.value: "on read",
    LoadTiming.ON_DEMAND.value: "on demand",
    LoadTiming.ON_DELEGATE.value: "on delegate",
    LoadTiming.REQUIRES_APPROVAL.value: "approval",
}

SCOPE_STYLES = {
    Scope.MANAGED.value: "dim white",
    Scope.USER.value: "dim cyan",
    Scope.PROJECT.value: "green",
    Scope.LOCAL.value: "yellow",
    Scope.ADDITIONAL.value: "cyan",
}

TYPE_STYLES = {
    SourceType.MEMORY.value: "magenta",
    SourceType.RULES.value: "blue",
    SourceType.CONFIG.value: "yellow",
    SourceType.SKILLS.value: "green",
    SourceType.AGENTS.value: "red",
    SourceType.PLUGINS.value: "cyan",
    SourceType.MCP.value: "cyan",
}

SCOPE_WIDTH = 15
KIND_WIDTH = 15


class MemoryFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section: LoadTiming
    scope: Scope
    type: SourceType
    path: str
    requires_trust: bool
    path_globs: tuple[str, ...] = ()


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Scope
    format: str
    path: str
    requires_trust: bool


class MemoryContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: Agent
    cwd: str
    project_root: str | None
    files: tuple[MemoryFile, ...] = ()
    config: tuple[MemoryConfig, ...] = ()


class MemoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contexts: tuple[MemoryContext, ...]


def loaded_context_model(ctx: LoadedContext) -> MemoryContext:
    return MemoryContext(
        agent=ctx.agent,
        cwd=str(ctx.cwd),
        project_root=str(ctx.project_root) if ctx.project_root else None,
        files=tuple(
            MemoryFile(
                section=source.load_timing,
                scope=source.scope,
                type=source.source_type,
                path=str(source.output_path),
                requires_trust=source.requires_trust,
                path_globs=tuple(source.path_globs or ()),
            )
            for source in ctx.sources
        ),
        config=tuple(
            MemoryConfig(
                scope=setting.scope,
                format=setting.format,
                path=str(setting.source_path),
                requires_trust=setting.requires_trust,
            )
            for setting in ctx.settings_sources
        ),
    )


def loaded_context_data(ctx: LoadedContext) -> dict[str, Any]:
    return loaded_context_model(ctx).model_dump(mode="json")


def print_loaded_context(console: Console, data: MemoryContext | dict[str, Any]) -> None:
    console.print(render_loaded_context(data))


def format_loaded_context(
    data: MemoryContext | dict[str, Any],
    *,
    width: int = 120,
) -> str:
    output = StringIO()
    console = Console(
        file=output,
        force_terminal=False,
        color_system=None,
        width=width,
    )
    print_loaded_context(console, data)
    return output.getvalue().rstrip("\n")


def render_loaded_context(data: MemoryContext | dict[str, Any]) -> Panel:
    data = context_data(data)
    title = Text.assemble((data["agent"].upper(), "bold"), " ", home_path(data["cwd"]))
    root = Text.assemble(
        ("root ", "dim"),
        home_path(data["project_root"]) if data["project_root"] else "(none)",
    )

    if not data["files"] and not data["config"]:
        body = Group(root, Text("no files", style="dim"))
        return Panel(body, title=title)

    by_timing = {}
    for item in data["files"]:
        by_timing.setdefault(item["section"], []).append(item)

    parts: list[Any] = [root]
    for timing in TIMING_ORDER:
        items = by_timing.get(timing)
        if not items:
            continue
        parts.append(Text(SECTION_LABELS[timing], style="bold"))
        parts.append(source_table(items, data, kind_key="type"))

    if data["config"]:
        parts.append(Text("config", style="bold"))
        parts.append(source_table(data["config"], data, kind_key="format"))

    return Panel(Group(*parts), title=title)


def context_data(data: MemoryContext | dict[str, Any]) -> dict[str, Any]:
    if isinstance(data, MemoryContext):
        return data.model_dump(mode="json")
    return MemoryContext.model_validate(data).model_dump(mode="json")


def source_table(
    items: list[dict[str, Any]],
    data: dict[str, Any],
    *,
    kind_key: str,
) -> Table:
    table = Table.grid(padding=(0, 2), expand=True)
    table.add_column(width=SCOPE_WIDTH, no_wrap=True)
    table.add_column(width=KIND_WIDTH, no_wrap=True)
    table.add_column(ratio=1, overflow="fold")
    for item in items:
        add_source_row(table, item, data, kind_key=kind_key)
    return table


def add_source_row(
    table: Table,
    item: dict[str, Any],
    data: dict[str, Any],
    *,
    kind_key: str,
) -> None:
    path = Text(display_path(item["path"], data))
    if item.get("path_globs"):
        path.append(f" (paths: {', '.join(item['path_globs'])})", style="dim")
    if item["requires_trust"]:
        path.append(" ")
        path.append("[!trust]", style="bold red")
    table.add_row(
        Text(scope_label(item["scope"]), style=SCOPE_STYLES[item["scope"]]),
        Text(kind_label(item, kind_key), style=kind_style(item, kind_key)),
        path,
    )


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


def kind_label(item: dict[str, Any], kind_key: str) -> str:
    if kind_key == "type":
        if item[kind_key] == SourceType.CONFIG.value:
            return config_label(item["path"])
        return type_label(item[kind_key])
    return settings_label(item[kind_key])


def kind_style(item: dict[str, Any], kind_key: str) -> str:
    if kind_key == "type":
        return TYPE_STYLES[item[kind_key]]
    return TYPE_STYLES[SourceType.CONFIG.value]


def settings_label(format_name: str) -> str:
    if format_name == "json":
        return "settings"
    if format_name == "toml":
        return "config"
    return format_name


def config_label(path: str) -> str:
    name = Path(path).name
    if name.startswith("settings") and name.endswith(".json"):
        return "settings"
    return type_label(SourceType.CONFIG.value)


def home_path(path: str) -> str:
    resolved = Path(path)
    if resolved.is_relative_to(Path.home()):
        return "~/" + str(resolved.relative_to(Path.home()))
    return path


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
