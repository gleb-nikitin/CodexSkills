# git-publish Current State

## Purpose

Current source-of-truth context for the shared `git-publish` skill.

Use this file when another agent needs the current behavior without reading historical specs, handoff notes, or review iterations.

## Scope

- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_publish.py`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/log_since_last_push.py`

## Current Workflow

1. `prepare`
2. user review
3. `publish`
4. after merge, run hygiene apply

`prepare` is read-only.

`publish` is the only mutating step.

## Commands

PR mode:
- `scripts/run prepare pr --repo /abs/path --topic <slug>`
- `scripts/run publish pr --repo /abs/path --plan /tmp/git-publish-plans/<token>.json`

No-PR mode:
- `scripts/run prepare no-pr --repo /abs/path`
- `scripts/run publish no-pr --repo /abs/path --plan /tmp/git-publish-plans/<token>.json`

Legacy compatibility still exists:
- `scripts/run pr --repo /abs/path --topic <slug>`
- `scripts/run pr --repo /abs/path --dry-run`
- `scripts/run no-pr --repo /abs/path`

Operational rule:
- new agent work should use only `prepare -> review -> publish`
- legacy one-shot commands are compatibility only
- workspace root `/Users/glebnikitin/work` must never be used as `--repo`
- direct push to default branch requires explicit user request

## Current Guarantees

- one publish action = one normal commit
- no standalone marker-only commit
- explicit staging only
- drift checks before mutation
- PR URL returned in output
- rollback hint returned in output
- low-noise successful output

## Current Prepare Behavior

`prepare` reports:
- included files
- excluded files
- exclusion reasons
- base branch
- target branch
- commit message
- PR title
- log path
- plan path

Untracked policy:
- suspicious paths like `.env`, `.pem`, `.key` -> `excluded-unclear`
- most ordinary untracked files -> `excluded-untracked`
- untracked directories -> `excluded-untracked` without recursive expansion
- only narrow safe text/code/doc files are auto-included

`prepare` also freezes pre-publish log context into the plan so the publish-time success marker does not erase PR body context.

## Current Publish Behavior

`publish`:
- validates that the requested CLI repo and mode still match the approved plan
- verifies repo state against the saved plan
- stages only approved included paths
- appends the success marker before commit
- keeps that marker inside the same main publish commit
- pushes and creates PR in PR mode
- uses frozen `plan["log_context"]` when building the PR body

## Current Post-Merge Protocol

After the user confirms the PR was merged:
- verify merge happened
- require a clean working tree
- run `scripts/git_hygiene.sh --repo <repo> --apply`
- report final local branch state

Current guaranteed local result:
- checkout on `main`
- local `main` updated to `origin/main`
- stale refs pruned
- local gone branches removed

Current limitation:
- remote feature branch deletion on GitHub is not guaranteed by current hygiene behavior
- that depends on GitHub auto-delete branch settings or future dedicated cleanup logic

Success marker format:
- `YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success`

## Rollback Guidance

Publish output includes this rollback hint:
- merge commit rollback: `git revert -m 1 <merge_commit_sha>`
- direct single-commit rollback: `git revert <commit_sha>`

## Current Limits

- plan files are stored in `/tmp/git-publish-plans`
- safe untracked allowlist is intentionally narrow and heuristic
- untracked directories are reported and excluded, not expanded for nested review
- legacy one-shot mode still exists only for compatibility and should not be the default agent path
- remote feature branch deletion after merge is not yet part of the guaranteed automated result

## Operational Recommendation

If a user says: "new skill, take it into work", an agent should be able to work from `git-publish/SKILL.md` alone.

This file exists only as compact maintainer context.
