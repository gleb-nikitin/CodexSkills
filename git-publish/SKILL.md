---
name: git-publish
description: Deterministic Git publish workflow for solo repos in /Users/glebnikitin/work. Use when the user says 'пуш', 'git push', 'push', 'пуш без пр', 'push no pr', or 'push without pr'. Default flow is prepare -> review -> publish with one normal commit.
---

# git-publish

## Intent

Create a low-noise publish flow that agents can use safely:
- review what will be committed
- create exactly one normal commit
- create a normal PR
- keep rollback guidance obvious

Default behavior: **prepare -> review -> PR publish**.

Exception: direct push to default branch only when the user explicitly requests `пуш без пр` / `push no pr` / `push without pr`.

## Core Rules

- Always pass `--repo /absolute/path/to/repo`.
- Never use workspace root `/Users/glebnikitin/work` as `--repo`.
- Always run `prepare` first.
- After `prepare`, show included/excluded files and wait for explicit user approval before `publish`.
- `prepare` is read-only.
- `publish` is the only mutating step.
- One publish action creates exactly one normal commit.
- No standalone `chore: git-publish marker` commit is allowed.
- Success marker is written into the same main publish commit.
- PR URL is returned in output, not written into the committed success marker.
- Never use `git add -A` or `git add .`.
- Stage explicit paths only.
- PR publish via this skill is allowed autonomously after user approval of the prepared plan.
- Direct push to the default branch is allowed only when the user explicitly requests `пуш без пр` / `push no pr` / `push without pr`.

## Recommended Agent Flow

1. Run `prepare`.
2. Show the user:
   - included files
   - excluded files and reasons
   - base branch
   - target branch
   - commit message
   - PR title
3. After approval, run `publish` with the returned `plan_path`.
4. Return:
   - commit SHA
   - PR URL
   - rollback hint

## Standard Workflow

### Phase 1: Publish

1. Run `prepare`.
2. Show included and excluded files to the user.
3. Wait for explicit approval.
4. Run `publish`.
5. Return the PR URL.

### Phase 2: After Merge

When the user confirms the PR was merged:

1. Verify the merge happened.
2. Require a clean working tree.
3. Run:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_hygiene.sh --repo /absolute/path/to/repo --apply
```

4. Report final local branch state.

For this workflow, post-merge hygiene is the standard completion step.

## Commands

PR mode:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run prepare pr --repo /absolute/path/to/repo --topic <slug>
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run publish pr --repo /absolute/path/to/repo --plan /tmp/git-publish-plans/<token>.json
```

No-PR mode:

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run prepare no-pr --repo /absolute/path/to/repo
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run publish no-pr --repo /absolute/path/to/repo --plan /tmp/git-publish-plans/<token>.json
```

Legacy compatibility (kept temporarily):

```bash
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run pr --repo /absolute/path/to/repo --topic <slug>
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run pr --repo /absolute/path/to/repo --dry-run
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run no-pr --repo /absolute/path/to/repo
```

Do not use legacy one-shot commands for new agent work. They exist only for temporary backward compatibility.

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

Classification rules:
- tracked modified/deleted/renamed files: included by default
- `.DS_Store`: `excluded-junk`
- suspicious untracked files like `.env`, `.env.local`, `.key`, `.pem`, `.p12`, `.pfx`: `excluded-unclear`
- other untracked files: `excluded-untracked` by default
- untracked directories: `excluded-untracked` by default; `prepare` reports them without recursive expansion
- only narrow safe text/code/doc files are auto-included

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

## After Merge Expectations

After a successful merge and hygiene apply, the expected local result is:
- current branch is `main`
- local `main` is updated to `origin/main`
- stale remote refs are pruned
- local gone feature branches are removed

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

Prepare output should make it easy for an agent to ask for approval.

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

Legacy log lines remain valid.

## Helpers

- `scripts/run`: wrapper for `prepare` and `publish`
- `scripts/git_publish.py`: core implementation
- `scripts/log_since_last_push.py`: log context helper
- `scripts/create_pr_gh.sh`: PR creation via `gh`
- `scripts/create_pr.py`: PR creation via GitHub API
- `scripts/git_hygiene.sh`: standard post-merge local cleanup step for this workflow
