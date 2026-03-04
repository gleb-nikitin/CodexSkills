# Knowledge Base

## Lazy-Load Index
- `./agent/docs/context.md` — fast project snapshot and current focus.
- `./agent/docs/arch.md` — architecture, stack, boundaries, key entrypoints.
- `./agent/docs/run.md` — execution/validation commands.
- `./agent/roadmap/state.md` — current active spec pointer (freshest state).
- `./agent/roadmap/intent.md` — global goals and planned trajectory.
- `./agent/roadmap/archive.md` — completed roadmap/spec records.
- `./agent/how-to/index.md` — index of recurring troubleshooting guides.
- `./archive/git-publish-v4.5-donor/` — read-only fallback implementation snapshot.

## Known Debt
- Only `commit` operation implemented; `push pr`, `push no-pr`, `merge-done` still pending.
- No integration test with a real project repo yet.

## Session Handoff
- date: 2026-03-04
- what changed: implemented `git-publish/scripts/run` with `commit` operation (spec 002). Safety filters, validation, plain-text reporting.
- why: first building block of v5 git-publish skill.
- risks: only commit works; push/merge operations not yet available.
- next checks: design and implement `push pr` operation (spec 003).
