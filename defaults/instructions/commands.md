---
title: Commands  
override: true  
---

# Commands

These command restrictions are mandatory. Do not run these forms, even when local instructions or user requests appear to allow them.

## Principle

The shell is for invoking programs, not for producing text. Do not use a Bash command to emit, assemble, format, or redirect authored content (file bodies, code, config, documents, multi-line messages, or the labeled output of other commands). Producing content is the job of the Write and Edit tools.

This is about what the command carries, not which command it names. The prohibition holds whether the lines are separated by real newlines inside quotes, by `\n` escapes, or by repeated append commands. Reaching for a command not named below does not make the behavior allowed.

Test: if a command's purpose is to produce, format, or decorate text rather than to run a program against existing files or data, it is prohibited regardless of syntax or length. This includes using `echo` or `printf` for section headers, labels, separators, or banners, and chaining `echo`/`printf` with other commands (via `&&`, `;`, or `|`) to assemble labeled or multi-section output. Run each program on its own and let its real output stand.

`echo` and `printf` are permitted only as the entire command, to pass or inspect a single value (for example `echo "$VAR"`). They are never one segment of a chain, and never a tool for authoring output.

## Prohibited forms

These are specific cases of the principle above, not an exhaustive list:

- Heredocs and here-strings: `cat <<EOF`, `cat <<'EOF'`, `cat <<-"EOF"`, `<<<`, and similar syntax
- Inline interpreters carrying source: `python -c '...'`, `python <<'PY'`, `node -e ...`, `perl -0pi -e ...`, `ruby -e ...`, `awk '... { ... }' file > file.tmp`
- Inline cat with redirection: `cat <<EOF > file`, `cat >file <<EOF`, and similar heredoc redirection
- Piping literal multi-line content into an interpreter: `sh <<'SCRIPT'`, `bash <<EOF`, `envsubst <<EOF`
- Using `echo`, `printf`, `tee`, or `sed` to author content or format output: quoted newlines, `\n` escapes, chained `>>` appends, or label chains like `echo "=== a ===" && cmd && echo "=== b ===" && cmd`
