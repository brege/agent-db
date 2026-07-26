from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_db.project import ProjectConfig, SkillsConfig, load_config, sync_skills


def _write_toml(root: Path, content: str) -> None:
    (root / "agent-db.toml").write_text(content, encoding="utf-8")


def _make_skill(source: Path, name: str, body: str = "# Skill\n") -> None:
    skill_dir = source / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")


class TestLoadConfig:
    def test_missing_toml(self, tmp_path: Path) -> None:
        config = load_config(tmp_path)
        assert config.root == tmp_path
        assert config.skills is None

    def test_no_skills_table(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[other]\nkey = 1\n")
        config = load_config(tmp_path)
        assert config.skills is None

    def test_valid(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            '[skills]\nsource = "_meta/skills"\ntargets = [".claude/skills", ".agents/skills"]\n',
        )
        config = load_config(tmp_path)
        assert config.skills is not None
        assert config.skills.source == tmp_path / "_meta/skills"
        assert config.skills.targets == (tmp_path / ".claude/skills", tmp_path / ".agents/skills")

    def test_missing_source(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, '[skills]\ntargets = [".claude/skills"]\n')
        with pytest.raises(ValueError, match="skills.source"):
            load_config(tmp_path)

    def test_missing_targets(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, '[skills]\nsource = "src"\n')
        with pytest.raises(ValueError, match="skills.targets"):
            load_config(tmp_path)

    def test_empty_targets(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, '[skills]\nsource = "src"\ntargets = []\n')
        with pytest.raises(ValueError, match="skills.targets"):
            load_config(tmp_path)


class TestSyncSkills:
    def test_no_config(self, tmp_path: Path) -> None:
        config = ProjectConfig(root=tmp_path, skills=None)
        result = sync_skills(config)
        assert result.written == []
        assert result.failures == []

    def test_source_missing(self, tmp_path: Path) -> None:
        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=tmp_path / "missing", targets=(tmp_path / "out",)),
        )
        with pytest.raises(FileNotFoundError):
            sync_skills(config)

    def test_copies_to_all_targets(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "my-skill", "# My Skill\n")

        target_a = tmp_path / "a"
        target_b = tmp_path / "b"
        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=source, targets=(target_a, target_b)),
        )
        result = sync_skills(config)
        assert len(result.written) == 2
        assert result.failures == []
        assert (target_a / "my-skill" / "SKILL.md").read_text() == "# My Skill\n"
        assert (target_b / "my-skill" / "SKILL.md").read_text() == "# My Skill\n"

    def test_idempotent(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "s")

        target = tmp_path / "out"
        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=source, targets=(target,)),
        )
        first = sync_skills(config)
        assert len(first.written) == 1
        second = sync_skills(config)
        assert second.written == []

    def test_copies_nested_files(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        skill_dir = source / "review"
        refs = skill_dir / "references"
        refs.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Review\n")
        (refs / "template.md").write_text("# Template\n")

        target = tmp_path / "out"
        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=source, targets=(target,)),
        )
        sync_skills(config)
        assert (target / "review" / "SKILL.md").read_text() == "# Review\n"
        assert (target / "review" / "references" / "template.md").read_text() == "# Template\n"

    def test_copies_skills_to_all_targets_ignoring_loose_files(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "my-skill", "# My Skill\n")
        _make_skill(source, "other", "# Other\n")
        # Loose files and non-skill directories at the source root are ignored.
        (source / "README.md").write_text("readme\n", encoding="utf-8")
        (source / "notes").mkdir()
        (source / "notes" / "draft.md").write_text("draft\n", encoding="utf-8")

        target_a = tmp_path / "a"
        target_b = tmp_path / "b"
        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=source, targets=(target_a, target_b)),
        )
        result = sync_skills(config)
        assert result.failures == []
        for target in (target_a, target_b):
            assert (target / "my-skill" / "SKILL.md").read_text() == "# My Skill\n"
            assert (target / "other" / "SKILL.md").read_text() == "# Other\n"
            assert not (target / "README.md").exists()
            assert not (target / "notes").exists()

    def test_unwritable_file_does_not_stop_other_skills_or_targets(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "my-skill", "# My Skill\n")
        _make_skill(source, "other", "# Other\n")

        target_a = tmp_path / "a"
        target_b = tmp_path / "b"
        # A read-only subdir in the first target blocks creating its SKILL.md
        blocked = target_a / "my-skill"
        blocked.mkdir(parents=True)
        os.chmod(blocked, 0o555)
        try:
            config = ProjectConfig(
                root=tmp_path,
                skills=SkillsConfig(source=source, targets=(target_a, target_b)),
            )
            result = sync_skills(config)

            assert len(result.failures) == 1
            failure = result.failures[0]
            assert failure.target == target_a
            assert failure.path == target_a / "my-skill" / "SKILL.md"

            # Sibling skill in the failing target still lands
            assert (target_a / "other" / "SKILL.md").read_text() == "# Other\n"
            # Second target is unaffected
            assert (target_b / "my-skill" / "SKILL.md").read_text() == "# My Skill\n"
            assert (target_b / "other" / "SKILL.md").read_text() == "# Other\n"
        finally:
            os.chmod(blocked, 0o755)

    def test_prunes_stale_files_within_owned_skills(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "keep")

        target = tmp_path / "out"
        # Stale file inside a source-owned skill: pruned.
        (target / "keep" / "references").mkdir(parents=True)
        (target / "keep" / "references" / "old.md").write_text("old\n", encoding="utf-8")
        # Sibling skill the source does not own: left alone.
        unowned = target / "retired"
        (unowned / "references").mkdir(parents=True)
        (unowned / "SKILL.md").write_text("# Retired\n", encoding="utf-8")
        (unowned / "references" / "notes.md").write_text("notes\n", encoding="utf-8")
        (target / "scripts").mkdir()

        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=source, targets=(target,)),
        )
        result = sync_skills(config)

        assert (target / "keep" / "SKILL.md").is_file()
        assert not (target / "keep" / "references").exists()
        assert target / "keep" / "references" / "old.md" in result.removed
        # Unowned siblings are untouched.
        assert (unowned / "SKILL.md").is_file()
        assert (unowned / "references" / "notes.md").is_file()
        assert (target / "scripts").is_dir()
        assert result.failures == []

    def test_prune_is_idempotent(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        _make_skill(source, "s")

        target = tmp_path / "out"
        # Stale file inside the owned skill triggers a prune on the first sync.
        (target / "s").mkdir(parents=True)
        (target / "s" / "stale.md").write_text("x\n", encoding="utf-8")

        config = ProjectConfig(
            root=tmp_path,
            skills=SkillsConfig(source=source, targets=(target,)),
        )
        first = sync_skills(config)
        assert first.removed != []
        second = sync_skills(config)
        assert second.removed == []
        assert second.written == []
