---
name: git-best-practices
description: Enforce Conventional Commits, trunk-based branching, atomic PRs, rebase-over-merge hygiene, and structured review checklists. Use when committing code, creating branches, opening PRs, reviewing code, handling merge conflicts, or discussing Git workflow.
---

# Git Best Practices

## Quick start

**Commit format**: `<type>(<scope>): <subject>`

```
feat(auth): add JWT refresh token rotation
fix(api): handle null pointer in dashboard query
refactor(model): extract shared validation logic
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

## Commit conventions

- **Do not modify files before committing.** When the user says to commit, commit the working tree exactly as it is. Never edit, format, lint, or otherwise touch files after the commit instruction — even files you edited earlier in the session.
- **Subject line**: 50 characters max, imperative mood ("add" not "added"), no trailing period.
- **For small changes**: one-line commit only — the subject is enough.
- **For complex changes**: add a body explaining **what** changed and **why**.
  - Wrap body lines at 72 characters.
  - Reference related issues (e.g. `Closes #42`, `Refs #99`).
- **Atomic commits** — prefer commits with few changes: one logical change per commit. Never bundle unrelated work.
  - Each commit must be self-explanatory when read in isolation.
  - Each commit message should be short and descriptive.
  - **If the working tree has many changes**, do not cram them into one commit — make multiple commits, one per logical change, each with its own short, descriptive message.
- **Body separated** from subject by a blank line.
- **No WIP/merge commits on main** — squash or rebase before merging.

## Branching

### Strategy

Trunk-based: `main` is always deployable. Short-lived feature branches only.

### Naming

`<type>/<short-description>` (lowercase, hyphen-separated): `feat/jwt-refresh`, `fix/null-pointer`, `refactor/shared-validation`, `chore/update-deps`.

### Lifecycle

1. Branch from latest `main`.
2. Commit and push frequently.
3. Rebase onto `main` before opening a PR (never merge `main` into feature).
4. Squash-merge into `main` after approval.
5. Delete branch after merge.

## Pull requests

### Before opening

- [ ] Rebased onto latest `main` with no conflicts
- [ ] All new behavior covered by tests
- [ ] CI passes locally
- [ ] No debug logging, commented-out code, or untracked TODOs
- [ ] Self-reviewed diff line by line
- [ ] PR under ~400 lines changed (break larger changes into stacked PRs)

### Body template

**What** — brief description of the change and why. **How** — key decisions, tradeoffs. **Testing** — commands and scenarios to verify.

## Code review

### Checklist

- [ ] Code matches the PR description
- [ ] Edge cases and error states handled
- [ ] Tests are comprehensive and sensible
- [ ] Code follows codebase conventions
- [ ] No security concerns (injection, secrets exposure, auth bypass)
- [ ] No performance regressions (N+1 queries, blocking I/O)

### Conduct

- Request changes for bugs, design flaws, or convention violations.
- Use suggestions for style preferences.
- Approve once concerns are resolved — don't block on perfection.

## Rebase hygiene

Always rebase, never merge when updating from `main`:

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

- Resolve conflicts per-commit during interactive rebase.
- Squash fixup commits before review: `git rebase -i main`.
