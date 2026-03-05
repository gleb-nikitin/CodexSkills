# Completed Specs
# Append newest first.

## 003-push-and-merge
- status: completed
- accepted_on: 2026-03-05
- scope:
  - Extended `git-publish/scripts/run` with `push pr`, `push no-pr`, and `merge-done`.
  - Added shared top-level argument parsing and common `--repo` validation across operations.
  - Implemented anchored PR cleanup in `merge-done` using `.git/git-publish-anchor`.
  - Finalized clean-worktree behavior to ignore excluded paths (`exclude_reason()` scope).
  - Added cycle SHA guard in `merge-done` to refuse local-main drift after publish.
  - Kept backward compatibility for old one-line anchors (PR number only).
  - Updated `git-publish/SKILL.md` to remove "Not yet implemented" markers.
- residual_risks:
  - Full end-to-end verification against a real GitHub remote should be rerun periodically after future protocol edits.

## 002-git-commit
- status: completed
- accepted_on: 2026-03-04
- scope:
  - Created `git-publish/scripts/run` (bash, 153 lines) with `commit` operation.
  - Safety filters: `.DS_Store`, `.claude/`, `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `dist/`, editor temps.
  - Dispatch architecture ready for future operations (`push`, `merge-done`).
- residual_risks:
  - Only `commit` implemented; `push pr`, `push no-pr`, `merge-done` still missing.
  - No integration test with real project repo yet (only temp-dir tests).

## 001-context-refresh
- status: completed
- accepted_on: 2026-03-04
- scope:
  - Updated `agent/docs/context.md`, `agent/docs/arch.md`, `agent/docs/run.md`, and `agent/docs/kb.md` from bootstrap placeholders to current repository facts.
  - Updated `agent/roadmap/intent.md` with real global goals and planned intents.
  - Added missing `agent/how-to/index.md`.
- residual_risks:
  - AGENTS roadmap path mismatch (`agent/specs/roadmap/*` vs actual `agent/roadmap/*`).
  - `git-publish` runtime scripts are missing in active skill directory and currently exist only in donor archive.
