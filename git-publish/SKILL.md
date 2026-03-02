---
name: git-publish
description: Deterministic Git protocol split for solo repos in /Users/glebnikitin/work. Use when the user says 'комит', 'ребейз', 'пуш', 'git push', 'push', 'пуш без пр', 'push no pr', 'push without pr', or 'мердж дан'. Push is self-authorizing and internally runs prepare -> publish -> report; commit and rebase stay local-only; merge-done is verified post-merge cleanup plus tracked confirmation logging.
---

# git-publish

## Intent

Keep four explicit protocols separate:
- `комит`: one local checkpoint commit from the exact `prepare` classifier include set
- `ребейз`: deterministic cleanup of local unpublished history only
- `пуш`: self-authorizing `prepare -> publish -> report`
- `мердж дан`: verify the merged PR for the last PR-mode push, run hygiene, append one `merge-confirmed ...` project-log line

Do not infer one protocol from another.

## Core Rules

- Always pass `--repo /absolute/path/to/repo`.
- Never use workspace root `/Users/glebnikitin/work` as `--repo`.
- All mutating protocols refuse unresolved conflicts.
- `комит` and `пуш` must reuse the exact current `prepare` classifier.
- Manual pre-staging is never inherited. Clean-index refusal is mandatory where the protocol requires it.
- Never use `git add -A` or `git add .`.
- Stage explicit paths only.
- `пуш` is the only protocol allowed to publish, push, or open PRs.
- `комит` and `ребейз` never write tracked project-log lines.
- `мердж дан` appends a tracked `merge-confirmed ...` line after hygiene and intentionally leaves that one tracked log delta unstaged.

## Protocol Map

### `комит`

- Local only.
- Refuse on detached HEAD, staged index content, or unresolved conflicts.
- Run the current classifier without mutation.
- Resolve a named point first.
- If the user did not name the point, derive it from recent milestones / meaningful changes and report the chosen name.
- Show included files, excluded files with reasons, point name, and final message `wip: <point-name>`.
- Stage exactly the included paths and create exactly one local commit.
- If nothing is includable, return a clean no-op.

### `ребейз`

- Local only.
- Refuse on detached HEAD, the default branch, staged index content, tracked unstaged changes, or unresolved conflicts.
- Rewrite only commits that are local and unpublished relative to `@{u}` or, if no upstream exists, relative to the merge-base with the default branch.
- Supported model is deterministic only:
  - one local commit: non-interactive reword
  - multiple local commits: squash to exactly one new local commit
- Final message comes from the newest local commit with one leading `fixup! ` or `squash! ` prefix stripped.
- If nothing is rewriteable, return a clean no-op.

### `пуш`

- This remains the healthy publish workflow.
- `push` / `пуш` in `scripts/run` is self-authorizing.
- Default flow is internal `prepare -> publish -> report`.
- User review happens on the created PR before merge, not as an extra approval round after `prepare`.
- Direct push to the default branch remains allowed only when the user explicitly requests `пуш без пр` / `push no pr` / `push without pr`.
- Resolve a named point first. Explicit user naming wins; if no point name is provided, derive one from recent milestones / meaningful changes and report it.
- If a free-text point name conflicts with `--topic`, `--message`, or `--pr-title`, refuse clearly instead of guessing.
- If the only tracked delta before publish is the active tracked project log path, `пуш` auto-checkpoints that log locally on the current branch before PR-branch checkout instead of failing.
- `пуш` can publish saved local work from local unpublished commits even when the worktree is clean.
- In that clean-worktree case, `пуш` internally derives the publish scope from the local unpublished commit range on the current branch, re-applies the exact classifier to those changed paths, and still creates one normal PR commit.
- `autocheckpoint: applied` means `пуш` created a local checkpoint commit for the active tracked project log before continuing; that checkpoint stays local and must not pollute the PR branch.
- Commit-range planning is rename-aware. If a rename crosses classifier boundaries, `пуш` must refuse instead of silently degrading into a delete or partial publish.
- On a non-default branch, `пуш` may run internal normalization of local unpublished history before publishing. If it does, output must report that normalization ran and the local source branch remains in the normalized state after success.

### `мердж дан`

- Applies only when the most recent project-log success marker is `push mode=pr`.
- Resolve the anchor from that last marker: `branch=<anchor_branch> base=<anchor_base>`, then resolve the exact publish commit that introduced that marker line in the tracked project log.
- Refuse if the current branch before cleanup is neither the default branch nor `anchor_branch`.
- Verify exactly one matching GitHub PR for `head=anchor_branch`, `base=anchor_base`, and the resolved publish commit SHA, and require that PR to be merged.
- Require no staged changes, no tracked unstaged changes, and no unresolved conflicts before hygiene.
- If only tracked protocol-management delta is present under `agent/*.md`, `git-publish/SKILL.md`, `git-publish/scripts/git_publish.py`, or `git-publish/scripts/run`, `мердж дан` may create one safe local preflight checkpoint commit first instead of refusing immediately.
- Run the existing hygiene flow, ensure the default branch is current and synced, and ensure the local anchor branch is gone.
- Remote branch deletion is best-effort only.
- If that preflight checkpoint starts from `main`, any temporary checkpoint branch created for it must be removed locally before successful completion.
- Append exactly one line:

```text
YYYY-MM-DD HH:MM | git-publish skill | merge-confirmed branch=<anchor_branch> base=<anchor_base> | user confirmed merged; hygiene=applied; remote_branch=<gone|present|unknown>
```

- That final tracked log delta is intentional. Do not clean it away.

## Commands

Local checkpoint:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run commit --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run комит --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run комит --repo /absolute/path/to/repo close spec 6
```

Local history cleanup:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run rebase --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run ребейз --repo /absolute/path/to/repo
```

Push protocol:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run push pr --repo /absolute/path/to/repo --topic <slug>
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run push pr --repo /absolute/path/to/repo close spec 6
```

Optional inspection/debug entrypoints:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run prepare pr --repo /absolute/path/to/repo --topic <slug>
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run publish pr --repo /absolute/path/to/repo --plan /tmp/git-publish-plans/<token>.json
```

No-PR push:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run push no-pr --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run prepare no-pr --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run publish no-pr --repo /absolute/path/to/repo --plan /tmp/git-publish-plans/<token>.json
```

Post-merge completion:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run merge-done --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run мердж дан --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run мердж дан --repo /absolute/path/to/repo finalize protocol split
```

Legacy one-shot compatibility (kept temporarily):

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run pr --repo /absolute/path/to/repo --topic <slug>
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run pr --repo /absolute/path/to/repo --dry-run
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run no-pr --repo /absolute/path/to/repo
```

Do not use legacy one-shot commands for new agent work.

## What `prepare` Reports

`prepare` reports:
- included files
- excluded files
- exclusion reasons
- base branch
- target branch
- commit message
- PR title
- active log path
- plan path

Classifier rules:
- tracked modified/deleted/renamed files: included by default
- `.DS_Store`: `excluded-junk`
- suspicious untracked files like `.env`, `.env.local`, `.key`, `.pem`, `.p12`, `.pfx`: `excluded-unclear`
- untracked paths under `.claude/`: `excluded-local`
- untracked paths under `dist/`: `excluded-build`
- other untracked files: `excluded-untracked` by default
- new untracked directories are inspected recursively during `prepare`
- safe files discovered inside a new untracked directory are reported at file level and can be included without manual pre-staging
- only narrow safe text/code/doc files are auto-included, including `.gitignore`
- paths already hidden by Git ignore rules are not surfaced by `prepare`

`prepare` also freezes log context into the plan so the publish-time success marker does not erase PR body context.

## What `publish` Does

`publish`:
- loads the approved plan
- validates that the requested `--repo` and `--mode` still match the approved plan
- verifies repo state did not drift after `prepare`
- stages only approved explicit paths
- appends the success marker before commit
- creates one normal commit
- pushes branch or base
- creates PR in `pr` mode
- prints rollback guidance

If repo state drifted after `prepare`, publish must fail and require a fresh `prepare`.

Legacy one-shot compatibility:
- if legacy one-shot prepare finds no includable files, it should return a clean no-op success instead of failing in publish

Self-authorizing `push` compatibility:
- normal `push` may publish either:
  - current publishable worktree changes
  - or saved local unpublished commits from the current branch when the worktree is already clean
- in that clean-worktree local-commit path, excluded files from the exact classifier must still stay out of the PR commit
- rename-aware commit-range planning must refuse classifier-conflicting renames instead of publishing a degraded result
- if internal normalization runs on a non-default source branch, that local source branch remains in the normalized state after publish succeeds
- no extra approval round is required after that internal preparation

## After Merge Expectations

After successful hygiene inside `мердж дан`, the expected local result is:
- current branch is `main`
- local `main` is updated to `origin/main`
- stale remote refs are pruned
- local gone feature branches are removed

After that, `мердж дан` appends the required `merge-confirmed ...` line and intentionally leaves that one tracked log delta in the worktree.

Hygiene contract:
- harmless untracked files do not block hygiene by themselves
- staged changes still block hygiene
- tracked unstaged changes still block hygiene
- unresolved conflicts still block hygiene
- real checkout/update conflicts caused by untracked files still block hygiene safely

Important limitation:
- remote feature branch deletion on GitHub is not guaranteed by `git_hygiene.sh`
- in practice this depends on GitHub auto-delete branch settings or a separate manual/future automated step

## Success Marker

Success marker format:

```text
YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success
```

Failure markers may still be written on failed publish attempts.

## Output Expectations

Prepare output remains available for inspection/debug and plan-based workflows.

Publish output should include at least:
- mode
- repo
- base
- branch
- commit SHA
- included files
- log path
- PR URL in PR mode
- rollback hint

Rollback hint:
- merge commit rollback: `git revert -m 1 <merge_commit_sha>`
- direct single-commit rollback: `git revert <commit_sha>`

## Safety

Keep these protections:
- explicit staging only
- `gh` PR creation with API fallback
- drift check before mutation
- low-noise successful output
- append-only project log marker behavior
- no publish from workspace root
- no direct push to default branch without explicit user request

## Project Log

Project log path:
- prefer `./agent/log.md`
- fallback `./log.md`

Log lines used by this skill:

```text
YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success
YYYY-MM-DD HH:MM | git-publish skill | merge-confirmed branch=<anchor_branch> base=<anchor_base> | user confirmed merged; hygiene=applied; remote_branch=<gone|present|unknown>
```

## Helpers

- `scripts/run`: wrapper for `commit`, `rebase`, `prepare`, `publish`, and `merge-done`
- `scripts/git_publish.py`: core implementation
- `scripts/log_since_last_push.py`: log context helper
- `scripts/create_pr_gh.sh`: PR creation via `gh`
- `scripts/create_pr.py`: PR creation via GitHub API
- `scripts/git_hygiene.sh`: standard post-merge local cleanup step for this workflow
