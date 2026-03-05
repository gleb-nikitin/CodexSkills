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
- `git-publish` flow is implemented for `commit`, `push pr`, `push no-pr`, and `merge-done`; real GitHub integration should be revalidated after future protocol edits.
- No active queued spec; next work item should be user-prioritized.

## Session Handoff
- date: 2026-03-05
- what changed: closed spec 003; `git-publish/scripts/run` now supports full commit/publish/merge cleanup cycle with shared repo validation, excluded-aware clean-worktree checks, anchored PR cleanup, and SHA drift guard in `merge-done`.
- why: complete minimal working publish protocol and prevent unsafe `merge-done` reset when local `main` moved after publish.
- risks: full production verification on a real GitHub remote should be rerun after any additional script changes.
- next checks: pick the next spec from user priority; if git-publish evolves again, keep anchor compatibility and clean-worktree semantics covered by tests.
