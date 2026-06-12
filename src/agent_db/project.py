"""Project-level skill sync: read agent-db.toml, copy skills to targets."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from agent_db.claude import copy_assets
from agent_db.source import load_asset_dirs


@dataclass(frozen=True)
class SkillsConfig:
    source: Path
    targets: tuple[Path, ...]


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    skills: SkillsConfig | None


def load_config(root: Path) -> ProjectConfig:
    config_path = root / "agent-db.toml"
    if not config_path.is_file():
        return ProjectConfig(root=root, skills=None)

    with open(config_path, "rb") as fh:
        data = tomllib.load(fh)

    skills_data = data.get("skills")
    if skills_data is None:
        return ProjectConfig(root=root, skills=None)

    if not isinstance(skills_data, dict):
        raise ValueError("skills must be a table")

    source = skills_data.get("source")
    if not isinstance(source, str) or not source:
        raise ValueError("skills.source is required")

    targets = skills_data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("skills.targets is required")
    for entry in targets:
        if not isinstance(entry, str) or not entry:
            raise ValueError("each skills.targets entry must be a non-empty string")

    return ProjectConfig(
        root=root,
        skills=SkillsConfig(
            source=root / source,
            targets=tuple(root / t for t in targets),
        ),
    )


def sync_skills(config: ProjectConfig) -> list[Path]:
    if config.skills is None:
        return []

    source = config.skills.source
    if not source.is_dir():
        raise FileNotFoundError(f"skills source not found: {source}")

    assets = load_asset_dirs(source)
    written: list[Path] = []
    for target in config.skills.targets:
        written.extend(copy_assets(assets, target))
    return written


def find_git_root(start: Path | None = None) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=start,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except FileNotFoundError:
        pass
    return None
