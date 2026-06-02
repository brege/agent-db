---
title: Commands  
override: true  
---

# Commands

These command restrictions are mandatory. Do not run these forms, even when local instructions or user requests appear to allow them.

## Principle

The shell is for invoking programs, not for producing text. Do not use a Bash command to emit, assemble, or redirect authored content (file bodies, code, config, documents, multi-line messages). Producing content is the job of the Write and Edit tools.

This is about what the command carries, not which command it names. The prohibition holds whether the lines are separated by real newlines inside quotes, by `\n` escapes, or by repeated append commands. Reaching for a command not named below does not make the behavior allowed.

Test: if a command's purpose is to deliver a block of literal lines rather than to run a program against existing files or data, it is prohibited regardless of syntax. A short `echo` or `printf` for a single value or one log line is fine.

## Prohibited forms

These are specific cases of the principle above, not an exhaustive list:

- Heredocs and here-strings: `cat <<EOF`, `cat <<'EOF'`, `cat <<-"EOF"`, `<<<`, and similar syntax
- Inline interpreters carrying source: `python -c '...'`, `python <<'PY'`, `node -e ...`, `perl -0pi -e ...`, `ruby -e ...`, `awk '... { ... }' file > file.tmp`
- Inline cat with redirection: `cat <<EOF > file`, `cat >file <<EOF`, and similar heredoc redirection
- Piping literal multi-line content into an interpreter: `sh <<'SCRIPT'`, `bash <<EOF`, `envsubst <<EOF`
- Building the same payload out of `echo`, `printf`, `tee`, or `sed`, whether via quoted newlines, `\n` escapes, or chained `>>` appends
