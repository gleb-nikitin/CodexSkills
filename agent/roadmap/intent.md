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

## Current Decisions (Pre-Spec-002)
- Build `git-publish` v5 as a minimal working version first; avoid overengineering and strict blocking behavior.
- `пуш` default mode remains PR; `пуш без пр` only on explicit user request.
- No backward compatibility layer is required for older aliases/commands in v5.
- Incident-driven hardening only: collect incident reports first, then add targeted safeguards.
- Operation report minimum: final status and PR link (when PR mode is used).
- Scope/boundaries for `spec 002` will be discussed and approved separately before execution.

## Direction Rules
- Keep specs concise, implementation-oriented, and testable.
- Prefer explicit contracts and deterministic behavior over heuristic automation.
- Keep context files compact and suitable for no-history sessions.
- Move recurring troubleshooting into `agent/how-to/` and index it in `kb.md`.
