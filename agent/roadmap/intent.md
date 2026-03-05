# Roadmap Intent

## Global Goals
- Project: CodexSkills workspace (`rss/skills`)
- Purpose: Maintain deterministic local skills and concise operational context for reliable no-history agent execution.

## Planned Intents
1. Keep `git-publish` protocol guidance authoritative and synchronized with implementation reality.
2. Keep `infra-bootstrap` v2 flow stable with explicit config validation and machine-readable reports.
3. Keep context/roadmap files compact, current, and actionable for cold starts.
4. Define and execute the next concrete spec when user requests implementation work.

## Deferred Intents
- For `git-publish` v5, move a minimal `комит` protocol card into project `AGENTS.md` working rules and keep `git-publish/SKILL.md` as the reference for the remaining operations (`ребейз`, `пуш`, `пуш без пр`, `мердж дан`).

## Current Decisions
- `push` default mode remains PR; `push no-pr` only on explicit user request.
- Anchor-based merge cleanup remains strict: clean worktree + anchored PR verification + exact branch cleanup.
- Keep one-line anchor backward compatibility while using two-line anchors for new cycles (PR number + published SHA).

## Direction Rules
- Keep specs concise, implementation-oriented, and testable.
- Prefer explicit contracts and deterministic behavior over heuristic automation.
- Keep context files compact and suitable for no-history sessions.
- Move recurring troubleshooting into `agent/how-to/` and index it in `kb.md`.
