# git_hygiene Untracked Cleanup Spec

## Status

Closed on 2026-03-01 after the targeted `git_hygiene` update shipped and passed the required validation matrix.

Implemented result:
- `git_hygiene.sh --apply` now allows untracked-only state
- staged changes still block with exit `2`
- tracked unstaged changes still block with exit `2`
- unresolved conflict state still blocks with exit `2`
- real untracked checkout/update conflicts fail clearly and safely with exit `2`
- worktree-locked branch deletion remains warn-and-skip
- main fast-forward behavior remains safety-first
- remote feature branch deletion is still not guaranteed and was not added here

## Goal

Make post-merge cleanup usable when a repo contains harmless local untracked files.

Current pain point:
- `git_hygiene.sh --apply` refuses to run on any untracked files
- real users may keep harmless local files that are not meant to be committed
- this forces stash/move/restore ceremony just to finish cleanup after merge

Desired outcome:
- post-merge cleanup should proceed with untracked files when they do not create a real checkout or update conflict
- tracked/staged dirty state must remain blocking

## Scope

Files allowed to change in the implementation:
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_hygiene.sh`
- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/agent/git-publish-current-state.md`

## Non-Goals

Do not include these in this spec:
- redesign of publish flow
- remote feature branch deletion automation
- new long-lived commands or a new cleanup subsystem unless strictly required
- broader `git-publish` policy enforcement changes unrelated to hygiene

## Keep These Invariants

- explicit `--repo` remains required
- dry-run remains read-only
- `--apply` still fetches/prunes before deletion decisions
- remotes are still auto-detected the same way unless a minimal fix requires otherwise
- gone branches are still recomputed after fetch/prune
- current branch is never deleted
- `main` is never deleted
- worktree-locked branch deletion remains warn-and-skip
- main fast-forward behavior remains safety-first

## Required Behavior Change

### 1. Dirty-state model

Replace the current blanket rule:
- any porcelain output blocks `--apply`

With this model:
- staged changes: blocking, exit `2`
- tracked unstaged changes: blocking, exit `2`
- unresolved merge/conflict state: blocking, exit `2`
- untracked files only: allowed to proceed

Implementation does not need a complex repo-state engine.
A simple, deterministic parse of `git status --porcelain=v1` is enough.

## 2. Untracked-file behavior

Untracked files must be treated as harmless local state by default.
They should not block:
- fetch/prune
- switching to `main`
- fast-forwarding `main`
- local stale branch cleanup

unless they create a real checkout/update conflict.

## 3. Real conflict behavior

If untracked files would be overwritten or otherwise prevent checkout/update:
- stop `--apply` with exit `2`
- print a clear message that cleanup is blocked by an actual untracked-file conflict
- do not continue with branch deletion after such a conflict

The message should make the distinction explicit:
- harmless untracked files are allowed
- this run failed because a real checkout/update conflict exists

## 4. Main update semantics

Keep the current main-update intent:
- if local `main` exists, try to move to `main`
- prefer `branch.main.remote` + `branch.main.merge`
- fallback to `<selected-remote>/main`
- use fast-forward only

Behavior rules:
- non-fast-forward pull failure remains warning-only and cleanup may continue
- checkout blocked by another worktree remains warning-only and cleanup may continue
- checkout or update blocked by an actual untracked-file conflict becomes a hard failure for this run

## 5. Branch cleanup semantics

After refresh:
- recompute gone local branches
- delete only local `[gone]` branches
- never delete `main`
- never delete the current branch
- if a branch is locked in another worktree: warn and skip

If the run hits an actual untracked-file conflict before cleanup can safely continue:
- abort without deleting branches

## 6. Dry-run expectations

Dry-run should remain inspection-only and should succeed even when untracked files exist.

It should still show:
- repo status
- selected remote
- gone local branches
- no mutation happened

No fetch/prune or deletion in dry-run.

## 7. Docs update requirements

`/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md` must be updated to say:
- hygiene is the standard post-merge cleanup step
- harmless untracked files do not block hygiene by themselves
- tracked/staged changes still block hygiene
- real checkout/update conflicts from untracked files still block hygiene

Do not claim that remote feature branch deletion is guaranteed.
That remains out of scope here.

## Validation Expectations

Minimum validation matrix:

1. Dry-run with untracked-only state: succeeds, no mutation
2. Apply with untracked-only state and no conflict: succeeds
3. Apply with tracked unstaged change: exits `2`
4. Apply with staged change: exits `2`
5. Apply with untracked-file checkout/update conflict: exits `2` with clear message
6. Apply with worktree-locked branch deletion target: warn + skip, do not fail whole run
7. Main fast-forward still works when remote `main` advanced
8. Remote branch deletion remains out of scope and is not falsely claimed in docs

## Acceptance Criteria

This spec is satisfied when:
- a merged PR repo with harmless local untracked files can complete post-merge hygiene without stash gymnastics
- tracked/staged dirty state still blocks `--apply`
- actual untracked checkout/update conflicts are clearly reported and stop the run safely
- docs describe the new hygiene contract accurately

## Notes For Implementer

Keep this minimal.
This is a cleanup-ergonomics fix, not a redesign.
