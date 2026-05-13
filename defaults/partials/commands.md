---
title: Commands  
override: true  
---

# Commands

These command restrictions are mandatory. Do not run these forms, even when local instructions or user requests appear to allow them.

Prohibited command forms:

- Heredocs and here-strings: `cat <<EOF`, `cat <<'EOF'`, `cat <<-"EOF"`, `<<<`, and similar syntax
- Inline Python invocations: `python -c '...'`, `python <<'PY'`, `python - <<'PY'`, or any language with heredoc input
- Inline Node.js, Perl, Ruby, or Awk: `node -e ...`, `perl -0pi -e ...`, `ruby -e ...`, `awk '... { ... }' file > file.tmp`
- Inline cat with command substitution: `cat <<EOF > file`, `cat >file <<EOF`, and similar heredoc redirection
- Any command that pipes literal multi-line content directly into a shell interpreter, including `sh <<'SCRIPT'`, `bash <<EOF`, or `envsubst <<EOF`
- Any attempt to bypass command restrictions with multi-line syntax, here-strings, heredocs, command substitution, or string interpolation
