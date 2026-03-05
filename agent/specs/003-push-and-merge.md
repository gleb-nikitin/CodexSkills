# Spec 003: push pr, push no-pr, merge-done (as built)

- status: completed
- accepted_on: 2026-03-05

## Context

Spec 002 delivered local `commit` safepoints. Spec 003 completed the publish cycle in `git-publish/scripts/run`:
- publish via PR (`push pr`)
- direct initial push (`push no-pr`)
- post-merge cleanup (`merge-done`)

During validation and follow-up bugfixes, two safety behaviors were finalized:
1. clean-worktree checks ignore paths that `exclude_reason()` would exclude.
2. merge cleanup refuses if local `main` moved past the published cycle when anchor SHA is available.

## Deliverables

| File | Action |
|------|--------|
| `git-publish/scripts/run` | Added `push pr`, `push no-pr`, `merge-done`; shared top-level parsing/validation; cycle anchor + guards |
| `git-publish/SKILL.md` | Removed "Not yet implemented" markers for `push pr`, `push no-pr`, `merge-done` |

## As-Built Behavior

### Shared parsing and validation

`run` now parses at top-level and dispatches actions:
- `run commit --repo /abs/path [point words...]`
- `run push pr --repo /abs/path [--topic <slug>]`
- `run push no-pr --repo /abs/path`
- `run merge-done --repo /abs/path`

Common guards:
- `--repo` required, absolute, existing, git dir, not workspace root.
- Usage errors exit `2`; runtime errors exit `1`.

### Clean-worktree guard semantics

`require_clean_worktree()` scans `git status --porcelain` and ignores entries that `exclude_reason()` marks as excluded (`.DS_Store`, `.env*`, editor temps, etc.).

Result:
- only includable changes block `push`/`merge-done`.
- excluded-only trees no longer produce false dirty errors.

### `push pr`

Flow:
1. require on `main`.
2. require clean worktree (includable changes only).
3. require `origin/main` exists.
4. if `origin/main..HEAD` is empty: print `nothing to push`, exit `0`.
5. resolve branch: `publish/<topic>` or `publish/<short-sha>`.
6. create/push branch.
7. create PR via `gh pr create --base main --head <branch> --title <head-subject> --body ""`.
8. write anchor file `.git/git-publish-anchor`.
9. checkout `main`.
10. print:
   - `pushed <branch>`
   - `pr: <url>`
   - `pr-number: <number>`
   - `sha: <short-sha>`

Error behavior:
- push failure exits `1` (git error surfaces).
- if branch push succeeded but `gh` missing/auth/PR create fails, exits `1` with explicit "branch was pushed" message.

### Anchor format

Anchor path: `$REPO/.git/git-publish-anchor`
- line 1: PR number
- line 2: published full HEAD SHA

Backward compatibility:
- old one-line anchors remain valid for `merge-done` (PR number only).

### `push no-pr`

Flow:
1. require on `main`.
2. require clean worktree (includable changes only).
3. `git push -u origin main`.
4. print:
   - `pushed main`
   - `sha: <short-sha>`

### `merge-done`

Flow:
1. require on `main`.
2. require clean worktree (includable changes only).
3. require anchor file.
4. read PR number (line 1) and optional published SHA (line 2).
5. `git fetch origin`.
6. if published SHA exists and current `HEAD` differs: refuse with
   `local main has commits after the published cycle; commit or stash before merge-done`.
7. verify PR state via `gh pr view <number> --json state --jq '.state'` == `MERGED`.
8. resolve exact branch via `gh pr view <number> --json headRefName --jq '.headRefName'`.
9. `git reset --hard origin/main`.
10. delete only anchored branch locally (if present) and remotely (best-effort).
11. remove anchor file.
12. print:
   - `verified: pr #<number> merged`
   - `synced main <short-sha>`
   - `deleted: <headRefName>`

## Verification Summary

Validated in temp repos:
- `push no-pr` success path.
- dirty includable tracked change rejection.
- excluded-only files accepted by clean-worktree checks.
- `push pr` git-side publish and expected PR-creation failure on non-GitHub remote.
- `merge-done` refuses when no active cycle anchor.
- anchor SHA guard blocks `merge-done` when new commits appear on local `main` after `push pr`.
- one-line legacy anchor remains accepted (SHA guard skipped).

## Acceptance Criteria (final)

1. `push pr` publishes committed range `origin/main..HEAD` and opens PR via `gh`.
2. `push pr` supports `--topic` and default `publish/<short-sha>` naming.
3. `push pr` writes cycle anchor with PR number and published SHA.
4. `push no-pr` pushes `main`.
5. `merge-done` verifies the exact anchored PR is merged and resolves exact branch from PR metadata.
6. `merge-done` cleans only the anchored branch and syncs `main` to `origin/main`.
7. `merge-done` refuses missing anchor.
8. `merge-done` refuses if PR is not merged.
9. `merge-done` refuses if local `main` has commits after published cycle when anchor SHA is present.
10. one-line legacy anchors remain supported (skip SHA guard).
11. clean-worktree checks ignore excluded paths and still reject includable dirty changes.
12. operations do not write project logs.
