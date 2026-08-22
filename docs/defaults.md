# Default security policy

agent-db loads distribution settings from `defaults/settings.yaml` and
`defaults/settings/*.yaml` before user settings are applied. This document
identifies the environment assumptions, access restrictions, and override
behavior defined by those settings.


## Audience

agent-db is built for a developer who runs coding agents on a personal Linux
or macOS workstation where code repositories and personal data use the same
filesystem. The defaults permit project-directory access and deny access to
named credential, key, history, and browser-profile locations.

If you run agents exclusively inside containers, VMs, or ephemeral CI
environments, the path-level denials may duplicate restrictions supplied by
the outer environment. The sandbox and instruction defaults still apply.


## Assumptions

The distribution defaults assume the following about your environment:

- Credential files may exist in standard locations such as `~/.ssh`,
  `~/.aws`, and `~/.kube`.
- Bash, Zsh, or Fish history files may contain pasted credentials or other
  restricted values.
- Claude Code's sandbox must start successfully. `failIfUnavailable: true`
  prevents an unsandboxed fallback.
- `autoAllowBashIfSandboxed: true` permits Bash commands without a separate
  command prompt while the sandbox is active.
- `includeCoAuthoredBy: false` disables Claude co-author attribution.
- `alwaysThinkingEnabled: true` enables thinking mode.
- The distribution sets `model: haiku`. User settings may replace this value.


## Claude Code sandbox

The distribution enables Claude Code's sandbox with unavailable-sandbox
failure and unsandboxed-command rejection:

```yaml
claude:
  sandbox:
    enabled: true
    failIfUnavailable: true
    autoAllowBashIfSandboxed: true
    allowUnsandboxedCommands: false
```

On supported Linux systems, Claude Code uses Landlock for filesystem
isolation. On macOS, Claude Code uses Seatbelt. Kernel and Claude Code support
determine the operations each backend restricts.

`autoAllowBashIfSandboxed: true` means Bash commands run without a
per-command permission prompt when the sandbox is active. The operating
system sandbox applies filesystem restrictions to the command process. The
Trail of Bits configuration and Anthropic's `settings-bash-sandbox.json`
example use this setting.

`allowUnsandboxedCommands: false` rejects any command that cannot be
sandboxed rather than falling back to unsandboxed execution.

To require per-command prompts in addition to sandbox enforcement, set
`autoAllowBashIfSandboxed: false` in user settings.


## Denied paths

The distribution defaults deny agent access to credential stores, key material,
and shell history. These are organized by category.

### Key material

Directories containing cryptographic keys, password vaults, and desktop
keyring databases. The rules deny read, edit, write, and glob operations for
the complete directory tree.

| Path | Contents |
|---|---|
| `~/.ssh/**` | SSH keys, known_hosts, agent sockets |
| `~/.gnupg/**` | GPG keys, trust database |
| `~/.password-store/**` | pass(1) encrypted password store |
| `~/.local/share/keyrings/**` | GNOME keyring files on disk |

### Cloud and infrastructure credentials

Directories containing tokens, certificates, and session caches for cloud
providers, container registries, and orchestration tools.

| Path | Contents |
|---|---|
| `~/.aws/**` | AWS access keys, SSO cache, config |
| `~/.azure/**` | Azure CLI tokens and config |
| `~/.config/gcloud/**` | Google Cloud credentials and project config |
| `~/.kube/**` | Kubernetes cluster certs and auth tokens |
| `~/.config/gh/**` | GitHub CLI OAuth tokens |
| `~/.docker/config.json` | Docker registry auth tokens |

### Package manager and registry tokens

Individual files containing publish/upload tokens for language-specific
package registries. Only the credential file is denied, not the parent
directory (e.g. `~/.cargo/` is accessible for Rust builds, but
`~/.cargo/credentials.toml` is not).

| Path | Contents |
|---|---|
| `~/.npmrc` | npm registry tokens |
| `~/.pypirc` | PyPI upload tokens |
| `~/.cargo/credentials.toml` | crates.io publish token |
| `~/.gem/credentials` | RubyGems API key |
| `~/.git-credentials` | Git credential helper cache |
| `~/.netrc` | HTTP/FTP credentials (used by curl, git) |

### Shell history

History files can contain pasted secrets, database connection strings,
and one-off tokens from interactive sessions.

| Path | Contents |
|---|---|
| `~/.bash_history` | Bash command history |
| `~/.zsh_history` | Zsh command history |
| `~/.local/share/fish/fish_history` | Fish shell history |

### Browser and application profiles

Desktop application data directories that may contain session cookies,
saved passwords, or OAuth tokens.

| Path | Contents |
|---|---|
| `~/.var/app/**` | Flatpak application data |
| `~/.mozilla/**` | Firefox profiles, cookies, saved logins |
| `~/.thunderbird/**` | Thunderbird mail profiles and credentials |
| `~/.config/chromium/**` | Chromium profiles, cookies, saved logins |


## What the defaults do not cover

The distribution defaults omit:

- **Personal directories** (`~/Documents`, `~/Pictures`, etc.). These vary
  by user and must be declared in user-layer settings.
- **Network egress control**. Claude Code supports domain allowlists via
  `sandbox.network.allowedDomains`, but the required domains depend on the
  services used in each environment. The distribution does not restrict
  network access.
- **Codex-specific sandbox settings**. Codex uses `sandbox_mode` and
  `[sandbox_workspace_write]` or the newer permission profiles. These are
  set in user configuration because `writable_roots` and `network_access`
  depend on the project layout.

## Command denials

`defaults/settings/commands.yaml`, `defaults/settings/git.yaml`, and
`defaults/settings/installers.yaml` define distribution command-denial
patterns. agent-db translates these patterns into Claude Bash permission
entries and renders representable command prefixes as Codex `.rules` entries.
Generated CLAUDE.md and AGENTS.md files also include every denial as an
instruction.

Codex prefix rules cannot represent heredoc shell syntax. agent-db omits those
patterns from `.rules` output and reports each omission when the corresponding
rules file changes. The generated instruction files retain the patterns.


## Overriding defaults

The user layer (`~/.config/agent-db/settings.yaml` on Linux) is merged after
the distribution layer. Use `append:` to add rules while preserving
distribution defaults. Use `override:` to replace an entire namespace.

To add personal directory denials and project-specific allows:

```yaml
append:
  permissions:
    paths:
      deny:
        - path: "~/documents/**"
          permissions: [read, edit, write, glob]
      allow:
        - path: "~/code/**"
          permissions: [read, write, edit, glob]
  claude:
    model: claude-opus-4-5-20251101
```

Using `override:` for the `claude:` namespace replaces the entire distribution
`claude:` block, including the sandbox settings. If you override `claude:`
to set a model, you must re-declare the sandbox settings you want to keep.
Prefer `append:` for scalar overrides like `model:`, which replaces only
that key while preserving the rest.


## References

The following security configurations and hardening guides provided source
material for these defaults.

### Agent vendor examples

- [Anthropic claude-code examples/settings](https://github.com/anthropics/claude-code/tree/main/examples/settings):
  `settings-strict.json`, `settings-bash-sandbox.json`, and
  `settings-lax.json` provide strict, sandboxed Bash, and permissive examples.

### Published security configs

- [Trail of Bits claude-code-config](https://github.com/trailofbits/claude-code-config):
  security firm config with credential path denials, PreToolUse hooks for
  destructive command variants, and crypto wallet path blocking.
- [okdt claude-code-hardening-cheatsheet](https://github.com/okdt/claude-code-hardening-cheatsheet):
  structured deny rules by threat category with hook scripts for SQL
  injection and force-push blocking.
- [okdt codex-cli-hardening-cheatsheet](https://github.com/okdt/codex-cli-hardening-cheatsheet):
  Codex-specific Starlark rules and sandbox profiles.
- [dylancaponi/claude-code-permissions](https://github.com/dylancaponi/claude-code-permissions):
  settings, hooks, and macOS Seatbelt enforcement with compound
  command splitting in the hook layer.
- [fcakyon/claude-codex-settings](https://github.com/fcakyon/claude-codex-settings):
  allowlist-only model with domain-scoped WebFetch permissions.

### Dotfiles and practitioner configs

- [vsbuffalo/dotfiles](https://github.com/vsbuffalo/dotfiles/blob/main/docs/claude-code.md):
  three allowlist tiers: always allowed, denied variants, and prompted.
- [Harper Reed dotfiles](https://github.com/harperreed/dotfiles/blob/master/.claude/CLAUDE.md):
  behavioral constraints via CLAUDE.md rather than settings.json hardening.
- [feiskyer/codex-settings](https://github.com/feiskyer/codex-settings/blob/main/config.toml):
  Codex workspace-write with LiteLLM gateway.
- [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code/blob/main/.codex/config.toml):
  multi-agent Codex setup with strict and unrestricted profiles.

### Sandbox architectures

- [Esokia Labs bubblewrap sandbox guide](https://labs.esokia.com/post/sandboxing-claude-code-cli-linux-bubblewrap/):
  outer bwrap wrapper with namespace isolation, read-only system mounts,
  and selective credential directory binding.
- [CaptainMcCrank/SandboxedClaudeCode](https://github.com/CaptainMcCrank/SandboxedClaudeCode):
  three-backend sandbox (bubblewrap, firejail, Apple Container) with
  capability dropping and seccomp filtering.
- [rommelporras/dotfiles](https://github.com/rommelporras/dotfiles):
  Podman container-per-project with credential management via Podman
  secrets.

### Analysis and commentary

- [Simon Willison, "Living dangerously with Claude"](https://simonwillison.net/2025/Oct/22/living-dangerously-with-claude/):
  argues for OS-level sandboxing over prompt-based permissions and identifies
  network egress as a significant risk.
