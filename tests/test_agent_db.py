from __future__ import annotations

import json
from textwrap import dedent

from agent_db import claude, cli, codex
from agent_db.source import AgentSource, assemble_sections


def test_partials_use_title_filename_h1_order_and_default_append(tmp_path) -> None:
    source_root = tmp_path / "source"
    (source_root / "dist" / "partials").mkdir(parents=True)
    (source_root / "user" / "partials").mkdir(parents=True)

    (source_root / "dist" / "partials" / "docs.md").write_text(
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
    (source_root / "user" / "partials" / "docs.md").write_text(
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
    (source_root / "user" / "partials" / "special-case.md").write_text(
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
    (source_root / "dist" / "partials").mkdir(parents=True)
    (source_root / "dist" / "settings").mkdir(parents=True)
    (source_root / "user" / "partials").mkdir(parents=True)
    (source_root / "user" / "skills" / "comment-remover").mkdir(parents=True)

    (source_root / "dist" / "partials" / "code.md").write_text(
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
    (source_root / "user" / "partials" / "code.md").write_text(
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
    agents_home = tmp_path / "agents"

    claude.write_global(source, claude_home)
    codex.write_global(source, codex_home, agents_home)

    assert (claude_home / "CLAUDE.md").read_text(encoding="utf-8") == (
        "# CLAUDE.md\n\n## Code\n\n@rules/code.md\n"
    )
    assert (claude_home / "rules" / "code.md").read_text(encoding="utf-8").count("# Code") == 1
    claude_settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
    assert claude_settings["permissions"]["deny"] == [
        "Bash(sudo:*)",
        "Read(~/.ssh/**)",
        "Edit(~/.ssh/**)",
    ]

    agents_md = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_md.startswith("# AGENTS.md\n\n## Code")
    assert agents_md.count("\n# ") == 0
    assert "user code" in agents_md
    assert 'default_permissions = "agent_db"' in (codex_home / "config.toml").read_text(encoding="utf-8")
    assert "glob_scan_max_depth = 3" in (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '["sudo"]' in (codex_home / "rules" / "commands.rules").read_text(encoding="utf-8")
    assert (claude_home / "skills" / "comment-remover" / "SKILL.md").is_file()
    assert (agents_home / "skills" / "comment-remover" / "SKILL.md").is_file()

    assert claude.write_global(source, claude_home) == []
    assert codex.write_global(source, codex_home, agents_home) == []


def test_cli_build_uses_documented_home_environment(tmp_path, monkeypatch) -> None:
    defaults_root = tmp_path / "defaults"
    user_root = tmp_path / "user"
    (defaults_root / "partials").mkdir(parents=True)
    (defaults_root / "settings").mkdir(parents=True)
    (user_root / "skills" / "comment-remover").mkdir(parents=True)
    (defaults_root / "partials" / "code.md").write_text(
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
    assert (home / ".agents" / "skills" / "comment-remover" / "SKILL.md").is_file()


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
    assert '[tui]' in layered


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
