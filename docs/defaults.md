# Default security policy

agent-db ships a dist-layer settings file (`defaults/settings.yaml`) that
configures Claude Code and Codex with a security baseline before any user
settings are applied. This document explains what the defaults assume, what
they protect, and where to override them.


## Audience

agent-db is built for a developer who runs coding agents on a personal Linux
(or macOS) workstation where code repositories live alongside personal files,
credentials, and browser profiles. The defaults reflect that split: agents
should roam freely inside project directories but never touch personal data,
key material, or infrastructure credentials.

If you run agents exclusively inside containers, VMs, or ephemeral CI
environments, the path-level denials may be redundant. The sandbox and
instruction defaults still apply.


## Assumptions

The dist defaults assume the following about your environment:

- You have credential files in standard locations (`~/.ssh`, `~/.aws`,
  `~/.kube`, etc.) that agents should never read.
- You use a shell (bash, zsh, or fish) whose history file may contain
  pasted secrets.
- You want Claude Code's OS-level sandbox enabled and enforced. If the
  sandbox cannot start, the session should fail rather than run unsandboxed.
- You want Bash commands to auto-execute inside the sandbox rather than
  prompting for each one. The sandbox boundary, not a per-command prompt,
  is the security mechanism.
- You do not want the agent's name in your git co-author line.
- You want thinking mode enabled by default.
- Model selection is a user concern. The dist layer sets `model: haiku` as
  a conservative default. Override it in your user layer.


## Claude Code sandbox

The dist defaults enable Claude Code's sandbox in strict mode:

```yaml
claude:
  sandbox:
    enabled: true
    failIfUnavailable: true
    autoAllowBashIfSandboxed: true
    allowUnsandboxedCommands: false
```

On Linux (kernel 5.13+), the sandbox uses Landlock LSM for filesystem
isolation. On Fedora 7.x and other recent kernels, this provides full
read/write/truncate coverage. On macOS, Seatbelt (sandbox-exec) provides
equivalent process-level isolation.

`autoAllowBashIfSandboxed: true` means Bash commands run without a
per-command permission prompt when the sandbox is active. The OS sandbox
constrains what the process can access at the kernel level. This is the
approach used by Trail of Bits and recommended by Anthropic's own
`settings-bash-sandbox.json` example.

`allowUnsandboxedCommands: false` rejects any command that cannot be
sandboxed rather than falling back to unsandboxed execution.

If you want both layers (sandbox as a safety net, plus per-command
prompts), set `autoAllowBashIfSandboxed: false` in your user config.


## Denied paths

The dist defaults deny agent access to credential stores, key material,
and shell history. These are organized by category.

### Key material

Directories containing cryptographic keys, password vaults, and desktop
keyring databases. Full denial (read, edit, write, glob) on the entire
directory tree.

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

The dist defaults deliberately omit:

- **Personal directories** (`~/Documents`, `~/Pictures`, etc.). These vary
  by user and belong in your user-layer settings.
- **Network egress control**. Claude Code supports domain allowlists via
  `sandbox.network.allowedDomains`, but the right allowlist depends on
  your stack. The dist layer does not restrict network access.
- **Codex-specific sandbox settings**. Codex uses `sandbox_mode` and
  `[sandbox_workspace_write]` or the newer permission profiles. These are
  set per-user because `writable_roots` and `network_access` depend on
  your project layout.
- **Command-level deny rules**. The dist layer ships behavioral
  instruction rules (in `defaults/instructions/commands.md`) rather than
  settings-level command denials. Command denials in settings.json are
  translated per-agent and have known enforcement gaps; the instruction
  rules are a complementary layer.


## Overriding defaults

The user layer (`~/.config/agent-db/settings.yaml` on Linux) merges on
top of the dist layer. Use `append:` to add rules while preserving dist
defaults. Use `override:` to replace an entire namespace.

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

Using `override:` for the `claude:` namespace replaces the entire dist
`claude:` block, including the sandbox settings. If you override `claude:`
to set a model, you must re-declare the sandbox settings you want to keep.
Prefer `append:` for scalar overrides like `model:`, which replaces only
that key while preserving the rest.


## References

Security configurations and hardening guides from the community that
informed these defaults.

### Agent vendor examples

- [Anthropic claude-code examples/settings](https://github.com/anthropics/claude-code/tree/main/examples/settings):
  `settings-strict.json`, `settings-bash-sandbox.json`, and
  `settings-lax.json` covering the full strictness spectrum.

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
  three-layer approach (settings, hooks, macOS Seatbelt) with compound
  command splitting in the hook layer.
- [fcakyon/claude-codex-settings](https://github.com/fcakyon/claude-codex-settings):
  allowlist-only model with domain-scoped WebFetch permissions.

### Dotfiles and practitioner configs

- [vsbuffalo/dotfiles](https://github.com/vsbuffalo/dotfiles/blob/main/docs/claude-code.md):
  three-tier allowlist philosophy (always, deny-variants, prompted).
- [Harper Reed dotfiles](https://github.com/harperreed/dotfiles/blob/master/.claude/CLAUDE.md):
  behavioral constraints via CLAUDE.md rather than settings.json hardening.
- [feiskyer/codex-settings](https://github.com/feiskyer/codex-settings/blob/main/config.toml):
  Codex workspace-write with LiteLLM gateway.
- [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code/blob/main/.codex/config.toml):
  multi-agent Codex setup with strict/yolo profiles.

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
  argues for OS-level sandboxing over prompt-based permissions; flags
  network egress as the underappreciated threat vector.
