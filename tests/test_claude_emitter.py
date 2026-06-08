from __future__ import annotations

import pytest

from agent_db import claude, cli
from agent_db.source import AgentSource, merged_settings


def test_claude_settings_use_only_claude_namespace() -> None:
    rendered = claude.claude_settings(
        {
            "claude": {
                "model": "claude-opus-4-5-20251101",
                "alwaysThinkingEnabled": True,
            },
            "codex": {
                "permissions_profile": "enforce",
            },
            "permissions": {
                "commands": {
                    "deny": ["sudo *"],
                },
            },
        }
    )

    assert rendered["model"] == "claude-opus-4-5-20251101"
    assert rendered["alwaysThinkingEnabled"] is True
    assert rendered["permissions"]["deny"] == ["Bash(sudo:*)"]
    assert "codex" not in rendered
    assert "claude" not in rendered


def test_default_claude_settings_enable_strict_sandbox(tmp_path) -> None:
    user_root = tmp_path / "user"
    user_root.mkdir()

    source = AgentSource.from_roots(cli.defaults_root(), user_root)
    rendered = claude.claude_settings(merged_settings(source))

    assert rendered["sandbox"] == {
        "enabled": True,
        "failIfUnavailable": True,
        "autoAllowBashIfSandboxed": True,
        "allowUnsandboxedCommands": False,
    }


def test_claude_settings_reject_top_level_agent_keys() -> None:
    with pytest.raises(ValueError, match="model"):
        claude.claude_settings({"model": "haiku"})

    with pytest.raises(ValueError, match="sandbox"):
        claude.claude_settings({"sandbox": {"enabled": True}})


def test_claude_settings_layer_preserves_unmanaged_existing_keys() -> None:
    layered = claude.layer_settings(
        {
            "theme": "dark",
            "codex": {
                "permissions_profile": "enforce",
            },
            "permissions": {
                "allow": ["Bash(npm:*)"],
            },
        },
        {
            "model": "sonnet",
            "permissions": {
                "deny": ["Bash(sudo:*)"],
            },
        },
    )

    assert layered["theme"] == "dark"
    assert layered["model"] == "sonnet"
    assert "allow" not in layered["permissions"]
    assert layered["permissions"]["deny"] == ["Bash(sudo:*)"]
    assert "codex" not in layered


def test_claude_settings_layer_removes_stale_permissions_when_unmanaged() -> None:
    layered = claude.layer_settings(
        {
            "theme": "dark",
            "permissions": {
                "deny": ["Bash(old:*)"],
            },
        },
        {
            "model": "sonnet",
        },
    )

    assert layered == {
        "theme": "dark",
        "model": "sonnet",
    }


def test_unknown_claude_keys_survive_passthrough() -> None:
    rendered = claude.claude_settings(
        {
            "claude": {
                "model": "haiku",
                "futureSettingBool": True,
                "futureSettingString": "value",
                "futureNested": {"deep": "config"},
            },
        }
    )

    assert rendered["model"] == "haiku"
    assert rendered["futureSettingBool"] is True
    assert rendered["futureSettingString"] == "value"
    assert rendered["futureNested"] == {"deep": "config"}


def test_explicit_claude_output_style_wins_over_generated_default() -> None:
    rendered = claude.claude_settings(
        {
            "claude": {
                "outputStyle": "Custom Style",
            },
        },
        output_style="Agent DB",
    )

    assert rendered["outputStyle"] == "Custom Style"
