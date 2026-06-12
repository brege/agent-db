from __future__ import annotations

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
        assert sync_skills(config) == []

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
        written = sync_skills(config)
        assert len(written) == 2
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
        assert len(first) == 1
        second = sync_skills(config)
        assert second == []

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
