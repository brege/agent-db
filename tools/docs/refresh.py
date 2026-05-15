from __future__ import annotations

import sys
from pathlib import Path

if __package__:
    from .scrape import agent_md, claude, codex
else:
    root = str(Path(__file__).resolve().parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from scrape import agent_md, claude, codex


def main() -> int:
    written = []
    written.extend(claude.refresh())
    written.extend(codex.refresh())
    written.append(agent_md.refresh())

    for path in written:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
