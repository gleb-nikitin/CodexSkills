## Git protocols

### Critical include/exclude safety
- Default branch: `main` (override in project `AGENTS.md` if different).
- Stage explicit paths only. Never `git add -A` or `git add .`.
- Always pass `--repo /absolute/path`. Never use workspace root as `--repo`.
- Never include secrets: `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, private credentials/config dumps.
- Never include local-agent/workstation artifacts: `.claude/`, editor temp files, OS junk (`.DS_Store`), local cache/build output.
- Exclude generated build artifacts by default (for example `dist/`, large compiled bundles) unless explicitly required.
- If a path is ambiguous (could be sensitive or local-only), exclude it and report it as excluded with reason.

### `commit`
- This is a safepoint: save the current state so rollback is possible.
- Create exactly one local commit; no push, no PR.
- Use an explicit point name; if none is provided, derive a short meaningful one and report it.

### `push pr`
- Publish immediately via PR (self-authorizing step).
- Publish only the latest safepoint.
- If newer local worktree changes exist after that safepoint, do not silently publish or drop them; report clearly that they remain local.
- Always report: branch, commit SHA, PR URL, and exact published scope.

### `push no-pr`
- Use only on explicit user request.
- Keep the same publish-source rule: latest safepoint only, no implicit mixing.
- If the scenario is unsupported by current implementation, fail clearly and explain; do not bypass protocol with raw `git push`.

### `merge-done`
- Run only after explicit user confirmation that PR was merged.
- Verify the merged PR/branch for the current cycle.
- Run cleanup/hygiene to final operational state: on `main`, `main == origin/main`, no feature-branch tail.
- Append merge-confirmed log entry; this is expected protocol trace.