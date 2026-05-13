from __future__ import annotations

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
