from __future__ import annotations

from pathlib import Path

import pytest


FIXTURES_HOME = Path(__file__).parent / ".home"


@pytest.fixture(scope="session", autouse=True)
def _generate_fixtures() -> None:
    from tests.fixtures import fixtures_stale, generate_all

    if fixtures_stale():
        generate_all()


@pytest.fixture
def fixture_paths():
    import yaml

    def _get_paths(file_stem: str, scenario: str) -> dict[str, Path]:
        base = FIXTURES_HOME / f"{file_stem}:{scenario}"
        if not base.exists():
            raise FileNotFoundError(
                f"Fixture {file_stem}:{scenario} not found at {base}"
            )

        result = {
            "base": base,
        }
        home = base / "home"
        if home.exists():
            result["home"] = home

        repo = base / "repo"
        if repo.exists():
            result["repo"] = repo
            result["cwd"] = repo

            fixture_yml = Path(__file__).parent / "fixtures" / f"{file_stem}.yml"
            if fixture_yml.exists():
                with open(fixture_yml) as f:
                    fixture_data = yaml.safe_load(f) or {}
                    scenario_data = fixture_data.get("scenarios", {}).get(scenario, {})
                    repo_spec = scenario_data.get("repo", {})
                    if repo_spec and repo_spec.get("cwd"):
                        result["cwd"] = repo / repo_spec.get("cwd")

        return result

    return _get_paths
