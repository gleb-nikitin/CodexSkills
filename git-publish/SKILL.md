---
name: git-publish
description: Deterministic Git publish workflow for solo repos in /Users/glebnikitin/work. Use when the user says 'пуш', 'git push', 'push', or 'пуш без пр'. Creates a branch + PR by default; supports direct push to default branch only when explicitly requested.
---

# git-publish

## Intent

Make git publishing low-friction and low-risk without bloating project context.

Default behavior: **branch + PR**.

Exception: **direct push to default branch** only when user explicitly requests `пуш без пр`.

## Quick start (English)

Run from anywhere (repo is explicit):

- PR mode (default):
  - `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run pr --repo /absolute/path/to/repo --topic <slug>`
- No-PR mode (only when user explicitly asks `пуш без пр`):
  - `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run no-pr --repo /absolute/path/to/repo`
- Dry run (prints detected paths; no commit/push):
  - `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run pr --repo /absolute/path/to/repo --dry-run`

What it does:
- Reads git status, stages explicit paths (no `git add -A`), commits, pushes.
- In PR mode, auto-creates a PR via `gh` when authenticated (fallback: API).
- Appends a `git-publish skill | push ... | success/fail` marker to `log.md`.

## Inputs (from user message)

- `mode`: `pr` (default) or `no-pr` (only for `пуш без пр`)
- `topic`: short slug for branch name `codex/<topic>` (derive if missing)
- `repo`: absolute path to the target repo (agent must pass it to `scripts/run` via `--repo`)
- `notes`: short human summary (optional; can be derived from `log.md`)

## Required project artifacts

- Project root contains `log.md` with format: `YYYY-MM-DD HH:MM | action | result`

## Allowed out-of-scope reads (workspace allowlist)

- `/Users/glebnikitin/.ssh/AGENTS.md` is allowlisted by workspace policy for read-only access.
- Use it only when GitHub auth details are required (auto-PR creation).
- Do not copy secrets into repo files or logs. If a token is needed, load it into environment only for the current process/session.

## GitHub auth for auto-PR (recommended)

Store a GitHub token in macOS Keychain and let `create_pr.py` read it without printing:

- Keychain service (default): `codex_github_token`
- Keychain account (default): `$USER` (for you: `glebnikitin`)

The token must have permission to create PRs in the target repo.

Preferred auth is GitHub CLI (`gh`) with `gh auth login` (token stored in keyring).

## Log marker (source of truth for "since last push")

On success, append to project `./log.md` exactly one line:

`YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success`

On failure, append:

`YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | fail: <short-reason>`

## What to include in PR/commit context

1. **Git reality**: `git status`, `git diff`, `git diff --staged`, `git diff --stat`.
2. **Human intent**: lines from `./log.md` since the last `git-publish skill | ... | success` marker.

## Workflow (agent)

1. Always pass the target repo explicitly (`--repo /absolute/path/to/repo`) to avoid publishing from the wrong directory.
2. Ensure repo is valid (`git rev-parse --show-toplevel`).
2. Collect log context since last successful push marker:
   - Prefer the helper: `python3 /Users/glebnikitin/work/rss/skills/git-publish/scripts/log_since_last_push.py`
3. Preflight:
   - `git status --porcelain -b`
   - `git diff --stat`
   - Fail fast if there are suspicious files (secrets, `.env` without example, large binaries) unless user explicitly allows.
4. Staging policy (safe default):
   - Never use `git add -A` or `git add .`.
   - Stage explicit paths computed from `git status --porcelain`, excluding obvious junk (e.g. `.DS_Store`).
   - If untracked files exist, stage only those explicitly relevant (ask if unclear).
5. Commit message:
   - Use a short message derived from `topic` + log summary (1 line).
6. Publish:
    - `mode=pr`:
      - Create/switch to `codex/<topic>` and push it.
     - Create PR automatically when auth is available:
       - Preferred: GitHub CLI (`gh pr create ...`) when installed and authenticated.
       - Fallback: `python3 /Users/glebnikitin/work/rss/skills/git-publish/scripts/create_pr.py ...` (uses Keychain or `GITHUB_TOKEN`).
       - If neither is available: provide manual PR creation link.
    - `mode=no-pr`:
      - Only allowed if user explicitly asked `пуш без пр`.
      - Push directly to default branch (`main`/`master` as configured in project `AGENTS.md`).
7. Append the success/fail marker line to `./log.md`.

## Helpers

- `scripts/log_since_last_push.py`: prints `log.md` lines since last successful git-publish marker (for PR description).
- `scripts/create_pr.py`: creates a PR via GitHub API (uses `GITHUB_TOKEN` or macOS Keychain).
- `scripts/create_pr_gh.sh`: creates a PR via `gh` (preferred).
- `scripts/run`: entrypoint to stage/commit/push and create PR automatically (`--repo` required; `--dry-run` supported).
