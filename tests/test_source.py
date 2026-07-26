from __future__ import annotations

from textwrap import dedent

import pytest

from agent_db import claude, codex
from agent_db.source import (
    AgentSource,
    apply_settings_doc,
    assemble_sections,
    parse_settings,
)


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


def test_instruction_frontmatter_marks_claude_output_style(tmp_path) -> None:
    source_root = tmp_path / "source"
    (source_root / "dist" / "instructions").mkdir(parents=True)
    (source_root / "dist" / "instructions" / "communication.md").write_text(
        dedent(
            """\
            ---
            title: Communication
            claude_output_style: true
            ---

            # Communication

            style rules
            """
        ),
        encoding="utf-8",
    )

    source = AgentSource.from_root(source_root)
    sections = {section.key: section for section in assemble_sections(source)}

    assert sections["communication"].claude_output_style is True


def test_namespace_validation_rejects_any_unknown_top_level_key() -> None:
    with pytest.raises(ValueError, match="typo"):
        claude.claude_settings({"typo": "value"})

    with pytest.raises(ValueError, match="typo"):
        codex.render_config({"typo": "value"})


def test_parse_settings_rejects_non_mapping_yaml(tmp_path) -> None:
    settings_file = tmp_path / "bad.yaml"
    settings_file.write_text("just a string\n", encoding="utf-8")

    with pytest.raises(TypeError, match="settings must be a mapping"):
        parse_settings(settings_file)


def test_parse_settings_rejects_malformed_yaml(tmp_path) -> None:
    settings_file = tmp_path / "bad.yaml"
    settings_file.write_text("key: [unclosed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid YAML"):
        parse_settings(settings_file)


def test_apply_settings_doc_rejects_non_dict_append() -> None:
    target: dict = {}

    with pytest.raises(ValueError, match="append settings must be a mapping"):
        apply_settings_doc(target, {"append": "not a dict"})


def test_apply_settings_doc_rejects_non_dict_override() -> None:
    target: dict = {}

    with pytest.raises(ValueError, match="override settings must be a mapping"):
        apply_settings_doc(target, {"override": "not a dict"})


def test_from_root_rejects_nonexistent_path(tmp_path) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(NotADirectoryError):
        AgentSource.from_root(missing)


def test_from_root_rejects_empty_directory(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(FileNotFoundError, match="no source layers"):
        AgentSource.from_root(empty)
