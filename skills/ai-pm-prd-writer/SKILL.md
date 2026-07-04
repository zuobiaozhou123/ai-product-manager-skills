---
name: ai-pm-prd-writer
description: Use when an AI product manager wants to turn rough product ideas, screenshots, meeting notes, user feedback, or existing context into a structured PRD draft, including problem framing, scope, user flows, requirements, acceptance criteria, assumptions, and open questions.
---

# AI PM PRD Writer

Create practical PRD drafts from incomplete product context. Optimize for clarity, decision-making, and execution, not formal document length.

## Workflow

1. Identify the product context:
   - Product or module name.
   - Target users.
   - User scenario.
   - Business or operational goal.
   - Known constraints.

2. Separate facts from assumptions:
   - Treat user-provided information as facts.
   - Mark inferred details as assumptions.
   - Do not invent data, metrics, policies, or technical dependencies.

3. Clarify only blocking gaps:
   - Ask questions only when the PRD would be materially wrong without the answer.
   - Prefer one concise question at a time.
   - If the gap can be handled as an assumption, proceed and list it.

4. Draft the PRD:
   - Background.
   - Problem statement.
   - Goals and non-goals.
   - Target users and scenarios.
   - User journey or workflow.
   - Functional requirements.
   - Edge cases and constraints.
   - Acceptance criteria.
   - Metrics or success signals.
   - Open questions.

5. Keep scope disciplined:
   - Separate MVP from later iterations.
   - Avoid turning a simple workflow into a large platform.
   - Call out expensive or risky requirements.

## Output Format

Use this structure unless the user asks for another format:

```markdown
# PRD: <Feature Or Module Name>

## Background

## Problem

## Goals

## Non-Goals

## Target Users

## User Scenarios

## Scope

### MVP

### Later Iterations

## Functional Requirements

## User Flow

## Edge Cases

## Acceptance Criteria

## Success Signals

## Assumptions

## Open Questions
```

## Quality Bar

- Write in plain product language.
- Make requirements testable.
- Avoid generic slogans.
- Keep every section tied to user value or execution clarity.
- If the input is too thin, produce a short product brief instead of pretending it is a complete PRD.
