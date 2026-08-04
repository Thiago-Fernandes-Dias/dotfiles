---
name: commit
description: Create a git commit
---

Create git commits with all current changes. First run `git status` and `git diff --staged` to review the current state. Prefer atomic commits with few changes: if the working tree contains many changes, split them into multiple commits, one per logical change, each with a short, descriptive message. Stage and commit each group of changes separately. Write clear, concise commit messages following a Conventional Commits format. If there is a CONTRIBUTING.md or similar docs specifying commit conventions, follow those instead. Run `git diff --staged` once more to confirm the staging area looks correct, then commit each batch. Finally, push to the appropriate remote (e.g. `git push origin main`). If the remote or branch is ambiguous, ask which remote/branch to push to.
