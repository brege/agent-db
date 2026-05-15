---
title: Code  
override: true  
---

# Code

## Strictness
- Validate at entry points only (APIs, file reads, user input, untrusted data)
  - Use schema libraries (e.g. pydantic) whenever possible
  - When expectations are violated, throw or error, don't log and continue
- Inside the system, assume contracts hold--don't add defensive checks mid-function
- Don't wrap internal calls in try-catch: let exceptions propagate unless you can recover

## Naming
- Prefer conciseness and clarity over verbosity or ambiguity
  - `config` not `configuration`
  - `get_defaults()` not `get_default_values()`
  - don't let verbiage bury math and logic
- Filenames: one word when unambiguous, two only when necessary

## Comments
- Required for: regex patterns, complex recursion, multi-step data transformations
- Avoid: past tense verbs, end-of-line comments, change history

## File Operations

- Prefer editing an existing file to creating a new one
- Only create files when absolutely necessary for achieving the goal

## Code Comments
- Comments are required for: regex patterns, complex recursion, multi-step data transformations, non-obvious algorithms
- Don't comment out code - remove it instead
- Don't add comments describing the process of changing code
  - Comments should not include past tense verbs like "added", "removed", "changed"
  - Example of what to avoid: `// Changed to handle edge case`
- Don't add comments that emphasize different versions of code
  - Example of what to avoid: `// This code now handles...`
- Avoid end-of-line comments - place comments above the code they describe
- Remove debugging comments and instrumentation before finishing

## Backward Compatibility

- Avoid backward-compatibility hacks
  - Don't rename unused variables with underscores (`_var`)
  - Don't re-export types just to maintain old names
  - Don't add `// removed` comments for deleted code
  - If something is unused, delete it completely

## Code Practices

- Use long flag names: `--message` not `-m`
- Document any non-trivial command or transformation
- Prefer existing libraries over reimplementation
  - When multiple options exist, present them with pros/cons and specific use cases
  - Flag dependencies (size, maintenance status) when recommending
- Remove debugging comments before finishing
