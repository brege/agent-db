---
title: Documentation  
override: true  
---

# Documentation

## Authorization

- Do not create or proactively edit documentation files unless the user explicitly requests documentation work.
- A direct request to revise a named document authorizes edits to that document. It does not authorize changes to code, generated contracts, tests, or other documentation.
- In a read-only review, report proposed documentation revisions without editing files.

## Stale Documentation

- Always identify stale documentation. When code contradicts a document, name the document, quote the stale claim, and cite the code that disproves it.
- Do not silently leave stale maintained documentation in place.
- Do not silently rewrite stale documentation outside the authorized scope. Propose the corresponding update and wait for approval.

## Register and Accuracy

- Apply the encyclopedic register defined by the communication instructions. Preserve technical depth while naming components, operations, conditions, and consequences literally.
- Ground each claim about behavior in the code that defines it, such as a function, module, environment variable, schema, public type, generated contract, or maintained architecture record.
- Use implementation inspection to validate or correct the assigned documentation. Do not enlarge the document with implementation detail merely because the detail is true.
- Preserve the source document's level of abstraction unless correctness or retrieval requires a change. A reference rewrite should not become a call-by-call implementation narrative.
- Distinguish source fidelity from implementation accuracy. A faithful rewrite can preserve a stale source claim. A code-supported addition can still exceed the assigned document's scope.
- Do not describe data or behavior as owned, authored, known, or judged by software when a literal operation conveys the relationship. State which component supplies, constructs, validates, stores, or renders the value.
- Describe an operation with its concrete subject and verb. Name the exact symbol, type, value, or participant when that name improves the explanation.
- Use section headings that identify the documented entity, operation, condition, or reader task.
- Distinguish a control from the conclusion it supports. State the narrow conclusion established by the evidence instead of inferring broader safety or correctness.

## Scope

- Add a detail only when it corrects a stale claim, supplies a condition needed to use the documented behavior, resolves an ambiguity, or supports an existing reader task.
- Preserve the document's title, metadata, identifiers, numeric values, examples, warnings, and complete link destinations unless the task or implementation evidence requires a specific change.
- Leave effective text unchanged when revision would serve only stylistic uniformity.

## Reference Organization

- Organize maintained reference documentation for lookup. Give an independently configurable subject its own subsection when it has settings, conditions, exceptions, or failure behavior.
- Use an overview table only when readers need to compare subjects across the same fields. Treat the table as an index. Following prose must add a condition, precedence rule, exception, consequence, or implementation distinction instead of repeating the table.
- Use tables for genuinely repeated fields. Distinguish defaults, requirements, accepted values, examples, and purposes. Do not place these meanings under one ambiguous heading.
- State a default only when the source or an authorized implementation contract identifies it as a default. An example, optional value, current assignment, missing value, or `None` annotation is not a default.
- Use prose for causal relationships, precedence rules, limitations, and operational distinctions that do not fit concise table cells.
- Use lists only when the complete items are parallel in purpose and level of detail.

## Policy Explanations

- A policy explanation identifies its human audience, subject, rationale, and operative instruction sources.
- Keep mandatory coding-agent directives in the instruction sources loaded during work. Do not replace required agent context with a link to human-facing rationale.
- When a policy explanation and its operative instruction sources disagree, report the disagreement and obtain a maintainer decision instead of selecting one silently.

## Document Refinement

- Review the explicitly maintained document for language, presentation, and implementation accuracy.
- Identify language and presentation issues, fix them in place, validate revised claims against current code, and correct supported inaccuracies within the authorized document.
- When the implementation and intended public contract genuinely disagree, cite both and record the remaining maintainer decision instead of inventing a resolution.
