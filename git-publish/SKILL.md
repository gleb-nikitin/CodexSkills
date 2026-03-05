# git-publish

Safe git commit and publish operations for project repositories.

Status: development scaffold (target protocol), implementation in progress.

## Usage

```
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run <operation> --repo /absolute/path [args...]
```

`--repo` is always required. Must be an absolute path to a git repo. Never use workspace root (`/Users/glebnikitin/work`).

## Workflow

Standard publish path:
```
commit → push pr → [user merges PR on GitHub] → merge-done
```

Initial publish (new projects without remote history, explicit user request only):
```
commit → push no-pr
```

## Important: log before commit

The script never writes to project logs. The correct sequence:
```
1. do work
2. write to agent/log.md
3. run commit        ← log entry is captured in the commit
4. run push pr
```

Never write to logs between commit and push — it creates a dirty diff that breaks the push.

## Operations

### `commit`

Local safepoint. Saves current state so rollback is possible.

```
run commit --repo /path [point name words...]
```

- Creates exactly one local commit. No push, no branch creation.
- Point name becomes the commit message. Default: `wip: local checkpoint`.
- The script handles safety filtering automatically (see Safety below).
- Output: committed SHA, included files, excluded files with reasons.
- Exit 0 on success or nothing-to-commit. Exit 1 on error.

### `push pr`

Publish the latest safepoint via PR.

```
run push pr --repo /path [--topic <slug>]
```

- `--topic` is optional. Used for branch naming: `publish/<topic>` or `publish/<short-sha>` if omitted.
- Creates a branch from HEAD, pushes it, opens a PR to main via `gh`.
- After PR creation, switches back to main locally.
- Requires clean working tree (no uncommitted changes except safety-excluded files).
- Output: PR URL, branch, commit SHA.

### `push no-pr`

Push main directly to remote. For initial project setup only.

```
run push no-pr --repo /path
```

- Use only for new projects that have never pushed to remote.
- Pushes main to origin.

### `merge-done`

Post-merge cleanup.

```
run merge-done --repo /path
```

- Run only after user confirms the PR was merged.
- Syncs local main with remote, removes the publish branch (local + remote).
- Final state: on `main`, `main == origin/main`, no stale branches.
- Does not write to project logs (caller's responsibility).

## Safety

The `run` script enforces safety filtering automatically:
- Excludes secrets (`.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`).
- Excludes agent/workstation artifacts (`.claude/`, `.DS_Store`, editor temps).
- Excludes build artifacts (`dist/`).
- Stages files individually (never `git add -A` or `git add .`).
- Reports all excluded files with reasons.

Default branch is `main`. Override in project `AGENTS.md` if different.
