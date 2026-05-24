---
name: coding-agent-docs
description: Use when answering questions about configuring, extending, debugging, or operating Claude Code or Codex coding agents, including permissions, sandboxing, skills, subagents, hooks, MCP, rules, AGENTS.md, refresh behavior, CLI behavior, IDE or app behavior, and agent documentation freshness.
---

# Coding Agent Docs

Use the local reference snapshots before relying on memory for Claude Code or Codex coding-agent behavior.

## Locate Docs

Run:

```bash
agent-db --reference-root
```

Treat the output as `REFERENCE_ROOT`.

Start with:

- `REFERENCE_ROOT/README.md` for the curated human index
- `REFERENCE_ROOT/claude/README.md` for the generated Claude docs index
- `REFERENCE_ROOT/codex/README.md` for the generated Codex docs index

Do not bulk-read the generated docs tree. Search first with `rg`, then open only the matching files.

## Lookup Workflow

1. Identify whether the question is about Claude Code, Codex, or both.
2. Search the relevant generated index with focused terms.
3. Open the most relevant local markdown file.
4. Cite or summarize from local docs when answering behavior, configuration, or command questions.
5. If local docs appear stale and freshness matters, use the source link at the bottom of the generated index or curl the direct upstream markdown URL.

## URL To Local Path

Claude:

```text
https://code.claude.com/docs/en/<slug>.md
REFERENCE_ROOT/claude/<slug>.md
```

Codex:

```text
https://developers.openai.com/codex/<slug>.md
REFERENCE_ROOT/codex/<slug>.md
```

The Codex API docs are not the default source for coding-agent behavior. Use them only when the user asks about building integrations with OpenAI services.

## Freshness

Use:

```bash
agent-db --refresh
```

Refresh when the user asks for current docs, when local docs fail to answer a product behavior question, or when upstream links in the generated indexes show relevant pages that are missing locally.

For a single page, prefer curling the upstream `.md` URL instead of refreshing the full database.
