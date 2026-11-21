---
description: Inspect Git changes, propose atomic commits, and commit only after approval
---
Plan and, only after explicit approval, create coherent whole-file commits in the current repository. Follow applicable repository instructions. Do not change file contents as part of this workflow.

## Inspect

Run this read-only snapshot in one shell tool call. If outside a Git repository, stop.

```bash
cd "$(git rev-parse --show-toplevel)" &&
printf '\n--- Repository ---\n' && pwd &&
printf '\n--- Status ---\n' && git status --short --branch --untracked-files=all &&
printf '\n--- Unstaged ---\n' && git diff --no-ext-diff --stat &&
printf '\n--- Staged ---\n' && git diff --no-ext-diff --cached --stat &&
printf '\n--- Untracked ---\n' && git ls-files --others --exclude-standard &&
printf '\n--- Recent commits ---\n' &&
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  git log -5 --format='%h %s'
else
  printf 'No commits yet.\n'
fi
```

Then inspect the actual staged/unstaged diffs and relevant untracked contents; statistics alone are insufficient. Batch related inspection commands when practical. Stop for conflicts or an in-progress merge, rebase, cherry-pick, or revert. If nothing changed, say so and stop.

## Propose and wait

Group files by purpose, including related tests and documentation. Prefer a few coherent commits; never split a file across commits. Account for every changed path: assign it to one commit or explicitly list it as excluded. Flag suspected secrets and questionable generated/binary files rather than including them silently.

Use Conventional Commits with an imperative subject: `feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, `docs: ...`, or `chore: ...`. Use a scope only when helpful.

Example proposal:

```text
1. refactor(routing): use explicit collection routes
   - src/routes/collection/$writingType.tsx (delete)
   - src/routes/collection/blog.tsx (add)
   - src/components/Header.tsx
2. docs: explain collection routing
   - docs/architecture.md
Excluded: .local-notes.txt (personal notes)

Confirm these commits, or tell me what to regroup or rename.
```

Do not stage or commit yet. Feedback revises the proposal; only clear authorization approves it. If a file is partially staged, disclose that the proposal includes its entire current contents. If existing staging conflicts with the proposed grouping, explain the conflict and resolve the plan with the user; never silently unstage their work.

## Commit after approval

Recheck status and diffs against what you reviewed. If changes affect the approved plan, inspect them and request renewed approval. Work from the repository root and quote all paths safely; use literal Git pathspecs for filenames containing metacharacters.

Before each commit, ensure no staged changes fall outside that commit's approved paths. Never include unrelated staged changes or silently alter the user's staging to fix this. Stage only the explicit approved paths, including deletions and both sides of renames:

```bash
git add -- path/to/file-a path/to/file-b &&
git commit -m "refactor(scope): simplify the relevant behavior"
```

Execute commits sequentially, checking each result before continuing. Stop on any failure, including hook/signing failures; report what succeeded. Do not bypass hooks, disable signing, amend, reset, discard changes, or push. Do not use repository-wide `git add .` or `git add -A`.

Finish with the created commit hashes/messages and remaining working-tree status. Report verification performed or skipped; do not claim unrun checks passed.
