from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rich.console import Console

from agent_db import __version__, claude, codex
from agent_db.display import MemoryPayload, loaded_context_model, print_loaded_context
from agent_db.schema import Agent, claude_load_order, codex_load_order
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
        "-m",
        "--memory",
        dest="show_memory",
        action="store_true",
        help="show what Claude and Codex will load from current directory",
    )
    parser.add_argument(
        "-a",
        "--agent",
        choices=["claude", "codex", "all"],
        default="all",
        help="agent to inspect with --memory",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="emit --memory output as JSON",
    )
    parser.add_argument(
        "-r",
        "--refresh",
        dest="refresh_docs",
        action="store_true",
        help="refresh local reference snapshots",
    )
    parser.add_argument(
        "--reference-root",
        action="store_true",
        help="print the local reference snapshot root",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.refresh_docs:
        if args.show_memory:
            parser.error("--refresh cannot be used with --memory")
        if args.json_output:
            parser.error("--json requires --memory")
        if args.agent != "all":
            parser.error("--agent requires --memory")
        if args.reference_root:
            parser.error("--refresh cannot be used with --reference-root")
        return refresh_docs()
    if args.reference_root:
        if args.show_memory:
            parser.error("--reference-root cannot be used with --memory")
        if args.json_output:
            parser.error("--json requires --memory")
        if args.agent != "all":
            parser.error("--agent requires --memory")
        return print_reference_root()
    if args.json_output and not args.show_memory:
        parser.error("--json requires --memory")
    if args.agent != "all" and not args.show_memory:
        parser.error("--agent requires --memory")

    if args.show_memory:
        return show_memory(args)
    return build_outputs(args)


def show_memory(args: argparse.Namespace) -> int:
    cwd = Path.cwd()

    if args.agent == "all":
        agents_to_show = [Agent.CLAUDE, Agent.CODEX]
    else:
        agents_to_show = [Agent(args.agent)]

    contexts = []
    for agent in agents_to_show:
        if agent == Agent.CLAUDE:
            ctx = claude_load_order(cwd, claude_home=claude_home().expanduser())
        else:
            ctx = codex_load_order(
                cwd,
                codex_home=codex_home().expanduser(),
            )
        contexts.append(loaded_context_model(ctx))

    output = MemoryPayload(contexts=tuple(contexts))
    if args.json_output:
        print(json.dumps(output.model_dump(mode="json"), indent=2))
        return 0

    console = Console()
    for index, context in enumerate(contexts):
        if index:
            console.print()
        print_loaded_context(console, context)

    return 0


def build_outputs(args: argparse.Namespace) -> int:
    source = AgentSource.from_roots(defaults_root(), agent_db_home())
    written = claude.write_global(source, claude_home())
    written.extend(codex.write_global(source, codex_home()))

    for path in written:
        print(path)

    return 0


def refresh_docs() -> int:
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.docs import refresh

    return refresh.main()


def print_reference_root() -> int:
    print(reference_root())
    return 0


def reference_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "reference"


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


if __name__ == "__main__":
    raise SystemExit(main())
