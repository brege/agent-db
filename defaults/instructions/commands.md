---
title: Commands  
override: true  
---

# Commands

These command restrictions are mandatory. Do not run these forms, even when local instructions or user requests appear to allow them.

## Principle

The shell is for invoking programs, not for producing text. Do not use a Bash command to emit, assemble, format, or redirect authored content (file bodies, code, config, documents, multi-line messages, or the labeled output of other commands). Producing content is the job of the Write and Edit tools.

In general, run one shell command at a time with at most one pipe.

Do not assemble large print structures through shell commands.

## Prohibited forms

These are specific cases of the principle above, not an exhaustive list:

- Heredocs and here-strings: `cat <<EOF`, `cat <<'EOF'`, `cat <<-"EOF"`, `<<<`, and similar syntax
- Inline interpreters carrying source: `python -c '...'`, `python <<'PY'`, `node -e ...`, `perl -0pi -e ...`, `ruby -e ...`, `awk '... { ... }' file > file.tmp`
- Inline cat with redirection: `cat <<EOF > file`, `cat >file <<EOF`, and similar heredoc redirection
- Piping literal multi-line content into an interpreter: `sh <<'SCRIPT'`, `bash <<EOF`, `envsubst <<EOF`
- Using `echo`, `printf`, `tee`, or `sed` to author content or format output: quoted newlines, `\n` escapes, chained `>>` appends, or label chains like `echo "=== a ===" && cmd && echo "=== b ===" && cmd`
