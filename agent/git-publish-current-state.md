# git-publish Current State

## Purpose

Current source-of-truth context for the shared `git-publish` skill.

Use this file when another agent needs the current behavior without reading historical specs, handoff notes, or review iterations.

## Scope

- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_publish.py`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/log_since_last_push.py`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_hygiene.sh`

## Accepted State

The serious publish-flow stabilization phase is complete.

Accepted user-facing cycle:
1. `prepare`
2. user review
3. `publish`
4. user merges PR
5. agent runs post-merge cleanup

This cycle was completed end-to-end successfully in production testing.

## Current Workflow

1. `prepare`
2. user review
3. `publish`
4. after merge, run hygiene apply

`prepare` is read-only.

`publish` is the only mutating publish step.

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
- `publish` validates requested CLI repo and mode against the loaded plan
- PR URL returned in output
- rollback hint returned in output
- low-noise successful output
- legacy one-shot returns clean no-op success when nothing is includable

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
- only narrow safe text/code/doc files are auto-included
- `.DS_Store` -> `excluded-junk`
- untracked paths under `.claude/` -> `excluded-local`
- untracked paths under `dist/` -> `excluded-build`
- new untracked directories are expanded recursively at file level during `prepare`
- safe files discovered inside a new untracked directory can be published without manual pre-staging
- paths already hidden by Git ignore rules are still not surfaced by `prepare`

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
- require no staged changes, no tracked unstaged changes, and no unresolved conflicts
- harmless local untracked files may remain unless they create a real checkout/update conflict
- run `scripts/git_hygiene.sh --repo <repo> --apply`
- report final branch state

Current guaranteed local result when hygiene can run cleanly:
- checkout on `main`
- local `main` updated to `origin/main`
- stale refs pruned
- local gone branches removed

Current limitation:
- harmless untracked files are allowed only when they do not block checkout or fast-forward update
- a real untracked-file checkout/update conflict still stops the run safely
- remote feature branch deletion on GitHub is not guaranteed by current hygiene behavior
- GitHub auto-delete branch settings or manual deletion may still be needed

Most recent production feedback:
- publish is now considered good enough in real usage for tracked change sets
- hygiene now tolerates harmless local untracked files without weakening tracked/staged safety checks
- the focused gap for new untracked project directories is now covered by recursive file-level planning and explicit `.claude` / `dist` / junk exclusions

Success marker format:
- `YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success`

## Rollback Guidance

Publish output includes this rollback hint:
- merge commit rollback: `git revert -m 1 <merge_commit_sha>`
- direct single-commit rollback: `git revert <commit_sha>`

## Current Limits

- plan files are stored in `/tmp/git-publish-plans`
- safe untracked allowlist is intentionally narrow and heuristic
- recursive untracked-directory review uses a small explicit exclusion model, not a full generic ignore engine
- only a few obvious local/build cases are explicitly named today: `.claude`, `dist`, and `.DS_Store`
- Git-ignored untracked paths are not listed, so `prepare` cannot attach an explicit exclusion reason to content Git already hides
- manual pre-staging is intentionally rejected by publish, so it cannot be used as a workaround
- legacy one-shot mode still exists only for compatibility and should not be the default agent path
- hygiene still stops when untracked files would be overwritten or removed by checkout/update
- remote feature branch deletion after merge is not yet part of the guaranteed automated result

## Operational Recommendation

If a user says: "new skill, take it into work", an agent should be able to work from `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md` alone.

This file exists only as compact maintainer context.
