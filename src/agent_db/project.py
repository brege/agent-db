"""Project-level skill sync: read agent-db.toml, copy skills to targets."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from agent_db import files


@dataclass(frozen=True)
class SkillsConfig:
    source: Path
    targets: tuple[Path, ...]


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    skills: SkillsConfig | None


@dataclass(frozen=True)
class SyncFailure:
    target: Path
    path: Path
    error: str


@dataclass(frozen=True)
class SyncResult:
    written: list[Path] = field(default_factory=list)
    failures: list[SyncFailure] = field(default_factory=list)


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


def sync_skills(config: ProjectConfig) -> SyncResult:
    if config.skills is None:
        return SyncResult()

    source = config.skills.source
    if not source.is_dir():
        raise FileNotFoundError(f"skills source not found: {source}")

    sources = source_files(source)
    written: list[Path] = []
    failures: list[SyncFailure] = []
    for target in config.skills.targets:
        for source_file, relative in sources:
            target_file = target / relative
            try:
                if files.copy_file(source_file, target_file):
                    written.append(target_file)
            except OSError as exc:
                failures.append(SyncFailure(target=target, path=target_file, error=str(exc)))
    return SyncResult(written=written, failures=failures)


def source_files(source: Path) -> list[tuple[Path, Path]]:
    """Every file under source paired with its path relative to source."""
    return [
        (path, path.relative_to(source)) for path in sorted(source.rglob("*")) if path.is_file()
    ]


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
