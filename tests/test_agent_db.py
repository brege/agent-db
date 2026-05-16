from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from agent_db import claude, cli, codex
from agent_db.display import (
    MemoryContext,
    MemoryFile,
    MemoryPayload,
    format_loaded_context,
    loaded_context_data,
    loaded_context_model,
)
from agent_db.schema import (
    Agent,
    InstructionSource,
    LoadedContext,
    LoadTiming,
    RulesSource,
    Scope,
    SettingsSource,
    SourceType,
)
from agent_db.source import AgentSource, assemble_sections


def test_instructions_use_title_filename_h1_order_and_default_append(tmp_path) -> None:
    source_root = tmp_path / "source"
    (source_root / "dist" / "instructions").mkdir(parents=True)
    (source_root / "user" / "instructions").mkdir(parents=True)

    (source_root / "dist" / "instructions" / "docs.md").write_text(
        dedent(
            """\
            ---
            title: Documentation
            override: true
            ---

            # Documentation

            dist docs
            """
        ),
        encoding="utf-8",
    )
    (source_root / "user" / "instructions" / "docs.md").write_text(
        dedent(
            """\
            ---
            title: Documentation
            ---

            # Documentation

            user docs
            """
        ),
        encoding="utf-8",
    )
    (source_root / "user" / "instructions" / "special-case.md").write_text(
        "# Ignored H1\n\nbody\n",
        encoding="utf-8",
    )

    source = AgentSource.from_root(source_root)
    sections = {section.key: section for section in assemble_sections(source)}

    assert sections["documentation"].body.count("# Documentation") == 1
    assert "dist docs" in sections["documentation"].body
    assert "user docs" in sections["documentation"].body
    assert sections["special-case"].title == "Special Case"


def test_writes_claude_and_codex_globals(tmp_path) -> None:
    source_root = tmp_path / "source"
    (source_root / "dist" / "instructions").mkdir(parents=True)
    (source_root / "dist" / "settings").mkdir(parents=True)
    (source_root / "user" / "instructions").mkdir(parents=True)
    (source_root / "user" / "skills" / "comment-remover").mkdir(parents=True)

    (source_root / "dist" / "instructions" / "code.md").write_text(
        dedent(
            """\
            ---
            title: Code
            override: true
            ---

            # Code

            dist code
            """
        ),
        encoding="utf-8",
    )
    (source_root / "user" / "instructions" / "code.md").write_text(
        "# Code\n\nuser code\n",
        encoding="utf-8",
    )
    (source_root / "dist" / "settings.yaml").write_text(
        dedent(
            """\
            append:
              includeCoAuthoredBy: false
              model: haiku
            """
        ),
        encoding="utf-8",
    )
    (source_root / "dist" / "settings" / "commands.yaml").write_text(
        dedent(
            """\
            append:
              permissions:
                commands:
                  deny:
                    - "sudo *"
                    - "git add *"
            """
        ),
        encoding="utf-8",
    )
    (source_root / "dist" / "settings" / "paths.yaml").write_text(
        dedent(
            """\
            append:
              permissions:
                paths:
                  deny:
                    - path: "~/.ssh/**"
                      permissions: [read, write]
                  allow:
                    - path: "~/books/**"
                      permissions: [read, write]
            """
        ),
        encoding="utf-8",
    )
    (source_root / "user" / "skills" / "comment-remover" / "SKILL.md").write_text(
        "---\nname: comment-remover\ndescription: remove comments\n---\n",
        encoding="utf-8",
    )

    source = AgentSource.from_root(source_root)
    claude_home = tmp_path / "claude"
    codex_home = tmp_path / "codex"

    claude.write_global(source, claude_home)
    codex.write_global(source, codex_home)

    claude_md = (claude_home / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude_md.startswith("# CLAUDE.md\n\n## Code\n\n@rules/code.md\n")
    assert "## Permissions\n\n@rules/permissions.md" in claude_md
    assert "## Enforced Restrictions" not in claude_md
    assert (claude_home / "rules" / "code.md").read_text(encoding="utf-8").count("# Code") == 1
    permissions_md = (claude_home / "rules" / "permissions.md").read_text(encoding="utf-8")
    assert "## Enforced Restrictions" in permissions_md
    assert "- Never run 'git add' or any command matching it." in permissions_md
    assert "- Never read files matching ~/.ssh/**." in permissions_md
    claude_settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
    assert claude_settings["permissions"]["deny"] == [
        "Bash(sudo:*)",
        "Bash(git add:*)",
        "Read(~/.ssh/**)",
        "Edit(~/.ssh/**)",
    ]

    agents_md = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_md.startswith("# AGENTS.md\n\n## Code")
    assert agents_md.count("\n# ") == 0
    assert "user code" in agents_md
    assert "## Enforced Restrictions" in agents_md
    assert "- Never run 'git add' or any command matching it." in agents_md
    codex_config = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert 'default_permissions = "agent_db"' in codex_config
    assert "glob_scan_max_depth = 3" in (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '["sudo"]' in (codex_home / "rules" / "commands.rules").read_text(encoding="utf-8")
    assert '["git", "add"]' in (codex_home / "rules" / "commands.rules").read_text(encoding="utf-8")
    assert (claude_home / "skills" / "comment-remover" / "SKILL.md").is_file()
    assert (codex_home / "skills" / "comment-remover" / "SKILL.md").is_file()

    assert claude.write_global(source, claude_home) == []
    assert codex.write_global(source, codex_home) == []


def test_memory_output_lists_files_without_permission_rule_spam(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# test\n", encoding="utf-8")
    ctx = LoadedContext(
        agent=Agent.CLAUDE,
        cwd=tmp_path,
        project_root=tmp_path,
        sources=(
            InstructionSource(
                agent=Agent.CLAUDE,
                source_type=SourceType.MEMORY,
                scope=Scope.PROJECT,
                load_timing=LoadTiming.STARTUP,
                output_path=claude_md,
                layer_name="project",
                source_path=claude_md,
                path_globs=("src/**",),
                requires_trust=True,
            ),
        ),
        settings_sources=(
            SettingsSource(
                agent=Agent.CLAUDE,
                scope=Scope.LOCAL,
                format="json",
                output_path=settings,
                layer_name="local",
                source_path=settings,
            ),
        ),
        rules_sources=(
            RulesSource(
                agent=Agent.CLAUDE,
                scope=Scope.USER,
                rule_type="bash",
                action="deny",
                pattern="git add *",
                output_path=settings,
                layer_name="user",
                source_path=settings,
            ),
        ),
    )

    output = format_loaded_context(loaded_context_data(ctx))

    assert "Permission Rules" not in output
    assert "git add *" not in output
    assert "#" not in {line[:1] for line in output.splitlines()}
    assert "CLAUDE" in output
    assert f"root {tmp_path}" in output
    assert "startup" in output
    assert "config" in output
    assert "project" in output
    assert "memory" in output
    assert "settings" in output
    assert "./CLAUDE.md" in output
    assert "(paths: src/**)" in output
    assert "[!trust]" in output
    assert "local" in output
    assert "./settings.json" in output


def test_memory_json_output_uses_basic_data_structure(tmp_path, monkeypatch, capsys) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / ".git").mkdir()
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / "CLAUDE.md").write_text("# User\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert cli.main(["--memory", "--agent", "claude", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == ["contexts"]
    assert len(payload["contexts"]) == 1
    context = payload["contexts"][0]
    assert context["agent"] == "claude"
    assert context["cwd"] == str(work)
    assert context["project_root"] == str(work)
    assert context["files"] == [
        {
            "section": "startup",
            "scope": "user",
            "type": "memory",
            "path": str(claude_home / "CLAUDE.md"),
            "requires_trust": False,
            "path_globs": [],
        }
    ]
    assert context["config"] == []


def test_memory_models_preserve_json_shape(tmp_path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    settings = tmp_path / "settings.json"
    ctx = LoadedContext(
        agent=Agent.CLAUDE,
        cwd=tmp_path,
        project_root=tmp_path,
        sources=(
            InstructionSource(
                agent=Agent.CLAUDE,
                source_type=SourceType.MEMORY,
                scope=Scope.PROJECT,
                load_timing=LoadTiming.STARTUP,
                output_path=claude_md,
                layer_name="project",
                source_path=claude_md,
                path_globs=("src/**",),
            ),
        ),
        settings_sources=(
            SettingsSource(
                agent=Agent.CLAUDE,
                scope=Scope.LOCAL,
                format="json",
                output_path=settings,
                layer_name="local",
                source_path=settings,
            ),
        ),
    )

    payload = MemoryPayload(contexts=(loaded_context_model(ctx),))

    assert payload.model_dump(mode="json") == {
        "contexts": [
            {
                "agent": "claude",
                "cwd": str(tmp_path),
                "project_root": str(tmp_path),
                "files": [
                    {
                        "section": "startup",
                        "scope": "project",
                        "type": "memory",
                        "path": str(claude_md),
                        "requires_trust": False,
                        "path_globs": ["src/**"],
                    }
                ],
                "config": [
                    {
                        "scope": "local",
                        "format": "json",
                        "path": str(settings),
                        "requires_trust": False,
                    }
                ],
            }
        ]
    }


def test_memory_models_reject_unknown_fields(tmp_path) -> None:
    with pytest.raises(ValidationError):
        MemoryContext.model_validate(
            {
                "agent": "claude",
                "cwd": str(tmp_path),
                "project_root": str(tmp_path),
                "files": [],
                "config": [],
                "extra": True,
            }
        )


def test_memory_models_reject_invalid_enum_values(tmp_path) -> None:
    with pytest.raises(ValidationError):
        MemoryFile.model_validate(
            {
                "section": "never",
                "scope": "project",
                "type": "memory",
                "path": str(tmp_path / "CLAUDE.md"),
                "requires_trust": False,
                "path_globs": [],
            }
        )


def test_memory_text_output_uses_rich_without_rule_spam(tmp_path, monkeypatch, capsys) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / ".git").mkdir()
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / "CLAUDE.md").write_text("# User\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert cli.main(["--memory", "--agent", "claude"]) == 0

    output = capsys.readouterr().out
    assert "CLAUDE" in output
    assert "root" in output
    assert "startup" in output
    assert "user" in output
    assert "memory" in output
    assert "CLAUDE.md" in output
    assert "Permission Rules" not in output


def test_cli_refresh_uses_docs_refresh(monkeypatch) -> None:
    from tools.docs import refresh

    calls = []

    def fake_refresh() -> int:
        calls.append("refresh")
        return 17

    monkeypatch.setattr(refresh, "main", fake_refresh)

    assert cli.main(["--refresh"]) == 17
    assert cli.main(["-r"]) == 17
    assert calls == ["refresh", "refresh"]


def test_memory_output_shortens_home_paths() -> None:
    project = Path.home() / "code" / "project"
    output = format_loaded_context(
        {
            "agent": "codex",
            "cwd": str(project),
            "project_root": str(project),
            "files": [],
            "config": [],
        }
    )

    assert "~/code/project" in output
    assert str(Path.home()) not in output


def test_cli_build_uses_documented_home_environment(tmp_path, monkeypatch) -> None:
    defaults_root = tmp_path / "defaults"
    user_root = tmp_path / "user"
    (defaults_root / "instructions").mkdir(parents=True)
    (defaults_root / "settings").mkdir(parents=True)
    (user_root / "skills" / "comment-remover").mkdir(parents=True)
    (defaults_root / "instructions" / "code.md").write_text(
        "# Code\n\nrules\n",
        encoding="utf-8",
    )
    (defaults_root / "settings" / "commands.yaml").write_text(
        dedent(
            """\
            append:
              permissions:
                commands:
                  deny:
                    - "sudo *"
            """
        ),
        encoding="utf-8",
    )
    (defaults_root / "settings" / "paths.yaml").write_text(
        dedent(
            """\
            append:
              permissions:
                paths:
                  deny:
                    - path: "~/.ssh/**"
                      permissions: [read]
            """
        ),
        encoding="utf-8",
    )
    (user_root / "skills" / "comment-remover" / "SKILL.md").write_text(
        "---\nname: comment-remover\ndescription: remove comments\n---\n",
        encoding="utf-8",
    )

    home = tmp_path / "home"
    claude_home = tmp_path / "claude"
    codex_home = tmp_path / "codex"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_DB_DEFAULTS", str(defaults_root))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert cli.main(["--from", str(user_root)]) == 0

    assert (claude_home / "CLAUDE.md").is_file()
    assert (claude_home / "settings.json").is_file()
    assert (codex_home / "AGENTS.md").is_file()
    assert (codex_home / "config.toml").is_file()
    assert (codex_home / "skills" / "comment-remover" / "SKILL.md").is_file()


def test_agent_db_home_uses_platform_config_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_DB_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert cli.agent_db_home() == tmp_path / "agent-db"


def test_codex_config_layers_into_existing_toml() -> None:
    existing = dedent(
        """\
        model = "gpt-5.5"
        model_reasoning_effort = "xhigh"

        [projects."/example/project"]
        trust_level = "trusted"

        [tui]
        theme = "nord"
        """
    )
    generated = dedent(
        """\
        default_permissions = "agent_db"

        [permissions.agent_db.filesystem]
        glob_scan_max_depth = 3
        "/example/home/.ssh/**" = "none"
        """
    )

    layered = codex.layer_config(existing, generated)

    assert 'model = "gpt-5.5"' in layered
    assert '[projects."/example/project"]' in layered
    assert 'theme = "nord"' in layered
    assert "# agent-db begin" in layered
    assert 'default_permissions = "agent_db"' in layered
    assert "[permissions.agent_db.filesystem]" in layered


def test_codex_config_preserves_existing_default_permissions() -> None:
    existing = dedent(
        """\
        default_permissions = "workspace"
        model = "gpt-5.5"

        [permissions.workspace.filesystem]
        ":project_roots" = { "." = "write" }
        """
    )
    generated = dedent(
        """\
        default_permissions = "agent_db"

        [permissions.agent_db.filesystem]
        glob_scan_max_depth = 3
        "/example/home/.ssh/**" = "none"
        """
    )

    layered = codex.layer_config(existing, generated)

    assert layered.count("default_permissions") == 1
    assert 'default_permissions = "workspace"' in layered
    assert "[permissions.workspace.filesystem]" in layered
    assert "[permissions.agent_db.filesystem]" in layered


def test_codex_config_replaces_managed_block() -> None:
    existing = dedent(
        """\
        model = "gpt-5.5"

        # agent-db begin
        default_permissions = "agent_db"

        [permissions.agent_db.filesystem]
        "/old/**" = "none"
        # agent-db end

        [tui]
        theme = "nord"
        """
    )
    generated = dedent(
        """\
        default_permissions = "agent_db"

        [permissions.agent_db.filesystem]
        glob_scan_max_depth = 3
        "/new/**" = "none"
        """
    )

    layered = codex.layer_config(existing, generated)

    assert '"/old/**"' not in layered
    assert '"/new/**"' in layered
    assert "[tui]" in layered


def test_codex_config_write_backs_up_existing_file(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('model = "gpt-5.5"\n', encoding="utf-8")

    changed = codex.write_config(
        path,
        dedent(
            """\
            default_permissions = "agent_db"

            [permissions.agent_db.filesystem]
            glob_scan_max_depth = 3
            "/example/home/.ssh/**" = "none"
            """
        ),
    )

    assert changed is True
    assert 'model = "gpt-5.5"' in path.read_text(encoding="utf-8")
    backups = list(tmp_path.glob("config.toml.agent-db-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == 'model = "gpt-5.5"\n'


def test_codex_path_normalizes_terminal_recursive_glob_to_root() -> None:
    assert codex.codex_path("~/code/**") == str(Path.home() / "code")
    assert codex.codex_path("/tmp/project/**") == "/tmp/project"


def test_codex_skips_heredoc_patterns_that_are_not_argv_prefixes() -> None:
    rules = codex.render_rules(
        {
            "commands": {
                "deny": [
                    "python << *",
                    "sudo *",
                ],
            },
        }
    )

    assert 'pattern = ["python", "<<"]' not in rules
    assert "Codex rules match argv prefixes" in rules
    assert 'pattern = ["sudo"]' in rules
