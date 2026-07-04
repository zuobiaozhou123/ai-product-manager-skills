# AI Product Manager Skills

This repository collects practical AI workflows, Codex skills, and lightweight project templates for AI product managers.

The goal is not to store chat history. The goal is to turn repeatable product thinking, requirement writing, and delivery workflows into reusable assets that an AI agent can execute consistently.

## Current Skills

| Skill | Purpose | Status |
| --- | --- | --- |
| `ai-pm-prd-writer` | Turn rough product ideas, notes, screenshots, or meeting context into a structured PRD draft with assumptions, open questions, and acceptance criteria. | Draft v0.1 |

## Repository Structure

```text
.
├── README.md
├── docs/
│   ├── publishing-workflow.md
│   └── skill-design-template.md
├── skills/
│   └── ai-pm-prd-writer/
│       └── SKILL.md
└── examples/
    └── ai-pm-prd-writer-example.md
```

## How To Use This Repository

Use this repository as a portfolio and working library:

1. Start from a product-management workflow that repeats often.
2. Describe who uses it, what input they provide, and what output they expect.
3. Turn the workflow into a concise `SKILL.md`.
4. Add one example under `examples/`.
5. Commit and push the update to GitHub.

## Skill Quality Standard

Each skill should be:

- Specific enough to trigger in the right situations.
- Short enough that an AI agent can load it without wasting context.
- Operational, with clear steps and output expectations.
- Honest about assumptions, missing information, and risks.
- Useful to a product manager who may not write code.

## Owner

Created for `zuobiaozhou123` as a public AI product-management skill library.
