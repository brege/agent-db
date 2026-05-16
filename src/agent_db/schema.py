from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

AT_IMPORT = re.compile(r"^@(.+)$", re.MULTILINE)


class Agent(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"


class SourceType(StrEnum):
    MEMORY = "memory"
    RULES = "rules"
    CONFIG = "config"
    SKILLS = "skills"
    AGENTS = "agents"
    PLUGINS = "plugins"
    MCP = "mcp"


class Scope(StrEnum):
    MANAGED = "managed"
    USER = "user"
    PROJECT = "project"
    LOCAL = "local"
    ADDITIONAL = "additional"


class LoadTiming(StrEnum):
    STARTUP = "startup"
    ON_DEMAND = "on-demand"
    ON_READ_MATCH = "on-read-match"
    ON_DELEGATE = "on-delegate"
    REQUIRES_APPROVAL = "requires-approval"


@dataclass(frozen=True)
class InstructionSource:
    agent: Agent
    source_type: SourceType
    scope: Scope
    load_timing: LoadTiming

    output_path: Path

    layer_name: str
    source_path: Path

    path_globs: tuple[str, ...] | None
    requires_trust: bool = False

    description: str = ""

    @property
    def load_order_key(self) -> tuple[int, int, str]:
        """Sort key for load precedence.

        Returns (precedence_tier, timing_order, scope_order).
        Lower is earlier/higher priority.
        """
        # Precedence: managed < user < project < local < additional
        scope_order = {
            "managed": 0,
            "user": 1,
            "project": 2,
            "local": 3,
            "additional": 4,
        }[self.scope]

        # Load timing within same scope
        timing_order = {
            "startup": 0,
            "on-read-match": 1,
            "on-demand": 2,
            "on-delegate": 3,
            "requires-approval": 4,
        }[self.load_timing]

        return (scope_order, timing_order, self.scope)


@dataclass(frozen=True)
class SettingsSource:
    agent: Agent
    scope: Scope
    format: str
    output_path: Path

    layer_name: str
    source_path: Path

    requires_trust: bool = False
    description: str = ""
    precedence_order: int = 0


@dataclass(frozen=True)
class RulesSource:
    agent: Agent
    scope: Scope
    rule_type: str
    action: str
    pattern: str
    output_path: Path

    layer_name: str
    source_path: Path

    requires_trust: bool = False
    description: str = ""


@dataclass(frozen=True)
class LoadedContext:
    agent: Agent
    cwd: Path
    project_root: Path | None

    sources: tuple[InstructionSource, ...]
    settings_sources: tuple[SettingsSource, ...] = ()
    rules_sources: tuple[RulesSource, ...] = ()

    @property
    def startup_sources(self) -> tuple[InstructionSource, ...]:
        return tuple(s for s in self.sources if s.load_timing == LoadTiming.STARTUP)

    @property
    def on_demand_sources(self) -> tuple[InstructionSource, ...]:
        return tuple(s for s in self.sources if s.load_timing == LoadTiming.ON_DEMAND)

    @property
    def on_read_match_sources(self) -> tuple[InstructionSource, ...]:
        return tuple(s for s in self.sources if s.load_timing == LoadTiming.ON_READ_MATCH)

    def by_scope(self, scope: Scope) -> tuple[InstructionSource, ...]:
        return tuple(s for s in self.sources if s.scope == scope)

    def by_type(self, source_type: SourceType) -> tuple[InstructionSource, ...]:
        return tuple(s for s in self.sources if s.source_type == source_type)


def find_git_root(cwd: Path) -> Path | None:
    """Walk up from cwd to find git repository root.

    Handles both .git directories (normal repos) and .git files (worktrees/submodules).
    """
    current = cwd.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def paths_to_cwd(cwd: Path, git_root: Path) -> list[Path]:
    paths = []
    current = cwd.resolve()
    while current.is_relative_to(git_root):
        paths.append(current)
        if current == git_root:
            break
        current = current.parent
    paths.reverse()
    return paths


def claude_load_order(
    cwd: Path,
    *,
    claude_home: Path | None = None,
) -> LoadedContext:
    """Compute what Claude actually loads from a given cwd.

    Loads in this order:
    1. Managed CLAUDE.md (system policy)
    2. ~/.claude/CLAUDE.md
    3. ~/.claude/rules/*.md (unconditional)
    4. ./CLAUDE.md walking up from cwd
    5. ./.claude/CLAUDE.md walking up from cwd
    6. .claude/rules/*.md (unconditional) walking up
    7. .claude/rules/*.md (path-scoped) when files match
    8. ~/.claude/projects/<project>/memory/MEMORY.md (first 200 lines)
    9. ~/.claude/skills/
    10. ./.claude/skills/ (closest wins)
    11. ~/.claude/agents/ (on-delegate)
    12. ./.claude/agents/ (on-delegate)
    """
    sources: list[InstructionSource] = []
    git_root = find_git_root(cwd)

    _claude_home = (
        claude_home or Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()
    )

    user_claude_md = _claude_home / "CLAUDE.md"
    sources.append(
        InstructionSource(
            agent=Agent.CLAUDE,
            source_type=SourceType.MEMORY,
            scope=Scope.USER,
            load_timing=LoadTiming.STARTUP,
            output_path=user_claude_md,
            layer_name="user",
            source_path=user_claude_md,
            path_globs=None,
            description="User's global instructions",
        )
    )
    sources.extend(_resolve_at_imports(user_claude_md, Agent.CLAUDE, Scope.USER, "user"))

    user_rules_dir = _claude_home / "rules"
    if user_rules_dir.is_dir():
        for rule_file in sorted(user_rules_dir.glob("*.md")):
            sources.append(
                InstructionSource(
                    agent=Agent.CLAUDE,
                    source_type=SourceType.RULES,
                    scope=Scope.USER,
                    load_timing=LoadTiming.STARTUP,
                    output_path=rule_file,
                    layer_name="user",
                    source_path=rule_file,
                    path_globs=None,
                    description=f"User rule: {rule_file.stem}",
                )
            )

    if git_root is not None:
        for directory in paths_to_cwd(cwd, git_root):
            claude_md = directory / "CLAUDE.md"
            if claude_md.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CLAUDE,
                        source_type=SourceType.MEMORY,
                        scope=Scope.PROJECT,
                        load_timing=LoadTiming.STARTUP,
                        output_path=claude_md,
                        layer_name="project",
                        source_path=claude_md,
                        path_globs=None,
                        description=f"Project instructions at {claude_md.relative_to(git_root)}",
                    )
                )
                sources.extend(
                    _resolve_at_imports(
                        claude_md,
                        Agent.CLAUDE,
                        Scope.PROJECT,
                        "project",
                    )
                )

            dot_claude_md = directory / ".claude" / "CLAUDE.md"
            if dot_claude_md.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CLAUDE,
                        source_type=SourceType.MEMORY,
                        scope=Scope.PROJECT,
                        load_timing=LoadTiming.STARTUP,
                        output_path=dot_claude_md,
                        layer_name="project",
                        source_path=dot_claude_md,
                        path_globs=None,
                        description=(
                            f"Project instructions at {dot_claude_md.relative_to(git_root)}"
                        ),
                    )
                )
                sources.extend(
                    _resolve_at_imports(
                        dot_claude_md,
                        Agent.CLAUDE,
                        Scope.PROJECT,
                        "project",
                    )
                )

            claude_local_md = directory / "CLAUDE.local.md"
            if claude_local_md.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CLAUDE,
                        source_type=SourceType.MEMORY,
                        scope=Scope.LOCAL,
                        load_timing=LoadTiming.STARTUP,
                        output_path=claude_local_md,
                        layer_name="local",
                        source_path=claude_local_md,
                        path_globs=None,
                        description=(
                            f"Local instructions at {claude_local_md.relative_to(git_root)}"
                        ),
                    )
                )
                sources.extend(
                    _resolve_at_imports(
                        claude_local_md,
                        Agent.CLAUDE,
                        Scope.LOCAL,
                        "local",
                    )
                )

            project_rules_dir = directory / ".claude" / "rules"
            if project_rules_dir.is_dir():
                for rule_file in sorted(project_rules_dir.glob("*.md")):
                    is_path_scoped = _has_path_frontmatter(rule_file)
                    sources.append(
                        InstructionSource(
                            agent=Agent.CLAUDE,
                            source_type=SourceType.RULES,
                            scope=Scope.PROJECT,
                            load_timing=(
                                LoadTiming.ON_READ_MATCH if is_path_scoped else LoadTiming.STARTUP
                            ),
                            output_path=rule_file,
                            layer_name="project",
                            source_path=rule_file,
                            path_globs=_extract_path_globs(rule_file) if is_path_scoped else None,
                            description=f"Project rule: {rule_file.stem}",
                        )
                    )

            project_settings = directory / ".claude" / "settings.json"
            if project_settings.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CLAUDE,
                        source_type=SourceType.CONFIG,
                        scope=Scope.PROJECT,
                        load_timing=LoadTiming.STARTUP,
                        output_path=project_settings,
                        layer_name="project",
                        source_path=project_settings,
                        path_globs=None,
                        requires_trust=True,
                        description=f"Project config at {project_settings.relative_to(git_root)}",
                    )
                )

            local_settings = directory / ".claude" / "settings.local.json"
            if local_settings.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CLAUDE,
                        source_type=SourceType.CONFIG,
                        scope=Scope.LOCAL,
                        load_timing=LoadTiming.STARTUP,
                        output_path=local_settings,
                        layer_name="local",
                        source_path=local_settings,
                        path_globs=None,
                        description=f"Local config at {local_settings.relative_to(git_root)}",
                    )
                )

    if git_root:
        memory_dir = _claude_home / "projects" / str(git_root.resolve()).replace("/", "-")[1:]
        memory_md = memory_dir / "MEMORY.md"
        if memory_md.is_file():
            sources.append(
                InstructionSource(
                    agent=Agent.CLAUDE,
                    source_type=SourceType.MEMORY,
                    scope=Scope.LOCAL,
                    load_timing=LoadTiming.STARTUP,
                    output_path=memory_md,
                    layer_name="local",
                    source_path=memory_md,
                    path_globs=None,
                    description="Auto memory (first 200 lines / 25KB)",
                )
            )

    user_skills = _claude_home / "skills"
    if user_skills.is_dir():
        sources.append(
            InstructionSource(
                agent=Agent.CLAUDE,
                source_type=SourceType.SKILLS,
                scope=Scope.USER,
                load_timing=LoadTiming.ON_DEMAND,
                output_path=user_skills,
                layer_name="user",
                source_path=user_skills,
                path_globs=None,
                description="User skills",
            )
        )

    if git_root:
        project_skills = git_root / ".claude" / "skills"
        if project_skills.is_dir():
            sources.append(
                InstructionSource(
                    agent=Agent.CLAUDE,
                    source_type=SourceType.SKILLS,
                    scope=Scope.PROJECT,
                    load_timing=LoadTiming.ON_DEMAND,
                    output_path=project_skills,
                    layer_name="project",
                    source_path=project_skills,
                    path_globs=None,
                    description="Project skills",
                )
            )

    user_agents = _claude_home / "agents"
    if user_agents.is_dir():
        sources.append(
            InstructionSource(
                agent=Agent.CLAUDE,
                source_type=SourceType.AGENTS,
                scope=Scope.USER,
                load_timing=LoadTiming.ON_DELEGATE,
                output_path=user_agents,
                layer_name="user",
                source_path=user_agents,
                path_globs=None,
                description="User subagents",
            )
        )

    if git_root:
        project_agents = git_root / ".claude" / "agents"
        if project_agents.is_dir():
            sources.append(
                InstructionSource(
                    agent=Agent.CLAUDE,
                    source_type=SourceType.AGENTS,
                    scope=Scope.PROJECT,
                    load_timing=LoadTiming.ON_DELEGATE,
                    output_path=project_agents,
                    layer_name="project",
                    source_path=project_agents,
                    path_globs=None,
                    description="Project subagents",
                )
            )

    settings_sources = _load_claude_settings(_claude_home, cwd, git_root)

    rules_sources_list: list[RulesSource] = []
    for settings_src in settings_sources:
        settings_data = json.loads(settings_src.source_path.read_text(encoding="utf-8"))
        if not isinstance(settings_data, dict):
            raise ValueError(f"settings must be a JSON object: {settings_src.source_path}")
        rules = _extract_all_claude_rules(settings_data, settings_src.source_path)
        for rule in rules:
            updated_rule = RulesSource(
                agent=rule.agent,
                scope=settings_src.scope,
                rule_type=rule.rule_type,
                action=rule.action,
                pattern=rule.pattern,
                output_path=settings_src.output_path,
                layer_name=settings_src.layer_name,
                source_path=settings_src.source_path,
                requires_trust=settings_src.requires_trust,
                description=rule.description,
            )
            rules_sources_list.append(updated_rule)

    return LoadedContext(
        agent=Agent.CLAUDE,
        cwd=cwd.resolve(),
        project_root=git_root,
        sources=_dedupe(sources),
        settings_sources=settings_sources,
        rules_sources=tuple(rules_sources_list),
    )


def codex_load_order(
    cwd: Path,
    *,
    codex_home: Path | None = None,
) -> LoadedContext:
    """Compute what Codex actually loads from a given cwd.

    Loads in this order:
    1. ~/.codex/AGENTS.override.md or AGENTS.md
    2. ./AGENTS.md walking from project root to cwd (closest wins)
    3. ~/.codex/config.toml
    4. .codex/config.toml walking from project root to cwd (closest wins, trusted only)
    5. ~/.codex/skills/
    6. ~/.codex/agents/*.toml
    """
    sources: list[InstructionSource] = []
    git_root = find_git_root(cwd)

    _codex_home = codex_home or Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()

    codex_home = _codex_home
    agents_override = codex_home / "AGENTS.override.md"
    agents_md = codex_home / "AGENTS.md"

    if agents_override.is_file():
        sources.append(
            InstructionSource(
                agent=Agent.CODEX,
                source_type=SourceType.MEMORY,
                scope=Scope.USER,
                load_timing=LoadTiming.STARTUP,
                output_path=agents_override,
                layer_name="user",
                source_path=agents_override,
                path_globs=None,
                description="User AGENTS.override.md",
            )
        )
    elif agents_md.is_file():
        sources.append(
            InstructionSource(
                agent=Agent.CODEX,
                source_type=SourceType.MEMORY,
                scope=Scope.USER,
                load_timing=LoadTiming.STARTUP,
                output_path=agents_md,
                layer_name="user",
                source_path=agents_md,
                path_globs=None,
                description="User AGENTS.md",
            )
        )

    if git_root:
        for directory in paths_to_cwd(cwd, git_root):
            project_override = directory / "AGENTS.override.md"
            project_agents = directory / "AGENTS.md"

            if project_override.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CODEX,
                        source_type=SourceType.MEMORY,
                        scope=Scope.PROJECT,
                        load_timing=LoadTiming.STARTUP,
                        output_path=project_override,
                        layer_name="project",
                        source_path=project_override,
                        path_globs=None,
                        requires_trust=True,
                        description=(
                            "Project AGENTS.override.md at "
                            f"{project_override.relative_to(git_root)}"
                        ),
                    )
                )
            elif project_agents.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CODEX,
                        source_type=SourceType.MEMORY,
                        scope=Scope.PROJECT,
                        load_timing=LoadTiming.STARTUP,
                        output_path=project_agents,
                        layer_name="project",
                        source_path=project_agents,
                        path_globs=None,
                        requires_trust=True,
                        description=f"Project AGENTS.md at {project_agents.relative_to(git_root)}",
                    )
                )

    user_config = codex_home / "config.toml"
    if user_config.is_file():
        sources.append(
            InstructionSource(
                agent=Agent.CODEX,
                source_type=SourceType.CONFIG,
                scope=Scope.USER,
                load_timing=LoadTiming.STARTUP,
                output_path=user_config,
                layer_name="user",
                source_path=user_config,
                path_globs=None,
                description="User config.toml",
            )
        )

    if git_root:
        for directory in paths_to_cwd(cwd, git_root):
            project_config = directory / ".codex" / "config.toml"
            if project_config.is_file():
                sources.append(
                    InstructionSource(
                        agent=Agent.CODEX,
                        source_type=SourceType.CONFIG,
                        scope=Scope.PROJECT,
                        load_timing=LoadTiming.STARTUP,
                        output_path=project_config,
                        layer_name="project",
                        source_path=project_config,
                        path_globs=None,
                        requires_trust=True,
                        description=(
                            f"Project config.toml at {project_config.relative_to(git_root)}"
                        ),
                    )
                )

    user_skills = _codex_home / "skills"
    if user_skills.is_dir():
        sources.append(
            InstructionSource(
                agent=Agent.CODEX,
                source_type=SourceType.SKILLS,
                scope=Scope.USER,
                load_timing=LoadTiming.STARTUP,
                output_path=user_skills,
                layer_name="user",
                source_path=user_skills,
                path_globs=None,
                description="User skills",
            )
        )

    if git_root:
        project_skills = git_root / ".agents" / "skills"
        if project_skills.is_dir():
            sources.append(
                InstructionSource(
                    agent=Agent.CODEX,
                    source_type=SourceType.SKILLS,
                    scope=Scope.PROJECT,
                    load_timing=LoadTiming.STARTUP,
                    output_path=project_skills,
                    layer_name="project",
                    source_path=project_skills,
                    path_globs=None,
                    requires_trust=True,
                    description="Project skills",
                )
            )

    user_agents = _codex_home / "agents"
    if user_agents.is_dir():
        sources.append(
            InstructionSource(
                agent=Agent.CODEX,
                source_type=SourceType.AGENTS,
                scope=Scope.USER,
                load_timing=LoadTiming.STARTUP,
                output_path=user_agents,
                layer_name="user",
                source_path=user_agents,
                path_globs=None,
                description="User agents",
            )
        )

    settings_sources = _load_codex_settings(_codex_home, cwd, git_root)
    rules_sources = _load_codex_rules(_codex_home, cwd, git_root)

    return LoadedContext(
        agent=Agent.CODEX,
        cwd=cwd.resolve(),
        project_root=git_root,
        sources=_dedupe(sources),
        settings_sources=settings_sources,
        rules_sources=rules_sources,
    )


def _dedupe(sources: list[InstructionSource]) -> tuple[InstructionSource, ...]:
    seen: set[Path] = set()
    result = []
    for source in sources:
        if source.output_path not in seen:
            seen.add(source.output_path)
            result.append(source)
    return tuple(result)


def _has_path_frontmatter(rule_file: Path) -> bool:
    """Check if a .md rule file has paths: frontmatter."""
    content = rule_file.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False
    lines = content.split("\n")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("paths:"):
            return True
    return False


def _extract_path_globs(rule_file: Path) -> tuple[str, ...]:
    """Extract paths: globs from frontmatter."""
    content = rule_file.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return ()

    lines = content.split("\n")
    in_paths = False
    globs = []

    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("paths:"):
            in_paths = True
            continue
        if in_paths:
            if line.startswith("  - "):
                globs.append(line[4:].strip().strip("\"'"))
            elif line and not line.startswith(" "):
                break

    return tuple(globs)


def _resolve_at_imports(
    md_file: Path,
    agent: Agent,
    scope: Scope,
    layer_name: str,
    depth: int = 0,
) -> list[InstructionSource]:
    """Resolve @path imports from a markdown file (max 5 hops per Claude docs)."""
    if depth >= 5:
        return []
    if not md_file.is_file():
        return []
    content = md_file.read_text(encoding="utf-8")

    imported: list[InstructionSource] = []
    for match in AT_IMPORT.finditer(content):
        raw = match.group(1).strip()
        candidate = (md_file.parent / raw).resolve()
        if not candidate.is_file():
            continue
        imported.append(
            InstructionSource(
                agent=agent,
                source_type=SourceType.RULES,
                scope=scope,
                load_timing=LoadTiming.STARTUP,
                output_path=candidate,
                layer_name=layer_name,
                source_path=candidate,
                path_globs=None,
                description=f"@-imported by {md_file.name}",
            )
        )
        imported.extend(_resolve_at_imports(candidate, agent, scope, layer_name, depth + 1))
    return imported


def _load_claude_settings(
    claude_home: Path,
    cwd: Path,
    git_root: Path | None,
) -> tuple[SettingsSource, ...]:
    sources: list[SettingsSource] = []

    user_settings = claude_home / "settings.json"
    if user_settings.is_file():
        sources.append(
            SettingsSource(
                agent=Agent.CLAUDE,
                scope=Scope.USER,
                format="json",
                output_path=user_settings,
                layer_name="user",
                source_path=user_settings,
                precedence_order=1,
                description="User settings.json",
            )
        )

    if git_root:
        for directory in paths_to_cwd(cwd, git_root):
            project_settings = directory / ".claude" / "settings.json"
            if project_settings.is_file():
                sources.append(
                    SettingsSource(
                        agent=Agent.CLAUDE,
                        scope=Scope.PROJECT,
                        format="json",
                        output_path=project_settings,
                        layer_name="project",
                        source_path=project_settings,
                        requires_trust=True,
                        precedence_order=2,
                        description=(
                            f"Project settings.json at {project_settings.relative_to(git_root)}"
                        ),
                    )
                )

            local_settings = directory / ".claude" / "settings.local.json"
            if local_settings.is_file():
                sources.append(
                    SettingsSource(
                        agent=Agent.CLAUDE,
                        scope=Scope.LOCAL,
                        format="json",
                        output_path=local_settings,
                        layer_name="local",
                        source_path=local_settings,
                        precedence_order=3,
                        description=(
                            f"Local settings.json at {local_settings.relative_to(git_root)}"
                        ),
                    )
                )

    return tuple(sources)


def _extract_claude_rules(rule_str: str, action: str, settings_path: Path) -> RulesSource | None:
    """Parse a single Claude permission rule string like 'Bash(npm run lint)'."""
    rule_str = rule_str.strip()
    tool_match = re.match(r"(\w+)\((.*)\)", rule_str)
    if not tool_match:
        return None

    tool_name = tool_match.group(1).lower()
    pattern = tool_match.group(2)

    return RulesSource(
        agent=Agent.CLAUDE,
        scope=Scope.USER,
        rule_type=tool_name,
        action=action,
        pattern=pattern,
        output_path=settings_path,
        layer_name="user",
        source_path=settings_path,
        description=f"{action.capitalize()} {tool_name}: {pattern}",
    )


def _extract_all_claude_rules(
    settings: dict[str, Any],
    settings_path: Path,
) -> tuple[RulesSource, ...]:
    sources: list[RulesSource] = []
    permissions = settings.get("permissions", {})

    for action_key in ["allow", "deny", "ask"]:
        action_map = {"allow": "allow", "deny": "deny", "ask": "ask"}
        rules_list = permissions.get(action_key, [])
        if not rules_list:
            continue

        for rule_item in rules_list:
            if isinstance(rule_item, str):
                rule_src = _extract_claude_rules(rule_item, action_map[action_key], settings_path)
                if rule_src:
                    sources.append(rule_src)
            elif isinstance(rule_item, dict):
                tool = rule_item.get("tool", "unknown")
                pattern = str(rule_item.get("pattern", rule_item.get("paths", "*")))
                sources.append(
                    RulesSource(
                        agent=Agent.CLAUDE,
                        scope=Scope.USER,
                        rule_type=tool,
                        action=action_map[action_key],
                        pattern=pattern,
                        output_path=settings_path,
                        layer_name="user",
                        source_path=settings_path,
                        description=f"{action_key.capitalize()} {tool}: {pattern}",
                    )
                )

    return tuple(sources)


def _load_codex_settings(
    codex_home: Path,
    cwd: Path,
    git_root: Path | None,
) -> tuple[SettingsSource, ...]:
    sources: list[SettingsSource] = []

    user_config = codex_home / "config.toml"
    if user_config.is_file():
        sources.append(
            SettingsSource(
                agent=Agent.CODEX,
                scope=Scope.USER,
                format="toml",
                output_path=user_config,
                layer_name="user",
                source_path=user_config,
                precedence_order=1,
                description="User config.toml",
            )
        )

    if git_root:
        for index, directory in enumerate(paths_to_cwd(cwd, git_root), start=2):
            project_config = directory / ".codex" / "config.toml"
            if project_config.is_file():
                sources.append(
                    SettingsSource(
                        agent=Agent.CODEX,
                        scope=Scope.PROJECT,
                        format="toml",
                        output_path=project_config,
                        layer_name="project",
                        source_path=project_config,
                        requires_trust=True,
                        precedence_order=index,
                        description=(
                            f"Project config.toml at {project_config.relative_to(git_root)}"
                        ),
                    )
                )

    return tuple(sources)


def _load_codex_rules(
    codex_home: Path,
    cwd: Path,
    git_root: Path | None,
) -> tuple[RulesSource, ...]:
    sources: list[RulesSource] = []

    user_rules_dir = codex_home / "rules"
    if user_rules_dir.is_dir():
        for rules_file in sorted(user_rules_dir.glob("*.rules")):
            sources.extend(
                _parse_codex_rules_file(
                    rules_file,
                    scope=Scope.USER,
                    git_root=git_root,
                )
            )

    if git_root:
        for directory in paths_to_cwd(cwd, git_root):
            project_rules_dir = directory / ".codex" / "rules"
            if project_rules_dir.is_dir():
                for rules_file in sorted(project_rules_dir.glob("*.rules")):
                    sources.extend(
                        _parse_codex_rules_file(
                            rules_file,
                            scope=Scope.PROJECT,
                            git_root=git_root,
                            requires_trust=True,
                        )
                    )

    return tuple(sources)


def _parse_codex_rules_file(
    rules_file: Path,
    scope: Scope,
    git_root: Path | None = None,
    requires_trust: bool = False,
) -> list[RulesSource]:
    """Parse a Codex .rules file and extract prefix_rule() calls."""
    content = rules_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(rules_file))
    sources: list[RulesSource] = []

    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Name) or call.func.id != "prefix_rule":
            continue

        rule_pattern, action = _parse_prefix_rule_call(call, rules_file)
        sources.append(
            RulesSource(
                agent=Agent.CODEX,
                scope=scope,
                rule_type="command_prefix",
                action=action,
                pattern=rule_pattern,
                output_path=rules_file,
                layer_name=scope.value,
                source_path=rules_file,
                requires_trust=requires_trust,
                description=f"Command rule: {rule_pattern}",
            )
        )

    return sources


def _parse_prefix_rule_call(call: ast.Call, rules_file: Path) -> tuple[str, str]:
    keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
    pattern_node = keywords.get("pattern")
    decision_node = keywords.get("decision")

    if pattern_node is None and call.args:
        pattern_node = call.args[0]
    if decision_node is None and len(call.args) > 1:
        decision_node = call.args[1]
    if pattern_node is None or decision_node is None:
        raise ValueError(f"prefix_rule requires pattern and decision: {rules_file}")

    pattern = ast.literal_eval(pattern_node)
    decision = ast.literal_eval(decision_node)
    if isinstance(pattern, list) and all(isinstance(part, str) for part in pattern):
        rule_pattern = " ".join(pattern)
    elif isinstance(pattern, str):
        rule_pattern = pattern
    else:
        raise ValueError(f"prefix_rule pattern must be a string or string list: {rules_file}")
    if not isinstance(decision, str):
        raise ValueError(f"prefix_rule decision must be a string: {rules_file}")
    return rule_pattern, decision
