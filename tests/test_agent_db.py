from __future__ import annotations

import json
from textwrap import dedent

from agent_db import claude, codex
from agent_db.source import AgentSource


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
              claude:
                includeCoAuthoredBy: false
                model: haiku
              codex:
                permissions_profile: advisory
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
    assert claude_settings["model"] == "haiku"
    assert "codex" not in claude_settings
    assert "claude" not in claude_settings

    agents_md = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_md.startswith("# AGENTS.md\n\n## Code")
    assert agents_md.count("\n# ") == 0
    assert "user code" in agents_md
    assert "## Enforced Restrictions" in agents_md
    assert "- Never run 'git add' or any command matching it." in agents_md
    assert not (codex_home / "config.toml").exists()
    assert '["sudo"]' in (codex_home / "rules" / "commands.rules").read_text(encoding="utf-8")
    assert '["git", "add"]' in (codex_home / "rules" / "commands.rules").read_text(encoding="utf-8")
    assert (claude_home / "skills" / "comment-remover" / "SKILL.md").is_file()
    assert (codex_home / "skills" / "comment-remover" / "SKILL.md").is_file()

    assert claude.write_global(source, claude_home) == []
    assert codex.write_global(source, codex_home) == []
