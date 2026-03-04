# Project Context

## Snapshot
- Project: `rss/skills` (CodexSkills workspace)
- Workspace: `/Users/glebnikitin/work/rss/skills`
- Domain: Local skill definitions, execution protocols, and no-history agent context.
- Active spec: none
- Next spec: 002 (to be discussed before execution)
- Main skills: `git-publish`, `infra-bootstrap`

## Current Focus
- Prepare minimal `git-publish` v5 protocol/workflow design with low-context footprint.
- Keep `git-publish/SKILL.md` as the operational protocol source for git workflows.
- Maintain `infra-bootstrap` v2 scripts and explicit JSON config contract.
- Keep context files concise and synchronized for cold-start execution.
- Preserve archive donor `archive/git-publish-v4.5-donor/` as read-only fallback.
- Keep `commit` transfer to `AGENTS.md` as deferred intent (later phase).

## Agreed Constraints (v5 Prep)
- Default publish path: PR mode; no-PR only by explicit user command.
- No backward compatibility requirements for legacy aliases.
- Hardening should be incident-driven after first minimal version.
- User-facing operation output minimum: status and PR link if available.

## Risks
- `git-publish` runtime scripts are not present in the root skill folder; implementation currently lives in the donor archive.
- Scope creep risk while defining `spec 002`; keep minimal baseline first.
