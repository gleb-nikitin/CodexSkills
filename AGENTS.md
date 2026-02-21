# Skills Workspace AGENTS.md

## Scope
- `/Users/glebnikitin/work/rss/skills` and subfolders only.

## Required Files
- `./AGENTS.md` - skills workspace policy entrypoint.
- `./agent/log.md` - append-only factual action log for skills operations.

## Rules
- Each skill folder must contain `SKILL.md`.
- Optional skill subfolders: `scripts/`, `references/`, `assets/`.
- Do not store secrets, tokens, or keys in skill folders.
- Keep skill docs compact and LLM-efficient.
- Log meaningful actions to local `./agent/log.md` as `YYYY-MM-DD HH:MM | action | result`.
- `agent/log.md` entries must use current write-time timestamps only.
- Do not add backfilled/retroactive timestamps.
