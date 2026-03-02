# Git Roadmap

## Purpose

Deferred git-related improvements that are intentionally not part of the current production test round.

## Current Assessment

`git-publish` is now in a good operational state for normal use.

The core workflow is working repeatedly in real usage:
- prepare
- review
- publish
- merge
- cleanup
- final one-branch confirmation

No new urgent `git-publish` redesign is justified right now.
Further work should be driven by concrete production pain, not speculative refactoring.

## git-publish follow-ups

### 1. Enforce `prepare -> publish` in code
Current state:
- legacy one-shot wrapper path still works

Future change:
- remove or hard-block legacy one-shot publish for agent use
- require a real plan artifact before any publish

Why deferred:
- current flow is already good enough in practice
- this is policy hardening, not a blocking workflow gap

### 2. Enforce direct-push confirmation in code
Current state:
- no-pr is controlled by docs/policy

Future change:
- add runtime confirmation gate for direct push to default branch
- require explicit confirmation signal for `no-pr`

Why deferred:
- current docs/policy are sufficient for normal use
- hard enforcement can wait for actual misuse signals

### 3. Enforce workspace-root rejection in code
Current state:
- docs forbid `/Users/glebnikitin/work` as `--repo`

Future change:
- reject workspace root explicitly at runtime with exit code 2

Why deferred:
- low cost, but not currently blocking real workflows

### 4. Revisit safe untracked allowlist
Current state:
- safe untracked auto-include uses a narrow heuristic allowlist

Future change:
- refine allowlist using more real production examples
- possibly move to per-project or per-skill tuning

Why deferred:
- remaining issues here are polish, not protocol breakage

### 5. Plan artifact durability
Current state:
- plans are stored in `/tmp/git-publish-plans`

Future change:
- evaluate a more durable location if `/tmp` proves too fragile in actual workflows

Why deferred:
- current behavior is acceptable in active agent sessions

### 6. Post-merge remote branch deletion
Current state:
- post-merge hygiene updates local state only
- final remote branch cleanup may still require GitHub auto-delete or manual deletion

Future change:
- define and implement explicit remote branch deletion policy after merge
- decide whether this belongs in `git_hygiene`, a separate post-merge command, or GitHub-side automation only

Why deferred:
- the repo can already be brought back to one clean local and remote `main`
- remaining work here is cleanup ergonomics and automation clarity

## Recently completed
- harmless untracked files during post-merge cleanup
- spec: `/Users/glebnikitin/work/rss/skills/agent/git-hygiene-untracked-spec.md`
- status: shipped
- recursive planning for new untracked project directories
- spec: `/Users/glebnikitin/work/rss/skills/agent/git-publish-untracked-project-spec.md`
- status: shipped

## Next likely spec target

No next `git-publish` spec is selected right now.

Reassess only after more real-world feedback on:
- rough edges in new untracked directory ergonomics
- plan storage durability outside `/tmp`
- runtime-only enforcement of policy rules that are currently documented but not hard-blocked
- post-merge remote branch cleanup automation

## git_hygiene

Any non-trivial `git_hygiene` evolution still requires a separate spec.
