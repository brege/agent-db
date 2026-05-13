from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from agent_db import __version__
from agent_db import claude, codex
from agent_db.source import AgentSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-db",
        description="Maintain global Claude Code and Codex configuration.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--from",
        dest="user_root",
        type=Path,
        help="read user config from this directory",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return build_outputs(args)


def build_outputs(args: argparse.Namespace) -> int:
    source = AgentSource.from_roots(defaults_root(), args.user_root or agent_db_home())
    written = claude.write_global(source, claude_home())
    written.extend(codex.write_global(source, codex_home(), agents_home()))

    for path in written:
        print(path)

    return 0


def defaults_root() -> Path:
    value = os.environ.get("AGENT_DB_DEFAULTS")
    if value:
        return Path(value)
    return Path(__file__).resolve().parents[2] / "defaults"


def agent_db_home() -> Path:
    value = os.environ.get("AGENT_DB_HOME")
    if value:
        return Path(value)
    return platform_config_home() / "agent-db"


def platform_config_home() -> Path:
    if sys.platform == "win32":
        value = os.environ.get("APPDATA")
        return Path(value) if value else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    value = os.environ.get("XDG_CONFIG_HOME")
    return Path(value) if value else Path.home() / ".config"


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex"))


def agents_home() -> Path:
    return Path("~/.agents")


if __name__ == "__main__":
    raise SystemExit(main())
