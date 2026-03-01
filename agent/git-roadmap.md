# Git Roadmap

## Purpose

Deferred git-related improvements that are intentionally not part of the current production test round.

## git-publish follow-ups

### 1. Enforce `prepare -> publish` in code
Current state:
- legacy one-shot wrapper path still works

Future change:
- remove or hard-block legacy one-shot publish for agent use
- require a real plan artifact before any publish

Why deferred:
- current flow is good enough for production testing
- better to observe actual agent behavior first

### 2. Enforce direct-push confirmation in code
Current state:
- no-pr is controlled by docs/policy

Future change:
- add runtime confirmation gate for direct push to default branch
- require explicit confirmation signal for `no-pr`

Why deferred:
- policy and docs are enough for first rollout
- code enforcement can follow if misuse appears in testing

### 3. Enforce workspace-root rejection in code
Current state:
- docs forbid `/Users/glebnikitin/work` as `--repo`

Future change:
- reject workspace root explicitly at runtime with exit code 2

Why deferred:
- low implementation cost, but not currently blocking production testing

### 4. Revisit safe untracked allowlist
Current state:
- safe untracked auto-include uses a narrow heuristic allowlist

Future change:
- refine allowlist using real production examples
- possibly move to per-project or per-skill tuning

Why deferred:
- current policy is conservative enough to test in production
- needs real-world feedback more than speculative redesign

### 5. Plan artifact durability
Current state:
- plans are stored in `/tmp/git-publish-plans`

Future change:
- evaluate a more durable location if `/tmp` proves too fragile in actual workflows

Why deferred:
- current behavior is acceptable for near-term agent sessions

### 6. Post-merge remote branch deletion
Current state:
- post-merge hygiene updates local state only
- remote feature branch deletion depends on GitHub auto-delete or manual cleanup

Future change:
- define and implement explicit remote branch deletion policy after merge
- decide whether this belongs in `git_hygiene`, a separate post-merge command, or GitHub-side automation only

Why deferred:
- current production testing mainly needs the agent protocol to be clear
- remote deletion semantics should be designed explicitly, not patched ad hoc

## Recently completed
- harmless untracked files during post-merge cleanup
- spec: `/Users/glebnikitin/work/rss/skills/agent/git-hygiene-untracked-spec.md`
- status: shipped
- recursive planning for new untracked project directories
- spec: `/Users/glebnikitin/work/rss/skills/agent/git-publish-untracked-project-spec.md`
- status: shipped

## git_hygiene

Any non-trivial `git_hygiene` evolution requires a separate spec.

## Next likely spec target

No next `git-publish` spec is selected right now.

Reassess after more real-world feedback on:
- the narrow safe untracked allowlist
- plan storage durability outside `/tmp`
- runtime-only enforcement of policy rules that are currently documented but not hard-blocked
