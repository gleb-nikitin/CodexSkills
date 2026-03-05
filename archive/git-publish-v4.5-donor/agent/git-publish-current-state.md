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

Accepted explicit protocol set:
1. `комит`
2. `ребейз`
3. `пуш`
4. `мердж дан`

Accepted user-facing publish cycle:
1. `пуш`
2. PR is created immediately
3. user reviews and merges PR
4. `мердж дан`
5. agent confirms final state

The publish cycle has now been repeated successfully across multiple real production-like runs.
The current update keeps that healthy `пуш` behavior and adds explicit local-only and post-merge-only boundaries around it.

## Current Workflow

Current protocol split:
1. `комит`: exact-classifier local checkpoint
2. `ребейз`: deterministic local unpublished-history rewrite only
3. `пуш`: self-authorizing internal `prepare -> publish -> report` for either worktree changes or saved local unpublished commits
4. `мердж дан`: verify merged PR, run hygiene, append merge confirmation log line

`prepare` is read-only.

`publish` is the only mutating publish step.

`комит`, `ребейз`, and `мердж дан` must not call `publish`.

## Commands

Local checkpoint:
- `scripts/run commit --repo /abs/path`
- `scripts/run комит --repo /abs/path`

Local history cleanup:
- `scripts/run rebase --repo /abs/path`
- `scripts/run ребейз --repo /abs/path`

PR mode:
- `scripts/run push pr --repo /abs/path --topic <slug>`
- `scripts/run prepare pr --repo /abs/path --topic <slug>`
- `scripts/run publish pr --repo /abs/path --plan /tmp/git-publish-plans/<token>.json`

No-PR mode:
- `scripts/run push no-pr --repo /abs/path`
- `scripts/run prepare no-pr --repo /abs/path`
- `scripts/run publish no-pr --repo /abs/path --plan /tmp/git-publish-plans/<token>.json`

Post-merge completion:
- `scripts/run merge-done --repo /abs/path`
- `scripts/run мердж дан --repo /abs/path`

Legacy compatibility still exists:
- `scripts/run pr --repo /abs/path --topic <slug>`
- `scripts/run pr --repo /abs/path --dry-run`
- `scripts/run no-pr --repo /abs/path`

Operational rule:
- new agent work should use the explicit protocol that matches the user's command
- for `пуш`, the default agent path is self-authorizing internal `prepare -> publish -> report`
- `пуш` may publish saved local unpublished commits even when the worktree is clean
- legacy one-shot commands are compatibility only
- workspace root `/Users/glebnikitin/work` must never be used as `--repo`
- direct push to default branch requires explicit user request

## Current Guarantees

- `комит` and `пуш` share the exact same classifier
- `комит` creates at most one local `wip: local checkpoint` commit and never pushes
- `ребейз` rewrites only local unpublished commits and never publishes them
- one publish action = one normal commit
- no standalone marker-only commit
- explicit staging only
- drift checks before mutation
- `publish` validates requested CLI repo and mode against the loaded plan
- PR URL returned in output
- rollback hint returned in output
- low-noise successful output
- legacy one-shot returns clean no-op success when nothing is includable
- `мердж дан` appends one tracked `merge-confirmed ...` line after hygiene and intentionally leaves that tracked log delta in the worktree

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

Boundary with local commit history:
- standalone `prepare` still reports only worktree-based include/exclude state
- self-authorizing `пуш` now has a second path for clean worktrees with local unpublished commits
- in that case it derives publish scope from the local unpublished commit range on the current branch, then re-applies the exact classifier to those changed paths before publishing
- excluded paths from that classifier are restored out of the PR branch before the single publish commit is created
- when that publish source branch is the default branch, local default-branch state is realigned to the base after the PR branch is created so `мердж дан` can still finalize cleanly later

## Current `комит` Behavior

`комит`:
- reuses the exact current classifier without mutation first
- refuses staged index inheritance, detached HEAD, and unresolved conflicts
- prints included files, excluded files with reasons, and the fixed message `wip: local checkpoint`
- stages exactly the included paths
- creates exactly one local commit or returns a clean no-op when nothing is includable
- does not push, open a PR, or write tracked project-log lines

## Current `ребейз` Behavior

`ребейз`:
- refuses detached HEAD, the default branch, staged index content, tracked unstaged changes, and unresolved conflicts
- computes the protected boundary from `@{u}` when available, otherwise from the merge-base with the default branch
- rewrites only commits reachable from `HEAD` and not reachable from that protected boundary
- supports only deterministic non-interactive reword-or-squash behavior
- restores the original `HEAD` on rewrite failure

## Current Post-Merge Protocol

`мердж дан` now owns the standard post-merge completion step.

After the user confirms the PR was merged:
- resolve the most recent successful publish marker from the active project log
- require that marker to be `mode=pr`
- resolve the exact publish commit that introduced that marker line in the tracked project log
- verify the exact PR identified by `branch=<anchor_branch>`, `base=<anchor_base>`, and that publish commit SHA
- require no staged changes, no tracked unstaged changes, and no unresolved conflicts
- harmless local untracked files may remain unless they create a real checkout/update conflict
- run `scripts/git_hygiene.sh --repo <repo> --apply`
- if needed, remove leftover feature branch tails locally and remotely
- append one tracked `merge-confirmed ...` line to the active project log
- confirm final state and report that the remaining tracked delta is intentional

Standard final-state checklist:
- current branch is `main`
- local `main == origin/main`
- no leftover feature branch locally
- no leftover feature branch remotely unless best-effort deletion could not confirm it
- working tree may remain dirty only at the active tracked project log path by design

Current guaranteed local result when hygiene can run cleanly:
- checkout on `main`
- local `main` updated to `origin/main`
- stale refs pruned
- local gone branches removed
- project log appended with merge confirmation after hygiene success

Current limitation:
- harmless untracked files are allowed only when they do not block checkout or fast-forward update
- a real untracked-file checkout/update conflict still stops the run safely
- remote feature branch deletion on GitHub is not guaranteed by current hygiene behavior alone
- GitHub auto-delete branch settings or manual deletion may still be needed
- exact merged-PR verification still depends on GitHub lookup being available through `gh` auth or the API token fallback
- part of the newest operator intent still lives only in `agent/` maintainer context rather than in `SKILL.md`; this should be corrected in a future update so external agents can rely on `SKILL.md` alone
- `agent/` files still carry some procedural GitHub protocol guidance that should eventually move out of maintainer context and back into `SKILL.md`
- `push no-pr` is still inconsistent with PR mode for clean-worktree publish-from-local-commits; treat that as deferred protocol debt, not as final intended behavior

Known next-fix candidate:
- commit-range `push` is rename-aware and now refuses classifier-conflicting renames instead of silently degrading into deletes or partial publish output
- `комит` and `пуш` now work with a named point; explicit user naming wins, otherwise the agent derives a meaningful name from recent milestones and reports what name it used
- future intent: derived point naming should compress that meaning into a short human-usable summary automatically, without requiring the user to rename the point manually

Most recent production feedback:
- `git-publish` is now considered healthy in real use
- tracked and normal repo-wide change sets work through the full cycle repeatedly
- one normal PR commit, merge, cleanup, and final one-branch state are now repeatable
- remaining issues are polish, not fundamental workflow failures
- `пуш` is now intended to be self-authorizing, with user review happening on the PR before merge
- saved local checkpoint commits can now be published through `пуш` without requiring a dirty worktree
- if the only tracked delta between `комит` and `пуш` is the active tracked project log path, `пуш` now auto-checkpoints that log locally before PR-branch checkout instead of failing on overwrite protection
- `autocheckpoint: applied` in push output means that local pre-publish checkpoint of the active tracked project log was created and kept only on source-branch local history
- clarified user intent: `push` is supposed to publish only the latest safepoint. If newer includable worktree changes exist after that safepoint, they are not part of the publish candidate and must remain local.
- next protocol tightening: `push` should report clearly when newer local worktree changes exist outside the last safepoint, so omission from the PR is explicit rather than surprising.

Success marker format:
- `YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success`

Merge confirmation marker format:
- `YYYY-MM-DD HH:MM | git-publish skill | merge-confirmed branch=<anchor_branch> base=<anchor_base> | user confirmed merged; hygiene=applied; remote_branch=<gone|present|unknown>`

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
- remote feature branch deletion after merge is not yet part of the guaranteed automated result inside `git_hygiene` itself
- `ребейз` intentionally supports only deterministic reword-or-squash cleanup, not generic interactive rebase features
- `мердж дан` intentionally leaves one tracked log delta after success and that is not an incident

## Operational Recommendation

If a user says: "new skill, take it into work", an agent should be able to work from `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md` alone.

This file exists only as compact maintainer context.
