from __future__ import annotations

import json
import os
from importlib.metadata import version
from textwrap import dedent

import pytest

from agent_db import cli


@pytest.mark.parametrize("flag", ("-v", "--version"))
def test_cli_version_uses_package_metadata(flag, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([flag])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"agent-db {version('agent-db')}\n"


def test_cli_refresh_uses_docs_refresh(monkeypatch) -> None:
    from tools.docs import refresh

    calls = []

    def fake_refresh(agent: str) -> int:
        calls.append(agent)
        return 17

    monkeypatch.setattr(refresh, "main", fake_refresh)

    assert cli.main(["--refresh"]) == 17
    assert cli.main(["-r"]) == 17
    assert cli.main(["--refresh", "--agent", "codex"]) == 17
    assert calls == ["all", "all", "codex"]


def test_docs_refresh_runs_only_selected_agent(monkeypatch) -> None:
    from tools.docs import refresh

    calls = []
    monkeypatch.setattr(refresh.claude, "refresh", lambda: calls.append("claude") or [])
    monkeypatch.setattr(refresh.codex, "refresh", lambda: calls.append("codex") or [])
    monkeypatch.setattr(refresh.agent_md, "refresh", lambda: calls.append("agents"))

    assert refresh.main("codex") == 0
    assert calls == ["codex"]


def test_cli_reference_root_prints_absolute_docs_path(capsys) -> None:
    assert cli.main(["--reference-root"]) == 0

    assert capsys.readouterr().out == f"{cli.reference_root()}\n"
    assert cli.reference_root().is_absolute()


def test_cli_help_lists_short_flags_first() -> None:
    help_text = cli.build_parser().format_help()

    assert "-m, --memory" in help_text
    assert "-a, --agent {claude,codex,all}" in help_text
    assert "-r, --refresh" in help_text
    assert "-v, --version" in help_text
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


def test_cli_memory_single_agent_claude_json(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.chdir(tmp_path)

    assert cli.main(["--memory", "-a", "claude", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert len(output["contexts"]) == 1
    assert output["contexts"][0]["agent"] == "claude"


def test_cli_memory_single_agent_codex_json(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.chdir(tmp_path)

    assert cli.main(["--memory", "-a", "codex", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert len(output["contexts"]) == 1
    assert output["contexts"][0]["agent"] == "codex"


def test_cli_refresh_memory_combination_rejected() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--refresh", "--memory"])

    assert exc_info.value.code == 2


def test_cli_json_without_memory_rejected() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--json"])

    assert exc_info.value.code == 2


def test_cli_agent_without_memory_rejected() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--agent", "claude"])

    assert exc_info.value.code == 2


def test_cli_sync_reports_failures_and_exits_nonzero(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    source = root / "src"
    (source / "my-skill").mkdir(parents=True)
    (source / "my-skill" / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
    (source / "other").mkdir(parents=True)
    (source / "other" / "SKILL.md").write_text("# Other\n", encoding="utf-8")
    (root / "agent-db.toml").write_text(
        '[skills]\nsource = "src"\ntargets = ["a", "b"]\n',
        encoding="utf-8",
    )

    blocked = root / "a" / "my-skill"
    blocked.mkdir(parents=True)
    os.chmod(blocked, 0o555)
    try:
        assert cli.main(["sync", "--root", str(root)]) == 1

        captured = capsys.readouterr()
        assert "failed to sync 1 file(s) to" in captured.err
        assert str(root / "a" / "my-skill" / "SKILL.md") in captured.err
        # The unaffected target still received every skill
        assert (root / "b" / "my-skill" / "SKILL.md").read_text() == "# My Skill\n"
        assert (root / "b" / "other" / "SKILL.md").read_text() == "# Other\n"
        assert str(root / "b" / "other" / "SKILL.md") in captured.out
    finally:
        os.chmod(blocked, 0o755)


def test_cli_sync_success_exits_zero(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    source = root / "src"
    (source / "my-skill").mkdir(parents=True)
    (source / "my-skill" / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
    (source / "other").mkdir(parents=True)
    (source / "other" / "SKILL.md").write_text("# Other\n", encoding="utf-8")
    (root / "agent-db.toml").write_text(
        '[skills]\nsource = "src"\ntargets = ["a", "b"]\n',
        encoding="utf-8",
    )

    assert cli.main(["sync", "--root", str(root)]) == 0
    assert capsys.readouterr().err == ""
    for target in ("a", "b"):
        assert (root / target / "other" / "SKILL.md").read_text() == "# Other\n"
        assert (root / target / "my-skill" / "SKILL.md").read_text() == "# My Skill\n"


def test_cli_sync_prints_pruned_paths(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    source = root / "src"
    (source / "my-skill").mkdir(parents=True)
    (source / "my-skill" / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
    (root / "agent-db.toml").write_text(
        '[skills]\nsource = "src"\ntargets = ["a"]\n',
        encoding="utf-8",
    )
    # Stale content inside an owned skill is pruned; its emptied dir collapses.
    stale_dir = root / "a" / "my-skill" / "old"
    stale_dir.mkdir(parents=True)
    stale_file = stale_dir / "notes.md"
    stale_file.write_text("# Old\n", encoding="utf-8")

    assert cli.main(["sync", "--root", str(root)]) == 0

    captured = capsys.readouterr()
    assert f"removed {stale_file}" in captured.out
    assert f"removed {stale_dir}" in captured.out
    assert not stale_dir.exists()
