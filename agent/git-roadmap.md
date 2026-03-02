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

## Next Mandatory Update
- Close the currently recorded protocol intents instead of opening more parallel protocol branches.
- Priority 1: move the recorded future intents into concrete spec/implementation work.
- Priority 2: fix rename-aware planning for commit-range `push` so saved local commits with renames cannot be mispublished.
- New blocking review note: commit-range planning currently relies on `git diff --name-only`, which loses rename metadata. The next update must preserve rename-aware status/source paths before classification so excluded rename targets cannot turn into destructive deletes in the publish commit.


## Future Intent: Named Points For Commit And Push
- User intent: `комит` and `пуш` should operate on a named point, not a generic checkpoint label.
- If the user names the point explicitly, use that name or propose a tighter version.
- If the user does not name the point, the agent should derive a concise meaningful name from recent milestones / meaningful changes and tell the user which name was used.
- The agent should also tell the user that future `комит` / `пуш` commands can include the point name directly.
- This should drive local commit naming and publish naming (topic / commit message / PR title) in a consistent way.


## Future Intent: Better Autonomous Point Summaries
- User intent: when the user does not name the point, the skill should derive a short clean summary by itself instead of emitting a long technical tail from recent log lines.
- Desired evolution: autonomous point naming should compress recent milestones / validations into a concise human-usable point name suitable for commit and publish naming.
- Current signal: the latest derived point name was technically correct but far too long for normal daily use.

