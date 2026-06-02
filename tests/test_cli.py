from __future__ import annotations

from textwrap import dedent

from agent_db import cli


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


def test_cli_reference_root_prints_absolute_docs_path(capsys) -> None:
    assert cli.main(["--reference-root"]) == 0

    assert capsys.readouterr().out == f"{cli.reference_root()}\n"
    assert cli.reference_root().is_absolute()


def test_cli_help_lists_short_flags_first() -> None:
    help_text = cli.build_parser().format_help()

    assert "-m, --memory" in help_text
    assert "-a, --agent {claude,codex,all}" in help_text
    assert "-r, --refresh" in help_text
    assert "--reference-root" in help_text
    assert "--memory, -m" not in help_text
    assert "--agent, -a" not in help_text
    assert "--refresh, -r" not in help_text


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
    monkeypatch.setenv("AGENT_DB_HOME", str(user_root))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert cli.main([]) == 0

    assert (claude_home / "CLAUDE.md").is_file()
    assert (claude_home / "settings.json").is_file()
    assert (codex_home / "AGENTS.md").is_file()
    assert not (codex_home / "config.toml").exists()
    assert (codex_home / "skills" / "comment-remover" / "SKILL.md").is_file()


def test_agent_db_home_uses_platform_config_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_DB_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert cli.agent_db_home() == tmp_path / "agent-db"
