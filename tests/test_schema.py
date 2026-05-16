from __future__ import annotations

from pathlib import Path

from agent_db.schema import (
    Agent,
    LoadTiming,
    Scope,
    SourceType,
    claude_load_order,
    codex_load_order,
)


def test_claude_user_only(fixture_paths):
    paths = fixture_paths("claude", "user-only")
    cwd = paths.get("cwd") or paths["home"]
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    user_memory = [
        s for s in ctx.sources if s.scope == Scope.USER and s.source_type == SourceType.MEMORY
    ]
    assert len(user_memory) >= 1
    assert any(s.output_path.name == "CLAUDE.md" for s in user_memory)

    project_sources = [s for s in ctx.sources if s.scope == Scope.PROJECT]
    assert len(project_sources) == 0


def test_claude_layered_hierarchy(fixture_paths):
    paths = fixture_paths("claude", "layered-hierarchy")
    cwd = paths["repo"] / "src" if "repo" in paths else paths["home"]
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    memory_sources = [
        s for s in ctx.sources if s.source_type == SourceType.MEMORY and s.scope == Scope.PROJECT
    ]

    output_paths = [s.output_path for s in memory_sources]
    assert any("CLAUDE.md" in str(p) for p in output_paths)

    assert any("src/CLAUDE.md" in str(p) for p in output_paths)


def test_claude_local_md(fixture_paths):
    paths = fixture_paths("claude", "layered-hierarchy")
    cwd = paths.get("cwd", paths["home"])
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    local_sources = [s for s in ctx.sources if s.scope == Scope.LOCAL]
    assert len(local_sources) >= 1
    assert any("CLAUDE.local.md" in str(s.output_path) for s in local_sources)


def test_claude_local_md_resolves_imports(tmp_path):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    claude_home = home / ".claude"
    claude_home.mkdir(parents=True)
    repo.mkdir()
    (repo / ".git").mkdir()

    (claude_home / "CLAUDE.md").write_text("# User\n", encoding="utf-8")
    (repo / "CLAUDE.local.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("@README.md\n", encoding="utf-8")
    (repo / "README.md").write_text("# Project\n", encoding="utf-8")

    ctx = claude_load_order(repo, claude_home=claude_home)

    imported = [
        source.output_path.relative_to(repo).as_posix()
        for source in ctx.sources
        if source.scope == Scope.LOCAL and source.source_type == SourceType.RULES
    ]
    assert imported == ["AGENTS.md", "README.md"]


def test_claude_path_scoped_rules(fixture_paths):
    paths = fixture_paths("claude", "path-scoped-rules")
    cwd = paths.get("cwd", paths["home"])
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    path_scoped = [s for s in ctx.sources if s.load_timing == LoadTiming.ON_READ_MATCH]
    assert len(path_scoped) >= 2

    assert any(s.path_globs for s in path_scoped)

    startup = [
        s
        for s in ctx.sources
        if s.load_timing == LoadTiming.STARTUP and s.source_type == SourceType.RULES
    ]
    assert len(startup) >= 1


def test_claude_user_scope_before_project(fixture_paths):
    paths = fixture_paths("claude", "layered-hierarchy")
    cwd = paths.get("cwd", paths["home"])
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    scopes = [s.scope for s in ctx.sources if s.source_type == SourceType.MEMORY]

    if Scope.USER in scopes and Scope.PROJECT in scopes:
        user_idx = scopes.index(Scope.USER)
        project_idx = scopes.index(Scope.PROJECT)
        assert user_idx < project_idx


def test_claude_with_imports(fixture_paths):
    paths = fixture_paths("claude", "with-imports")
    cwd = paths.get("cwd", paths["home"])
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    rules = [s for s in ctx.sources if s.source_type == SourceType.RULES]
    assert len(rules) >= 2


def test_claude_settings_json(fixture_paths):
    paths = fixture_paths("claude", "settings-json")
    cwd = paths.get("cwd", paths["home"])
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    assert len(ctx.settings_sources) >= 1
    assert any(s.format == "json" for s in ctx.settings_sources)
    assert any(s.scope == Scope.USER for s in ctx.settings_sources)
    assert any(s.scope == Scope.LOCAL for s in ctx.settings_sources)
    assert any(s.output_path.name == "settings.local.json" for s in ctx.settings_sources)


def test_claude_rules_from_settings(fixture_paths):
    paths = fixture_paths("claude", "settings-json")
    cwd = paths.get("cwd", paths["home"])
    ctx = claude_load_order(cwd, claude_home=paths["home"] / ".claude")

    assert len(ctx.rules_sources) > 0

    actions = {s.action for s in ctx.rules_sources}
    assert "allow" in actions or "deny" in actions
    assert any(s.scope == Scope.LOCAL and s.pattern == "git add *" for s in ctx.rules_sources)


def test_codex_user_agents_md(fixture_paths):
    paths = fixture_paths("codex", "user-only")
    cwd = paths.get("cwd", paths["home"])
    ctx = codex_load_order(
        cwd,
        codex_home=paths["home"] / ".codex",
    )

    user_memory = [
        s for s in ctx.sources if s.scope == Scope.USER and s.source_type == SourceType.MEMORY
    ]
    assert len(user_memory) >= 1
    assert any(s.output_path.name == "AGENTS.md" for s in user_memory)


def test_codex_prefers_override_md(fixture_paths):
    paths = fixture_paths("codex", "override-precedence")
    cwd = paths.get("cwd", paths["home"])
    ctx = codex_load_order(
        cwd,
        codex_home=paths["home"] / ".codex",
    )

    user_sources = [s for s in ctx.sources if s.scope == Scope.USER]
    override_sources = [s for s in user_sources if "override" in str(s.output_path)]
    assert len(override_sources) == 1

    regular_sources = [s for s in user_sources if s.output_path.name == "AGENTS.md"]
    assert len(regular_sources) == 0


def test_codex_layered_agents_md(fixture_paths):
    paths = fixture_paths("codex", "layered-hierarchy")
    cwd = paths.get("cwd", paths["repo"])
    ctx = codex_load_order(
        cwd,
        codex_home=paths["home"] / ".codex",
    )

    project_sources = [
        s for s in ctx.sources if s.scope == Scope.PROJECT and s.source_type == SourceType.MEMORY
    ]
    paths_found = [s.output_path.relative_to(paths["repo"]).as_posix() for s in project_sources]
    assert paths_found == ["AGENTS.md", "src/AGENTS.md"]


def test_codex_config_toml(fixture_paths):
    paths = fixture_paths("codex", "config-toml")
    cwd = paths.get("cwd", paths["home"])
    ctx = codex_load_order(
        cwd,
        codex_home=paths["home"] / ".codex",
    )

    assert len(ctx.settings_sources) >= 1
    assert any(s.format == "toml" for s in ctx.settings_sources)
    assert any(s.scope == Scope.USER for s in ctx.settings_sources)
    project_configs = [
        s.source_path.relative_to(paths["repo"]).as_posix()
        for s in ctx.settings_sources
        if s.scope == Scope.PROJECT
    ]
    assert project_configs == [
        ".codex/config.toml",
        "src/.codex/config.toml",
    ]


def test_codex_rules_from_rules_file(fixture_paths):
    paths = fixture_paths("codex", "with-rules")
    cwd = paths.get("cwd", paths["home"])
    ctx = codex_load_order(
        cwd,
        codex_home=paths["home"] / ".codex",
    )

    rules = [s for s in ctx.rules_sources if s.rule_type == "command_prefix"]
    assert len(rules) >= 1


def test_codex_rules_parse_reordered_starlark_fields(tmp_path):
    from agent_db.schema import _parse_codex_rules_file

    rules_file = tmp_path / "commands.rules"
    rules_file.write_text(
        'prefix_rule(decision = "forbidden", reason = "test", pattern = ["git", "add"])\n',
        encoding="utf-8",
    )

    rules = _parse_codex_rules_file(rules_file, scope=Scope.PROJECT)

    assert len(rules) == 1
    assert rules[0].pattern == "git add"
    assert rules[0].action == "forbidden"


def test_git_worktree_with_dot_git_file(fixture_paths):
    from agent_db.schema import find_git_root

    paths = fixture_paths("git", "worktree")
    git_root = find_git_root(paths["repo"])

    assert git_root == paths["repo"]


def test_git_regular_with_dot_git_dir(fixture_paths):
    from agent_db.schema import find_git_root

    paths = fixture_paths("git", "regular")
    git_root = find_git_root(paths["repo"])

    assert git_root == paths["repo"]


def test_additional_scope_no_keyerror():
    from agent_db.schema import InstructionSource

    source = InstructionSource(
        agent=Agent.CLAUDE,
        source_type=SourceType.MEMORY,
        scope=Scope.ADDITIONAL,
        load_timing=LoadTiming.STARTUP,
        output_path=Path("/test"),
        layer_name="test",
        source_path=Path("/test"),
        path_globs=None,
    )

    key = source.load_order_key
    assert key is not None
    assert isinstance(key, tuple)


def test_startup_on_demand_on_read_match_separation(tmp_path):
    user_home = tmp_path / "home"
    user_home.mkdir()
    (user_home / ".claude").mkdir()
    (user_home / ".claude" / "CLAUDE.md").write_text("# test\n", encoding="utf-8")
    (user_home / ".claude" / "skills").mkdir()

    ctx = claude_load_order(user_home, claude_home=user_home / ".claude")

    startup = ctx.startup_sources

    startup_timings = {s.load_timing for s in startup}
    assert LoadTiming.ON_DEMAND not in startup_timings
    assert LoadTiming.ON_READ_MATCH not in startup_timings
