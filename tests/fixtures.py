from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"
HOME_DIR = Path(__file__).parent / ".home"
MANIFEST = HOME_DIR / ".manifest.json"


def load_fixtures() -> dict[str, dict[str, Any]]:
    all_fixtures = {}
    for yml_file in FIXTURES_DIR.glob("*.yml"):
        with open(yml_file) as f:
            data = yaml.safe_load(f) or {}
            scenarios = data.get("scenarios", {})
            for scenario_name, scenario_data in scenarios.items():
                key = f"{yml_file.stem}:{scenario_name}"
                all_fixtures[key] = scenario_data
    return all_fixtures


def generate_fixture(name: str, data: dict[str, Any]) -> Path:
    base = HOME_DIR / name
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    home_spec = data.get("home", {})
    if home_spec:
        home_dir = base / "home"
        _create_tree(home_dir, home_spec)

    repo_spec = data.get("repo")
    if repo_spec:
        repo_dir = base / "repo"
        _create_tree(repo_dir, repo_spec.get("files", {}))

        git_spec = repo_spec.get("git", False)
        if git_spec is True:
            (repo_dir / ".git").mkdir(exist_ok=True)
        elif git_spec == "file":
            (repo_dir / ".git").write_text("gitdir: .../path\n")

    return base


def _create_tree(root: Path, spec: dict[str, Any]) -> None:
    """Recursively create files and directories from spec."""
    root.mkdir(parents=True, exist_ok=True)
    for key, value in spec.items():
        path = root / key
        if isinstance(value, dict):
            _create_tree(path, value)
        elif isinstance(value, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        elif isinstance(value, bool) and value:
            path.mkdir(exist_ok=True)


def clean() -> None:
    if HOME_DIR.exists():
        shutil.rmtree(HOME_DIR)
    print(f"Cleaned {HOME_DIR}")


def generate_all() -> None:
    fixtures = load_fixtures()
    for name in sorted(fixtures):
        data = fixtures[name]
        path = generate_fixture(name, data)
        print(f"Generated: {path}")
    write_manifest()


def generate_one(pattern: str) -> None:
    fixtures = load_fixtures()
    matched = [name for name in fixtures if pattern in name]
    if not matched:
        print(f"No fixtures match {pattern!r}", file=sys.stderr)
        return
    for name in matched:
        data = fixtures[name]
        path = generate_fixture(name, data)
        print(f"Generated: {path}")
    write_manifest()


def fixtures_stale() -> bool:
    fixtures = load_fixtures()
    if not HOME_DIR.exists():
        return True
    if any(not (HOME_DIR / name).exists() for name in fixtures):
        return True
    if read_manifest() != fixture_signature():
        return True
    for name in fixtures:
        stem = name.split(":", 1)[0]
        source = FIXTURES_DIR / f"{stem}.yml"
        if source.stat().st_mtime_ns > (HOME_DIR / name).stat().st_mtime_ns:
            return True
    return False


def fixture_signature() -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURES_DIR.glob("*.yml"))
    }


def read_manifest() -> dict[str, str]:
    if not MANIFEST.is_file():
        return {}
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"fixture manifest must be a mapping: {MANIFEST}")
    return {str(key): str(value) for key, value in data.items()}


def write_manifest() -> None:
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(fixture_signature(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate test fixtures")
    parser.add_argument(
        "--clean",
        "-c",
        action="store_true",
        help="Remove all generated fixtures",
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        help="Fixture pattern to generate (e.g. 'claude:layered')",
    )

    args = parser.parse_args()

    if args.clean:
        clean()
        return 0
    elif args.pattern:
        generate_one(args.pattern)
    else:
        generate_all()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
