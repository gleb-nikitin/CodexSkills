# git-publish Push Auto-Checkpoint Spec

## 1. Purpose

This spec updates the existing `git-publish` skill.
It does not define a new skill.

The update fixes one concrete failure mode:
- `пуш` can currently fail even right after a successful `комит`
- if a new tracked protocol-management delta appears between `комит` and `пуш`, branch checkout for PR publish can abort with "local changes would be overwritten"

Required outcome:
- `пуш` must auto-checkpoint that allowed tracked protocol-management delta before publish, then continue successfully
- current healthy `комит -> пуш -> merge -> мердж дан` behavior must remain intact

## 2. Scope

Implementation is expected to touch only:
- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_publish.py`
- `/Users/glebnikitin/work/rss/skills/agent/git-publish-current-state.md`

This spec does not require changes to:
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_hygiene.sh`

## 3. Non-Goals

This update does not:
- redesign `комит`
- redesign `ребейз`
- redesign `мердж дан`
- change the one-normal-publish-commit rule in PR mode
- untrack or ignore `agent/log.md`
- broaden auto-checkpointing to arbitrary tracked repo changes
- change rename-aware commit-range refusal semantics

## 4. Invariants That Must Remain True

1. `пуш` remains the only protocol that may publish, push, or open a PR.
2. PR mode still produces exactly one normal publish commit.
3. Explicit staging only. Never use `git add -A` or `git add .`.
4. Current worktree-based `пуш` behavior must not regress.
5. Current clean-worktree push-from-local-commits behavior must not regress.
6. Current rename-aware commit-range planning must not regress.
7. `agent/log.md` remains tracked.
8. Current hygiene behavior remains unchanged.

## 5. Problem Definition

Current failure mode:
1. user runs `комит`
2. repo becomes clean and is ahead of remote locally
3. new tracked protocol-management delta appears before `пуш`
   - typical examples:
     - `agent/log.md`
     - `agent/git-publish-current-state.md`
     - `agent/git-roadmap.md`
4. user runs `пуш`
5. `пуш` tries to create or check out the PR branch from base
6. checkout fails because tracked local changes would be overwritten

This is not acceptable for the intended workflow.
The user should not need to run a second manual `комит` just because the protocol itself created or recorded allowed maintenance state.

## 6. Eligible Auto-Checkpoint Scope

`пуш` may auto-checkpoint only tracked protocol-management delta in this narrow allowlist:
- `./agent/*.md`
- `./git-publish/SKILL.md`
- `./git-publish/scripts/git_publish.py`
- `./git-publish/scripts/run`

Rules:
- tracked modifications inside this scope are eligible
- tracked deletions inside this scope are eligible
- tracked renames inside this scope are eligible only if both source and destination stay inside this same allowed scope
- untracked files are not handled by this auto-checkpoint rule; existing classifier rules continue to decide them

If any tracked delta exists outside this allowed scope, `пуш` must refuse clearly.

## 7. When `пуш` Auto-Checkpoints vs Refuses

### 7.1 Auto-Checkpoint Required

`пуш` must auto-checkpoint before publish when all of the following are true:
- there are tracked changes in the working tree
- every tracked changed path is inside the allowed protocol-management scope from section 6
- there are no unresolved conflicts
- there is no pre-existing staged index content that violates current clean-index rules

### 7.2 Refusal Required

`пуш` must still refuse when any of the following are true:
- unresolved conflicts exist
- staged index content exists before the protocol starts
- any tracked changed path is outside the allowed protocol-management scope
- rename-aware commit-range planning already requires refusal
- any existing current publish safety rule requires refusal

Refusal must be clear and say that tracked changes outside the allowed protocol-management scope require manual resolution.

## 8. Auto-Checkpoint Placement

The auto-checkpoint happens on the current branch before PR branch creation or base-branch checkout for publish.

Required order:
1. resolve point naming for the publish operation
2. inspect tracked delta
3. if eligible tracked protocol-management delta exists, create one local checkpoint commit on the current branch
4. only after that continue with normal `пуш` flow

This keeps Git checkout safe because the tracked delta becomes part of local history before the protocol tries to create or switch to the PR branch.

## 9. Naming Interaction

The auto-checkpoint must reuse the current named-point model.

Required behavior:
- if the user explicitly names the point in `пуш`, that point name drives both:
  - the auto-checkpoint commit message
  - the publish naming
- if the user does not name the point, derive one once and reuse it consistently for both steps

Required naming format:
- auto-checkpoint commit message: `wip: <point-name>`
- publish commit message: existing publish format driven by the same point name
- PR title/topic: existing publish format driven by the same point name

The protocol must not derive two different names for the auto-checkpoint and the publish that follows.

## 10. Final Publish Result

After successful `пуш` with auto-checkpoint:
- publish still produces one normal PR commit on the PR branch
- the auto-checkpoint remains only in local history on the source branch
- the PR branch must not include an extra checkpoint commit
- the publish report must mention that an automatic pre-push checkpoint was created and include its SHA
- if point naming was derived, existing point-name reporting rules still apply

This preserves the clean external PR while making local protocol-management delta non-disruptive.

## 11. `agent/log.md` Rule

`agent/log.md` stays tracked.

Design rule:
- `пуш` must not treat a tracked `agent/log.md` delta inside the allowed scope as a reason to fail branch checkout
- instead, it must absorb that tracked delta into the local auto-checkpoint before publish

This is the intended way to keep protocol logs tracked without making them operationally disruptive.

## 12. Output Requirements

When auto-checkpoint happens, `пуш` output must include:
- resolved point name
- whether it was explicit or derived
- `autocheckpoint: applied`
- `autocheckpoint_commit_sha`
- normal publish result fields:
  - branch
  - publish commit SHA
  - PR URL
  - rollback hint

If no auto-checkpoint was needed, output should either:
- omit these fields
- or report `autocheckpoint: not-needed`

Choose one behavior and keep it consistent.

## 13. Failure Semantics

`пуш` must fail clearly when:
- tracked changes exist outside the allowed protocol-management scope
- staged changes exist before protocol start
- unresolved conflicts exist
- auto-checkpoint staging would unexpectedly produce no staged content
- auto-checkpoint commit fails
- later publish safety checks fail as they do today

The existence of allowed tracked protocol-management delta alone must no longer be a failure.

## 14. Validation Matrix

The implementation must validate at least these scenarios:

1. `комит` followed by new tracked `agent/log.md` delta, then `пуш`
- `пуш` auto-checkpoints
- PR publish still succeeds
- one normal publish commit on PR branch

2. `комит` followed by tracked changes in multiple allowed files:
- `agent/log.md`
- `agent/git-publish-current-state.md`
- `agent/git-roadmap.md`
- `пуш` auto-checkpoints and succeeds

3. `пуш` with tracked change outside allowed protocol-management scope:
- protocol refuses clearly before branch checkout

4. `пуш` with pre-existing staged index content:
- protocol still refuses clearly

5. clean-worktree push-from-local-commits with no new tracked delta:
- behavior unchanged

6. worktree-based push with normal tracked app changes and no allowed protocol delta:
- behavior unchanged

7. rename-aware conflicting rename scenario:
- still refuses

8. named-point explicit user input during auto-checkpoint path:
- same point name drives checkpoint and publish naming

9. derived point-name path during auto-checkpoint path:
- one derived name is reported and reused consistently

## 15. Acceptance Criteria

This update is implementation-ready only if all of the following are true:

1. Eligible tracked protocol-management delta is narrowly and explicitly defined.
2. `пуш` auto-checkpoints that eligible delta before branch checkout.
3. Out-of-scope tracked delta still causes a clear refusal.
4. `agent/log.md` remains tracked but no longer causes this specific checkout failure by itself.
5. One normal PR publish commit remains the external result.
6. The auto-checkpoint stays local and does not pollute the PR branch.
7. Existing healthy worktree-based publish, clean-worktree publish-from-local-commits, rename-aware planning, merge-done, and hygiene behavior all remain intact.
