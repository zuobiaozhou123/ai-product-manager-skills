# Publishing Workflow

This workflow is for creating and publishing AI product-manager skills or project templates on GitHub.

## 1. Define The Asset

Before writing files, answer four questions:

- Who is the target user?
- What repeatable task should the AI perform?
- What input will the user provide?
- What output should the AI produce?

If the answer is still vague, write a short product brief before creating a skill.

## 2. Choose The Artifact Type

Use a skill when the value is a repeatable AI workflow.

Use a project template when the value is a folder structure, document pack, app prototype, or reusable implementation scaffold.

Use a product note when the idea is not ready for execution yet.

## 3. Create The Local Files

Recommended structure:

```text
skills/<skill-name>/SKILL.md
examples/<skill-name>-example.md
docs/<topic>.md
```

Keep `SKILL.md` focused on agent behavior. Put explanations, examples, and background into `docs/` or `examples/`.

## 4. Review Before Publishing

Check:

- The skill name is clear and lowercase with hyphens.
- The frontmatter has `name` and `description`.
- The description explains when the skill should be used.
- The body gives a concrete workflow.
- The output format is explicit.
- No secrets, private credentials, or unnecessary personal information are included.

## 5. Commit And Push

Use:

```bash
git status
git add .
git commit -m "Add <asset-name>"
git push
```

## 6. Iterate

After use, update the skill when one of these happens:

- The AI repeatedly asks the same avoidable clarification.
- The output structure is useful but inconsistent.
- A step depends on tacit knowledge that should be made explicit.
- A reference document would reduce repeated explanation.
