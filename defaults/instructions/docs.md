---
title: Documentation  
override: true  
---

# Documentation

## Authorization

- Do not create or proactively edit documentation files unless the user explicitly requests documentation work.
- When a code change contradicts existing documentation, identify the affected document and propose the corresponding update instead of silently leaving stale instructions.

## Register and Organization

- Apply the encyclopedic register defined by the communication instructions. Preserve technical depth while naming components, operations, conditions, and consequences literally.
- Organize maintained reference documentation for lookup. Give an independently configurable subject its own subsection when it has settings, conditions, exceptions, or failure behavior.
- Use an overview table only when readers need to compare subjects across the same fields. Treat the table as an index. Following prose should add a condition, precedence rule, exception, consequence, or implementation distinction instead of repeating the table.
- Distinguish defaults, requirements, accepted values, examples, and purposes. Do not combine those meanings under one ambiguous table heading.
- Use prose for causal relationships, precedence rules, limitations, and operational distinctions that do not fit concise table cells.
- Use section headings that identify the documented entity, operation, condition, or reader task.

## Accuracy and Scope

- Ground each claim about behavior in the code, schema, public type, generated contract, or maintained architecture record that defines it.
- Distinguish source fidelity from implementation accuracy. A faithful rewrite can preserve a stale claim, while a code-supported addition can exceed the assigned document's scope.
- Do not enlarge a document with implementation detail merely because the detail is true. Add detail only when it corrects an inaccuracy, supplies a condition needed to use the documented behavior, resolves an ambiguity, or supports an existing reader task.
- Preserve the document's title, metadata, identifiers, numeric values, examples, warnings, and complete link destinations unless the task or implementation evidence requires a specific change.
- Leave effective text unchanged when revision would serve only stylistic uniformity.
