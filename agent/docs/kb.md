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
- `git-publish` executable scripts are not in root skill directory; active implementation is archived.
- `git-publish` v5 spec scope is intentionally pending; do not execute before explicit spec discussion/approval.

## Session Handoff
- date: 2026-03-04
- what changed: aligned discussion context for `git-publish v5` prep and recorded explicit pre-spec decisions in roadmap intent and context snapshot.
- why: lock minimal-v5 direction before drafting/executing `spec 002`.
- risks: active `git-publish` runtime still not present in root skill folder; premature hardening can expand scope.
- next checks: discuss and approve `spec 002` boundaries, then implement minimal scripts with PR-default flow and minimal reporting.
