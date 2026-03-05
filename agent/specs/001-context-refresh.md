# Spec 001: Context Refresh

## Goal
Replace bootstrap placeholders in agent context files with current repository facts and keep cold-start context operational.

## Executed Work
- Updated `agent/docs/context.md`.
- Updated `agent/docs/arch.md`.
- Updated `agent/docs/run.md`.
- Updated `agent/docs/kb.md`.
- Updated `agent/roadmap/intent.md`.
- Added `agent/how-to/index.md`.

## Result
- Status: completed
- User acceptance: received on 2026-03-04
- Closure: spec archived and roadmap state advanced to next spec.

## Residual Risks
- AGENTS roadmap path mismatch (`agent/specs/roadmap/*` vs actual `agent/roadmap/*`).
- Active `git-publish` runtime scripts are missing in root skill folder.
