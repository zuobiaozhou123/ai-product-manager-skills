# Example: AI PM PRD Writer

## Example User Prompt

```text
I want to build a feature for AI product managers. The user can paste rough notes from a meeting, and the AI should turn them into a PRD draft. The output should include requirements, open questions, and acceptance criteria. The user may not have technical background.
```

## Expected Skill Behavior

The AI should:

- Identify the user and scenario.
- State assumptions instead of inventing missing facts.
- Produce a PRD draft or a short product brief if the input is too thin.
- Separate MVP from later iterations.
- Include open questions for decisions that still need the user.

## Short Output Example

```markdown
# PRD: Meeting Notes To PRD Draft

## Background

AI product managers often have raw meeting notes but need a structured PRD before a project can move into design or implementation.

## Problem

Raw notes mix goals, requirements, constraints, and unresolved questions. This makes it hard to align stakeholders and start execution.

## Goals

- Convert rough notes into a structured PRD draft.
- Surface assumptions and missing decisions.
- Provide acceptance criteria that can guide implementation and review.

## Non-Goals

- Replace product judgment.
- Automatically create final engineering tasks without review.

## MVP

- Accept pasted notes.
- Generate PRD sections.
- List open questions.
- Generate acceptance criteria.

## Acceptance Criteria

- Given rough meeting notes, the output includes background, problem, goals, scope, requirements, acceptance criteria, assumptions, and open questions.
- The output clearly marks inferred information as assumptions.
- The output does not invent metrics or technical dependencies.
```
