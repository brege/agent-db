from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
URL = "https://github.com/agentsmd/agents.md"
TARGET = ROOT / "docs" / "reference" / "agents.md"


def refresh() -> Path:
    if not TARGET.exists():
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", URL, str(TARGET)])
        return TARGET

    if not (TARGET / ".git").exists():
        raise RuntimeError(f"{TARGET} exists but is not a git repository")

    origin = run(["git", "-C", str(TARGET), "remote", "get-url", "origin"])
    if normalize_url(origin.stdout.strip()) != normalize_url(URL):
        raise RuntimeError(f"{TARGET} origin mismatch: {origin.stdout.strip()}")

    status = run(["git", "-C", str(TARGET), "status", "--porcelain"])
    if status.stdout.strip():
        raise RuntimeError(f"{TARGET} has local changes")

    run(["git", "-C", str(TARGET), "fetch", "--prune", "origin"])
    remote_head = resolve_remote_head()
    local_head = run(["git", "-C", str(TARGET), "rev-parse", "--verify", "HEAD"])
    remote_commit = run(["git", "-C", str(TARGET), "rev-parse", "--verify", remote_head])
    if local_head.stdout.strip() != remote_commit.stdout.strip():
        raise RuntimeError(f"{TARGET} is stale relative to {remote_head}")
    return TARGET


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=True,
    )


def normalize_url(url: str) -> str:
    return url.removesuffix(".git").removesuffix("/")


def resolve_remote_head() -> str:
    result = run(
        [
            "git",
            "-C",
            str(TARGET),
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "--short",
        ]
    )
    return result.stdout.strip() or "origin/main"
