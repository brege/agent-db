from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from agent_db import codex

CODEX_PATH_PERMISSIONS = {
    "paths": {
        "allow": [
            {
                "path": "~/books/**",
                "permissions": ["read", "write"],
            }
        ],
        "deny": [
            {
                "path": "~/.ssh/**",
                "permissions": ["read"],
            }
        ],
    }
}


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


def test_codex_config_is_advisory_by_default() -> None:
    generated = codex.render_config(
        {
            "permissions": CODEX_PATH_PERMISSIONS,
        }
    )

    assert generated == ""


def test_codex_config_rejects_top_level_agent_keys() -> None:
    with pytest.raises(ValueError, match="model"):
        codex.render_config({"model": "gpt-5.5"})


def test_codex_config_replaces_existing_model_keys_when_managed() -> None:
    existing = dedent(
        """\
        model = "gpt-5.3-codex"
        model_reasoning_effort = "medium"

        [sandbox_workspace_write]
        network_access = true
        """
    )
    generated = codex.render_config(
        {
            "codex": {
                "model": "gpt-5.5",
                "model_reasoning_effort": "xhigh",
            }
        }
    )

    layered = codex.layer_config(existing, generated)

    assert layered.count("model = ") == 1
    assert layered.count("model_reasoning_effort = ") == 1
    assert 'model = "gpt-5.5"' in layered
    assert 'model_reasoning_effort = "xhigh"' in layered
    assert 'default_permissions = "agent_db"' not in layered
    assert "gpt-5.3-codex" not in layered
    assert "[sandbox_workspace_write]" in layered


def test_codex_config_enforce_profile_is_complete() -> None:
    generated = codex.render_config(
        {
            "codex": {
                "permissions_profile": "enforce",
                "network": {
                    "enabled": True,
                    "mode": "limited",
                },
            },
            "permissions": CODEX_PATH_PERMISSIONS,
        }
    )

    assert 'default_permissions = "agent_db"' in generated
    assert "[permissions.agent_db.filesystem]" in generated
    assert '":minimal" = "read"' in generated
    assert '":project_roots" = { "." = "write" }' in generated
    assert f'{codex.toml_string(str(Path.home() / "books"))} = "write"' in generated
    assert f'{codex.toml_string(str(Path.home() / ".ssh"))} = "none"' in generated
    assert "[permissions.agent_db.network]" in generated
    assert "enabled = true" in generated
    assert 'mode = "limited"' in generated


def test_codex_config_enforce_network_keeps_filesystem_baseline() -> None:
    generated = codex.render_config(
        {
            "codex": {
                "permissions_profile": "enforce",
                "network": {
                    "enabled": True,
                },
            },
        }
    )

    assert 'default_permissions = "agent_db"' in generated
    assert "[permissions.agent_db.filesystem]" in generated
    assert '":minimal" = "read"' in generated
    assert '":project_roots" = { "." = "write" }' in generated
    assert "[permissions.agent_db.network]" in generated
    assert "enabled = true" in generated


@pytest.mark.parametrize(
    ("codex_config", "message"),
    [
        (
            {
                "network": {
                    "enabled": True,
                },
            },
            "permissions_profile",
        ),
        (
            {
                "permissions_profile": "enforce",
                "network": "enabled",
            },
            "codex.network",
        ),
        (
            {
                "permissions_profile": "enforce",
                "network": {
                    "enabled": "true",
                },
            },
            "codex.network.enabled",
        ),
        (
            {
                "permissions_profile": "enforce",
                "network": {
                    "mode": True,
                },
            },
            "codex.network.mode",
        ),
    ],
)
def test_codex_network_validation(codex_config, message) -> None:
    with pytest.raises(ValueError, match=message):
        codex.render_config(
            {
                "codex": codex_config,
            }
        )


def test_codex_config_enforce_rejects_existing_default_permissions() -> None:
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

    with pytest.raises(ValueError, match="default_permissions"):
        codex.layer_config(existing, generated)


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


def test_codex_config_removes_managed_block_when_empty() -> None:
    existing = dedent(
        """\
        model = "gpt-5.5"

        # agent-db begin
        default_permissions = "agent_db"

        [permissions.agent_db.filesystem]
        "/old/**" = "none"
        # agent-db end

        [sandbox_workspace_write]
        network_access = true
        """
    )

    layered = codex.layer_config(existing, "")

    assert "# agent-db begin" not in layered
    assert 'default_permissions = "agent_db"' not in layered
    assert "[permissions.agent_db.filesystem]" not in layered
    assert 'model = "gpt-5.5"' in layered
    assert "[sandbox_workspace_write]" in layered
    assert "network_access = true" in layered


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
    rules, skipped = codex.render_rules(
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
    assert skipped == ["python << *"]


def test_unknown_codex_keys_survive_passthrough() -> None:
    generated = codex.render_config(
        {
            "codex": {
                "model": "gpt-5.5",
                "model_reasoning_effort": "xhigh",
                "sandbox_mode": "workspace-write",
                "check_for_update_on_startup": False,
                "sandbox_workspace_write": {
                    "network_access": True,
                    "writable_roots": ["/home/user/code"],
                },
            },
        }
    )

    assert 'model = "gpt-5.5"' in generated
    assert 'model_reasoning_effort = "xhigh"' in generated
    assert 'sandbox_mode = "workspace-write"' in generated
    assert "check_for_update_on_startup = false" in generated
    assert "[sandbox_workspace_write]" in generated
    assert "network_access = true" in generated
    assert 'writable_roots = ["/home/user/code"]' in generated


def test_codex_passthrough_emits_array_of_tables() -> None:
    generated = codex.render_config(
        {
            "codex": {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "check-policy.py",
                                    "timeout": 30,
                                },
                            ],
                        },
                    ],
                    "PostToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "review.py",
                                },
                            ],
                        },
                    ],
                },
            },
        }
    )

    assert "[[hooks.PreToolUse]]" in generated
    assert 'matcher = "^Bash$"' in generated
    assert "[[hooks.PreToolUse.hooks]]" in generated
    assert 'type = "command"' in generated
    assert 'command = "check-policy.py"' in generated
    assert "timeout = 30" in generated
    assert "[[hooks.PostToolUse]]" in generated
    assert "[[hooks.PostToolUse.hooks]]" in generated
    assert 'command = "review.py"' in generated


def test_codex_enforce_rejects_sandbox_era_keys() -> None:
    with pytest.raises(ValueError, match="sandbox_mode"):
        codex.render_config(
            {
                "codex": {
                    "model": "gpt-5.5",
                    "sandbox_mode": "workspace-write",
                    "permissions_profile": "enforce",
                    "network": {"enabled": False},
                },
                "permissions": CODEX_PATH_PERMISSIONS,
            }
        )

    with pytest.raises(ValueError, match="sandbox_workspace_write"):
        codex.render_config(
            {
                "codex": {
                    "permissions_profile": "enforce",
                    "sandbox_workspace_write": {"writable_roots": ["/tmp"]},
                },
            }
        )


def test_codex_enforce_without_sandbox_keys_emits_permissions() -> None:
    generated = codex.render_config(
        {
            "codex": {
                "model": "gpt-5.5",
                "permissions_profile": "enforce",
                "network": {"enabled": False},
            },
            "permissions": CODEX_PATH_PERMISSIONS,
        }
    )

    assert 'model = "gpt-5.5"' in generated
    assert "sandbox_mode" not in generated
    assert 'default_permissions = "agent_db"' in generated
    assert "[permissions.agent_db.filesystem]" in generated
    assert "[permissions.agent_db.network]" in generated


def test_codex_layering_strips_existing_tables_matching_generated() -> None:
    existing = dedent(
        """\
        model = "gpt-5.5"
        check_for_update_on_startup = false

        [sandbox_workspace_write]
        network_access = true
        writable_roots = ["/home/user/code"]
        """
    )
    generated = dedent(
        """\
        model = "o3"
        check_for_update_on_startup = true

        [sandbox_workspace_write]
        network_access = false
        writable_roots = ["/tmp"]
        """
    )

    layered = codex.layer_config(existing, generated)

    assert layered.count("[sandbox_workspace_write]") == 1
    assert 'model = "gpt-5.5"' not in layered
    assert 'model = "o3"' in layered


def test_codex_layering_preserves_unrelated_tables() -> None:
    existing = dedent(
        """\
        model = "gpt-5.5"

        [profiles.custom]
        some_key = "value"
        """
    )
    generated = dedent(
        """\
        model = "o3"

        [sandbox_workspace_write]
        network_access = false
        """
    )

    layered = codex.layer_config(existing, generated)

    assert "[profiles.custom]" in layered
    assert 'some_key = "value"' in layered
    assert "[sandbox_workspace_write]" in layered
    assert layered.count("[sandbox_workspace_write]") == 1


def test_codex_advisory_allows_sandbox_keys() -> None:
    generated = codex.render_config(
        {
            "codex": {
                "model": "gpt-5.5",
                "sandbox_mode": "workspace-write",
                "sandbox_workspace_write": {
                    "network_access": True,
                    "writable_roots": ["/home/user/code"],
                },
            },
        }
    )

    assert 'sandbox_mode = "workspace-write"' in generated
    assert "[sandbox_workspace_write]" in generated
    assert "default_permissions" not in generated


def test_render_agent_toml_produces_valid_structure() -> None:
    result = codex.render_agent_toml("reviewer", "# Review\n\nCheck style.\n")

    assert result.startswith('name = "reviewer"')
    assert 'instructions = """' in result
    assert "# Review" in result
    assert "Check style." in result
    assert result.endswith('"""\n')


def test_write_agents_creates_toml_from_markdown(tmp_path) -> None:
    from agent_db.source import AssetDir

    agent_dir = tmp_path / "source" / "agents" / "helper"
    agent_dir.mkdir(parents=True)
    (agent_dir / "helper.md").write_text("# Helper\n\nDo helpful things.\n", encoding="utf-8")

    agents = (AssetDir(name="helper", path=agent_dir),)
    target_root = tmp_path / "codex" / "agents"

    written = codex.write_agents(agents, target_root)

    assert len(written) == 1
    assert written[0].name == "helper.toml"
    content = written[0].read_text(encoding="utf-8")
    assert 'name = "helper"' in content
    assert "# Helper" in content
    assert "Do helpful things." in content
