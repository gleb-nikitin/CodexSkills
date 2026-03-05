# Project Context

## Snapshot
- Project: `rss/skills` (CodexSkills workspace)
- Workspace: `/Users/glebnikitin/work/rss/skills`
- Domain: Local skill definitions, execution protocols, and no-history agent context.
- Active spec: none
- Next spec: none
- Main skills: `git-publish`, `infra-bootstrap`

## Current Focus
- Keep `git-publish` implementation and `git-publish/SKILL.md` synchronized as protocol source-of-truth.
- Keep `infra-bootstrap` v2 scripts stable with explicit JSON config contract.
- Keep context/roadmap files concise and current for cold-start execution.
- Preserve archive donor `archive/git-publish-v4.5-donor/` as read-only fallback.

## Agreed Constraints
- Default publish path: PR mode; no-PR only by explicit user command.
- Keep behavior deterministic and safety-first (explicit validation, explicit cleanup anchors).
- Incident-driven hardening: add guards only when concrete failure modes are identified.

## Risks
- Future edits to `git-publish/scripts/run` can desync behavior from `SKILL.md` unless updated together.
- Real GitHub integration should be rechecked after protocol changes (CLI/network/auth-dependent paths).
