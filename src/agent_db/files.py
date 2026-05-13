from __future__ import annotations

import filecmp
import shutil
from pathlib import Path


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
