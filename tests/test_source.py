from __future__ import annotations

from textwrap import dedent

import pytest

from agent_db import claude, codex
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


def test_namespace_validation_rejects_any_unknown_top_level_key() -> None:
    with pytest.raises(ValueError, match="typo"):
        claude.claude_settings({"typo": "value"})

    with pytest.raises(ValueError, match="typo"):
        codex.render_config({"typo": "value"})
