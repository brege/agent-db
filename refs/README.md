# Reference Index

`refs/` stores local snapshots of Claude, Codex, and AGENTS.md documentation. Generated snapshots are ignored by git. This index is tracked.

Refresh snapshots:

```bash
python docs.py
```

## User-Facing Behavior

Claude:

- [memory.md] - `CLAUDE.md`, `@path` imports, user instructions, project instructions, `.claude/rules/`, and auto memory
- [claude-directory.md] - global and project `.claude/` files
- [settings.md] - settings precedence, `settings.json`, subagents, plugins, and permission settings
- [permissions.md] - `permissions.allow`, `permissions.deny`, tool names, path rules, and additional directories
- [sandboxing.md] - sandbox behavior
- [skills.md] - `~/.claude/skills/<name>/SKILL.md`, project skills, skill frontmatter, and precedence
- [sub-agents.md] - `~/.claude/agents/*.md`, project agents, frontmatter, tools, model, and memory
- [commands.md] - slash commands and their overlap with skills

Codex:

- [agents-md.md] - global `AGENTS.md`, project `AGENTS.md`, `AGENTS.override.md`, fallback filenames, and size limits
- [config-basic.md] - `~/.codex/config.toml`, project `.codex/config.toml`, precedence, profiles, and permissions
- [config-advanced.md] - `CODEX_HOME`, project config discovery, hooks, profiles, and sandbox settings
- [config-reference.md] - config key reference, including permissions and filesystem profile keys
- [config-sample.md] - example config with permissions and `glob_scan_max_depth`
- [rules.md] - `.rules` files, `prefix_rule`, and command decisions
- [codex/skills.md] - `~/.agents/skills`, repo skills, user skills, and skill metadata
- [subagents.md] - `~/.codex/agents/*.toml`, project agents, and agent config keys

## Maintainer References

Claude:

- [hooks.md] - hook event reference
- [hooks-guide.md] - hook examples and settings integration
- [plugins.md] - plugin use and installation
- [plugins-reference.md] - plugin schema and caching details
- [mcp.md] - MCP settings
- [env-vars.md] - environment variables, including `CLAUDE_CONFIG_DIR`
- [server-managed-settings.md] - managed settings
- [debug-your-config.md] - troubleshooting generated config

Codex:

- [codex/hooks.md] - Codex hook events and config locations
- [codex/mcp.md] - MCP config in `config.toml`
- [codex/plugins.md] - plugin config and installation
- [plugins/build.md] - plugin package layout
- [speed.md] - speed settings

AGENTS.md:

- [agents.md/README.md] - public AGENTS.md convention
- [agents.md/AGENTS.md] - upstream repository agent instructions

## Output Checks

Use these docs when changing generators:

- Claude `CLAUDE.md` imports: [memory.md]
- Claude user config directory: [claude-directory.md], [env-vars.md]
- Claude permissions: [permissions.md], [settings.md]
- Claude skills: [skills.md]
- Claude agents: [sub-agents.md]
- Codex global instructions: [agents-md.md]
- Codex config home: [config-advanced.md]
- Codex config keys: [config-reference.md], [config-sample.md]
- Codex rules: [rules.md]
- Codex skills: [codex/skills.md]
- Codex agents: [subagents.md]

[agents-md.md]: codex/guides/agents-md.md
[agents.md/AGENTS.md]: agents.md/AGENTS.md
[agents.md/README.md]: agents.md/README.md
[claude-directory.md]: claude/claude-directory.md
[codex/hooks.md]: codex/hooks.md
[codex/mcp.md]: codex/mcp.md
[codex/plugins.md]: codex/plugins.md
[codex/skills.md]: codex/skills.md
[commands.md]: claude/commands.md
[config-advanced.md]: codex/config-advanced.md
[config-basic.md]: codex/config-basic.md
[config-reference.md]: codex/config-reference.md
[config-sample.md]: codex/config-sample.md
[debug-your-config.md]: claude/debug-your-config.md
[env-vars.md]: claude/env-vars.md
[hooks-guide.md]: claude/hooks-guide.md
[hooks.md]: claude/hooks.md
[mcp.md]: claude/mcp.md
[memory.md]: claude/memory.md
[permissions.md]: claude/permissions.md
[plugins-reference.md]: claude/plugins-reference.md
[plugins.md]: claude/plugins.md
[plugins/build.md]: codex/plugins/build.md
[rules.md]: codex/rules.md
[sandboxing.md]: claude/sandboxing.md
[server-managed-settings.md]: claude/server-managed-settings.md
[settings.md]: claude/settings.md
[skills.md]: claude/skills.md
[speed.md]: codex/speed.md
[sub-agents.md]: claude/sub-agents.md
[subagents.md]: codex/subagents.md
