"""Project-level skill sync: read agent-db.toml, copy skills to targets, prune stale files."""

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
    removed: list[Path] = field(default_factory=list)
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
            source=resolve_path(root, source),
            targets=tuple(resolve_path(root, t) for t in targets),
        ),
    )


def resolve_path(root: Path, value: str) -> Path:
    """Expand ~ and keep absolute paths; resolve relative paths against root."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def sync_skills(config: ProjectConfig) -> SyncResult:
    if config.skills is None:
        return SyncResult()

    source = config.skills.source
    if not source.is_dir():
        raise FileNotFoundError(f"skills source not found: {source}")

    sources = source_files(source)
    expected = {relative for _, relative in sources}
    written: list[Path] = []
    removed: list[Path] = []
    failures: list[SyncFailure] = []
    for target in config.skills.targets:
        for source_file, relative in sources:
            target_file = target / relative
            try:
                if files.copy_file(source_file, target_file):
                    written.append(target_file)
            except OSError as exc:
                failures.append(SyncFailure(target=target, path=target_file, error=str(exc)))
        target_removed, target_failures = prune_stale(target, expected)
        removed.extend(target_removed)
        failures.extend(target_failures)
    return SyncResult(written=written, removed=removed, failures=failures)


def prune_stale(target: Path, expected: set[Path]) -> tuple[list[Path], list[SyncFailure]]:
    """Delete stale files inside source-owned skills, then any emptied stale directories.

    Pruning is scoped to the top-level skill directories the source contains, so
    sibling skills the source does not own are never touched. Deepest paths first,
    so files go before their directories and nested empty directories collapse
    upward in one pass. Directories that are ancestors of expected files are kept
    even when empty (a failed copy must not cascade into removing the skill
    directory it was meant to fill).
    """
    removed: list[Path] = []
    failures: list[SyncFailure] = []
    if not target.is_dir():
        return removed, failures
    owned = {relative.parts[0] for relative in expected if relative.parts}
    expected_dirs: set[Path] = set()
    for relative in expected:
        expected_dirs.update(relative.parents)
    for path in sorted(target.rglob("*"), reverse=True):
        relative = path.relative_to(target)
        if not relative.parts or relative.parts[0] not in owned:
            continue
        try:
            if path.is_file():
                if relative not in expected:
                    path.unlink()
                    removed.append(path)
            elif path.is_dir():
                if relative not in expected_dirs and not any(path.iterdir()):
                    path.rmdir()
                    removed.append(path)
        except OSError as exc:
            failures.append(SyncFailure(target=target, path=path, error=str(exc)))
    return removed, failures


def source_files(source: Path) -> list[tuple[Path, Path]]:
    """Every file under each top-level skill, paired with its path relative to source.

    A skill is an immediate child directory of source that holds a SKILL.md. Loose
    files and non-skill directories (.git, tooling, sibling projects) are ignored,
    so a source pointed at a mixed repo root syncs only its skills.
    """
    result: list[tuple[Path, Path]] = []
    for skill in sorted(source.iterdir()):
        if not skill.is_dir() or not (skill / "SKILL.md").is_file():
            continue
        for path in sorted(skill.rglob("*")):
            if path.is_file():
                result.append((path, path.relative_to(source)))
    return result


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
