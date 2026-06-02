from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_db import cli
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
    assert "CLAUDE.md" in output
    assert "(paths: src/**)" in output
    assert "[!trust]" in output
    assert "local" in output
    assert "settings.json" in output


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
