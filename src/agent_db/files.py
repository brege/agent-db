"""Idempotent file writes: only touch disk when content changes."""

from __future__ import annotations

import filecmp
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_db.source import AssetDir


def write_text(path: Path, content: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def copy_file(source: Path, target: Path) -> bool:
    if target.is_file() and filecmp.cmp(source, target, shallow=False):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def copy_assets(assets: Iterable[AssetDir], target_root: Path) -> list[Path]:
    written: list[Path] = []
    for asset in assets:
        target = target_root / asset.name
        for source_file in sorted(asset.path.rglob("*")):
            if not source_file.is_file():
                continue
            relative = source_file.relative_to(asset.path)
            target_file = target / relative
            if copy_file(source_file, target_file):
                written.append(target_file)
    return written
