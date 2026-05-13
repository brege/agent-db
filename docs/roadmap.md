# Roadmap

## Source

- [x] Load project defaults from `defaults/`.
- [x] Load user config from `AGENT_DB_HOME`.
- [x] Default Linux user config to `~/.config/agent-db`.
- [x] Support `--from` for staging and migration.
- [x] Load `partials/*.md`.
- [x] Parse markdown frontmatter.
- [x] Use `title`, then filename, then first H1 as the partial title.
- [x] Treat missing `override` as `false`.
- [x] Merge partials by key with append or override behavior.
- [x] Drop duplicate matching H1 headings when appending a partial.
- [x] Load `settings.yaml` and `settings/*.yaml`.
- [x] Support YAML `append` and `override`.
- [x] Load `skills/*` and `agents/*`.
- [ ] Add clearer validation errors for malformed source files.
- [ ] Move the source contract out of `prototype/contract.yaml`.

## Claude

- [x] Emit `CLAUDE.md`.
- [x] Emit `rules/<section>.md`.
- [x] Render `CLAUDE.md` with `# CLAUDE.md` and section links to `@rules/<section>.md`.
- [x] Emit `settings.json`.
- [x] Map command policy to `Bash(...)` permissions.
- [x] Map path `read` and `glob` permissions to `Read(...)`.
- [x] Map path `edit` and `write` permissions to `Edit(...)`.
- [x] Copy skills to `skills/*`.
- [x] Copy agents to `agents/*.md`.
- [ ] Decide whether generated global rules should be imported from `CLAUDE.md`, loaded from `~/.claude/rules/`, or path-scoped.

## Codex

- [x] Emit `AGENTS.md`.
- [x] Render `AGENTS.md` with one top-level `# AGENTS.md`.
- [x] Demote partial headings in Codex output.
- [x] Emit `config.toml`.
- [x] Map path allow rules to `read` or `write`.
- [x] Map path deny rules to `none`.
- [x] Expand `~/` paths in filesystem permissions.
- [x] Emit `glob_scan_max_depth` for `**` globs.
- [x] Emit `rules/*.rules` from command policy.
- [x] Map command allow, ask, and deny to `allow`, `prompt`, and `forbidden`.
- [x] Skip heredoc and here-string command patterns in `.rules` output.
- [x] Copy skills to `~/.agents/skills/*`.
- [x] Convert simple agent markdown to `agents/*.toml`.
- [x] Preserve unrelated `config.toml` sections when rewriting Codex config.
- [ ] Report command patterns that cannot be represented as Codex prefix rules.
- [ ] Define Claude agent metadata to Codex agent TOML mapping.

## CLI

- [x] Provide `agent-db`.
- [x] Print changed files only.
- [x] Stay quiet on no-op runs.
- [x] Resolve Claude output from `CLAUDE_CONFIG_DIR`, defaulting to `~/.claude`.
- [x] Resolve Codex output from `CODEX_HOME`, defaulting to `~/.codex`.
- [x] Resolve Codex skills output from `~/.agents`.
- [x] Support staged builds through environment variables.
- [ ] Add `--check` for a read-only project view of Claude and Codex instruction files.
- [ ] Add a build summary for skipped or non-representable rules.

## References

- [x] Fetch Claude markdown docs.
- [x] Fetch Codex markdown docs.
- [x] Use Beautiful Soup for sidebar discovery only.
- [x] Keep generated refs ignored by git.
- [x] Track `refs/README.md` as the reference index.
- [ ] Update the reference index when target docs change.

## Tests

- [x] Test partial title resolution and default append behavior.
- [x] Test Claude and Codex global output generation.
- [x] Test idempotent writes.
- [x] Test Codex heredoc patterns are not emitted as fake prefix rules.
- [x] Keep scraper tests passing.
- [ ] Add a golden build test for the default source tree.
- [ ] Add CLI integration coverage.
- [ ] Add validation failure tests.
- [ ] Add agent conversion tests.
