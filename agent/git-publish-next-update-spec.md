# git-publish Next Update Spec

## 1. Purpose

This spec updates the existing `git-publish` skill.
It does not define a new skill.

The update closes the currently recorded future intents and one known correctness gap without redesigning the working protocol.

The required outcomes are:
- keep the healthy `комит -> пуш -> merge -> мердж дан` workflow intact
- preserve one normal publish commit in PR mode
- preserve explicit staging and clean-index safety
- make commit-range `пуш` rename-aware so local unpublished renames cannot be mispublished
- replace generic checkpoint naming with named-point semantics for `комит` and `пуш`
- move `ребейз` toward an internal pre-publish helper inside `пуш`
- let `мердж дан` start with a safe local checkpoint of protocol-management tracked delta instead of immediately refusing that state

## 2. Source Of Truth Scope

Files expected to change in implementation:
- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_publish.py`
- `/Users/glebnikitin/work/rss/skills/agent/git-publish-current-state.md`

This spec does not require changes to `git_hygiene.sh`.

## 3. Non-Goals

This update does not:
- redesign PR creation
- redesign hygiene semantics beyond the merge-done preflight checkpoint described below
- add a full backup/archive system
- add durable plan storage outside `/tmp`
- add remote-branch deletion guarantees beyond the current best-effort behavior
- change the one-normal-publish-commit rule in PR mode

## 4. Invariants That Must Remain True

1. `пуш` remains the only protocol that may publish, push, or open a PR.
2. PR mode still produces exactly one normal publish commit.
3. `комит` remains local-only.
4. Explicit staging only. Never use `git add -A` or `git add .`.
5. Publish still refuses dirty staged state where the current protocol already requires a clean index.
6. Current hygiene allowance for harmless untracked files remains intact.
7. `мердж дан` may still intentionally leave one tracked `merge-confirmed ...` log delta after success.
8. Current healthy worktree-based `пуш` behavior must not regress.

## 5. Shared Named-Point Model

### 5.1 Purpose

`комит` and `пуш` must operate on a named point instead of a generic unnamed checkpoint.

The point name is the shared human meaning of the current saved or published state.
It drives commit/publish naming consistently.

### 5.2 Resolution Order

When `комит` or `пуш` starts, resolve the point name in this order:

1. Explicit user-provided name in the command/request.
2. Agent-proposed tightened version of the explicit user name.
3. Derived name from recent milestones / meaningful changes when the user gave no name.

### 5.3 Explicit User Naming

If the user explicitly names the point, that name wins semantically.
The agent may tighten wording for brevity and clarity, but must keep the same meaning.

Example:
- user: `комит закрыли спеку 6`
- acceptable tightened point name: `close spec 6`

### 5.4 Derived Naming

If the user does not provide a point name, the agent must derive a concise meaningful name from:
- the latest milestone/validation records in `./agent/log.md`
- the current included change set
- the most recent accepted protocol milestone if it clearly dominates the change set

The agent must then tell the user what name it used.

Required phrasing model:
- `I named this point: <name>. In future you can say 'комит <name>' or 'пуш <name>' explicitly.`

### 5.5 Naming Outputs

The resolved point name must drive naming consistently:
- `комит` local commit message
- `пуш` topic slug
- `пуш` publish commit message
- `пуш` PR title

### 5.6 Required Naming Format

Use these exact defaults unless the user explicitly overrides them:
- local commit message: `wip: <point-name>`
- PR commit message: `chore: <point-name>`
- PR title: `<point-name>`
- topic slug: slugified `<point-name>`

### 5.7 Required Command Surface For Point Names

The implementation must support point naming directly from the user command text.

Required CLI model:
- `scripts/run комит --repo /abs/path <free-text-point-name...>`
- `scripts/run push pr --repo /abs/path <free-text-point-name...>`
- `scripts/run push no-pr --repo /abs/path <free-text-point-name...>`

Rules:
- any free-text tail after the protocol command is the explicit point name
- existing explicit flags such as `--topic`, `--message`, and `--pr-title` remain supported as lower-level overrides
- if a free-text point name is present, it is the primary semantic input and must drive derived topic/message/title defaults
- if both a free-text point name and lower-level naming overrides are provided, the implementation must refuse with a clear conflict message instead of guessing which naming source should win


## 6. `комит` Protocol Update

### 6.1 What Stays The Same

`комит` remains:
- local-only
- exact-classifier based
- explicit-staging only
- one local commit or clean no-op

### 6.2 Required Change

`комит` must stop using a fixed generic message.
It must use the shared named-point model.

### 6.3 Required Behavior

`комит` must:
1. resolve the point name
2. run the exact current classifier
3. show preview with:
   - point name used
   - included files
   - excluded files with reasons
   - final commit message
4. create exactly one local commit with message `wip: <point-name>`
5. if the point name was derived instead of user-provided, tell the user which name was used
6. if nothing is includable, return clean no-op and still report the resolved point name if one was derived

## 7. `ребейз` Evolution

### 7.1 Product Direction

`ребейз` remains available as an explicit command, but it is no longer the normal daily workflow step.
The normal user path should remain:
- `комит`
- `пуш`
- merge
- `мердж дан`

### 7.2 Internalization Rule

`пуш` must own an internal pre-publish normalization check that uses the same rewrite engine as explicit `ребейз`.

### 7.3 Required Minimum Implementation

For this update, `пуш` must use the internal `ребейз` engine only when all of the following are true:
- publish source is local unpublished commit history rather than dirty worktree state
- current branch is not the default branch
- there are two or more local unpublished commits
- deterministic squash/reword can run under the existing safety rules

If those conditions are not met, `пуш` must keep current behavior and publish without rewriting local history.

### 7.4 Safety Rule

`пуш` must never rewrite local history on the default branch.
For default-branch clean-worktree publish-from-local-commits, keep the current materialize-into-one-publish-commit behavior.

### 7.5 Required Local Branch Outcome

If `пуш` runs internal normalization on a non-default branch:
- the rewrite is allowed to change the local unpublished history on that branch
- after successful publish, the current local branch must remain the rewritten source branch state
- the implementation must not silently restore the old pre-normalization history after publish succeeds
- the implementation must report that internal normalization ran and that the local source branch now reflects the normalized history

This keeps the mental model consistent:
- `комит` saves local points
- `пуш` may clean up unpublished local history before publishing it
- after a successful `пуш`, the local source branch should match the normalized history that was just used as publish input

### 7.6 Explicit `ребейз`

The explicit `ребейз` command remains supported and keeps the current deterministic non-interactive contract.
Implementation should reuse the same internal normalization engine that `пуш` now calls when needed.

## 8. Rename-Aware Commit-Range Planning For `пуш`

### 8.1 Problem Being Fixed

Current path-only commit-range planning loses rename metadata.
That can corrupt publish results when a rename crosses classifier boundaries.

Example failure to eliminate:
- local unpublished history renames `old.txt` -> `new.pem`
- `new.pem` would be excluded by the classifier
- path-only planning drops rename origin and can restore the excluded target out of the staged result while still leaving `old.txt` deleted
- publish then lands a destructive delete instead of a safe refusal or correct rename handling

### 8.2 Required Planning Model

Commit-range planning for clean-worktree `пуш` must become rename-aware.
It must preserve, at minimum, for each changed item in the unpublished range:
- status kind (`A`, `M`, `D`, `R`, etc.)
- destination path
- source path for rename/copy-style entries when present

Path-only `git diff --name-only` planning is not sufficient for this path anymore.

### 8.3 Required Classification Model

Rename-aware planning must classify both sides of a rename when applicable:
- source/original path
- destination/new path

The implementation must use current classifier semantics, not invent a second classifier.

### 8.4 Required Safe Outcomes

For commit-range `пуш`:

1. Included tracked rename where both sides remain publishable:
- allowed
- publish may preserve the rename in the final one-commit PR result

2. Rename whose destination or source crosses into an excluded/unclear/local/build class:
- must not be silently published
- must not degrade into a destructive delete
- must refuse the push with a clear message that rename-aware planning found a classifier-conflicting rename

3. Mixed commit range with ordinary included files plus one conflicting rename:
- refuse the push
- do not partially publish a corrupted subset from that rename relationship
- make the refusal explicit so the user can resolve it intentionally

### 8.5 Allowed Simpler Implementation

This update does not require a perfect generic history engine.
A conservative refusal is acceptable when rename-aware safe publication cannot be guaranteed.
Conservative refusal is preferred over silently corrupted publish output.

## 9. `пуш` Protocol Update

### 9.1 What Stays The Same

`пуш` remains:
- self-authorizing
- PR-first in normal mode
- one normal publish commit in PR mode
- exact-classifier based
- immediate publish plus post-publish report

### 9.2 Required Changes

`пуш` must now combine:
1. named-point resolution
2. optional internal `ребейз` normalization when needed
3. rename-aware commit-range planning for saved local commits

### 9.3 Required User-Facing Flow

Normal `пуш` flow becomes:
1. resolve point name
2. determine publish source:
   - worktree changes
   - or saved local unpublished commits
3. if eligible, run internal rebase-normalization step
4. build publish scope with exact classifier semantics
5. if clean-worktree source uses commit range, apply rename-aware planning
6. publish immediately to a PR
7. report:
   - chosen point name
   - branch
   - commit SHA
   - PR URL
   - rollback hint
   - whether the point name was derived or explicit

### 9.4 No Extra Approval Round

`пуш` remains self-authorizing.
There is still no extra approval round after internal preparation.
Review continues to happen on the PR before merge.

## 10. `мердж дан` Protocol Update

### 10.1 Product Change

`мердж дан` must stop immediately refusing all tracked protocol-management delta.
Instead, it must be able to start with a safe local checkpoint of that tracked delta before merge verification and hygiene.

### 10.2 What Counts As Eligible Preflight Checkpoint State

For this update, the automatic preflight checkpoint is allowed only for tracked protocol-management delta under the skills workspace, specifically files that are part of current git-publish maintenance context such as:
- `./agent/*.md`
- `./git-publish/SKILL.md`
- `./git-publish/scripts/git_publish.py`
- `./git-publish/scripts/run`

If tracked changes exist outside that protocol-management scope, `мердж дан` must still refuse.

### 10.3 Required Preflight Behavior

When `мердж дан` starts and finds eligible tracked protocol-management delta:
1. resolve a point name for the preflight checkpoint
   - if the user did not provide one, derive it from recent milestones and the current tracked delta
2. create one local checkpoint commit before merge verification/hygiene
3. report that preflight checkpoint SHA in the final merge-done output
4. continue with current merge-done flow

Branch rule for that checkpoint:
- if current branch before cleanup is the anchor feature branch, the checkpoint may be created there
- if current branch before cleanup is the default branch, the checkpoint must be created on a temporary local checkpoint branch created from current `HEAD`, then the implementation must return to the default branch before hygiene
- the checkpoint step must not leave the default branch ahead of `origin/<default>` before hygiene starts
- if a temporary checkpoint branch was created from the default branch, it must be deleted locally before the end of a successful `мердж дан` run
- a successful `мердж дан` run must not leave that temporary checkpoint branch behind as a tail

### 10.4 Naming For Preflight Checkpoint

Use:
- `wip: <point-name>`

If the name was derived, report it the same way as in `комит`/`пуш`.

### 10.5 What Still Must Refuse

Even after this update, `мердж дан` must still refuse when:
- unresolved conflicts exist
- staged index content exists that is outside the allowed checkpoint path
- tracked modifications outside the allowed protocol-management scope exist
- merge verification cannot identify the intended PR uniquely
- hygiene cannot complete safely

### 10.6 Final State Contract

After successful `мердж дан`:
- current branch must be `main`
- local `main` must equal `origin/main`
- anchor feature branch must be gone locally
- any temporary checkpoint branch created by `мердж дан` from `main` must also be gone locally
- remote feature branch status must be reported (`gone`, `present`, or `unknown`)
- one tracked `merge-confirmed ...` log delta may remain by design
- if a preflight checkpoint commit was created, its SHA must be reported explicitly

## 11. Logging Rules

### 11.1 What Stays The Same

Success marker format stays unchanged:
- `YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success`

Merge-confirmed marker format stays unchanged:
- `YYYY-MM-DD HH:MM | git-publish skill | merge-confirmed branch=<anchor_branch> base=<anchor_base> | user confirmed merged; hygiene=applied; remote_branch=<gone|present|unknown>`

### 11.2 New Output/Reporting Requirements

The protocol must report, in human and JSON output where relevant:
- resolved point name
- whether that point name was explicit or derived
- when `мердж дан` created a preflight checkpoint commit, its SHA
- when `пуш` used internal rebase normalization, that it did so
- when `пуш` refused due to classifier-conflicting rename-aware planning, a clear refusal reason

No new tracked marker line is required for named-point resolution itself.

## 12. Failure Semantics

### 12.1 `комит`

Must fail clearly on:
- detached HEAD
- unresolved conflicts
- staged index inheritance

Must no-op cleanly when nothing is includable.

### 12.2 `ребейз`

Must keep current clean refusal and rollback semantics.

### 12.3 `пуш`

Must fail clearly when:
- rename-aware commit-range planning detects a classifier-conflicting rename
- internal normalization would require rewriting the default branch
- repo safety checks fail
- no publishable local work exists

### 12.4 `мердж дан`

Must fail clearly when:
- a preflight checkpoint would need to capture out-of-scope tracked changes
- merge verification stays ambiguous
- hygiene fails
- final-state checks fail

## 13. Validation Matrix

The implementation must validate at least these scenarios:

1. `комит` with explicit point name:
- commit message becomes `wip: <explicit-name>`
- preview reports the chosen point name

2. `комит` with no explicit point name:
- derived point name is reported to the user
- commit message uses that derived name

3. `пуш` from dirty worktree with explicit point name:
- PR branch uses slugified point name
- publish commit message and PR title use the same point name
- one normal publish commit only

4. `пуш` from clean worktree + saved local commits + no explicit point name:
- derived point name is reported
- publish succeeds through PR
- one normal publish commit only

5. Commit-range `пуш` with rename from included tracked path to excluded target:
- push refuses clearly
- no corrupted partial publish lands

6. Commit-range `пуш` with normal included rename:
- push succeeds
- final PR commit preserves correct safe rename result

7. `пуш` on non-default branch with multiple unpublished commits where internal normalization is eligible:
- internal rebase helper may run
- publish still succeeds with one normal PR commit

8. `пуш` on default branch with multiple unpublished commits:
- no local default-branch rewrite occurs
- publish still follows current safe materialization behavior

9. `мердж дан` with only tracked protocol-management delta present:
- preflight checkpoint commit is created
- merge verification continues
- hygiene continues
- final output reports the checkpoint SHA

10. `мердж дан` with tracked changes outside allowed protocol-management scope:
- protocol refuses clearly before hygiene

11. Existing healthy worktree-based `пуш` scenario:
- no regression

12. Existing harmless-untracked hygiene scenario:
- no regression

## 14. Acceptance Criteria

This update is implementation-ready only if all of the following are true:

1. Named-point behavior is fully defined for both `комит` and `пуш`.
2. Derived-name fallback is explicit and user-visible.
3. `ребейз` evolution is concrete enough that `пуш` can use the same engine internally without guessing when it is allowed.
4. Rename-aware commit-range planning no longer relies on path-only diffing.
5. Classifier-conflicting renames fail safely instead of silently degrading into deletes or partial publish corruption.
6. `мердж дан` can begin with a safe local checkpoint of allowed tracked protocol-management delta.
7. Existing healthy publish, PR, and hygiene behavior remains intact.
8. The update still produces one normal publish commit in PR mode.

## 15. Design Note About Scope Tension

There is one intentional scope tension in this update:
- `мердж дан` should become more tolerant by checkpointing allowed tracked protocol-management delta automatically
- but it must not quietly swallow arbitrary tracked changes

This spec resolves that tension by making the automatic preflight checkpoint narrow and path-scoped.
If implementation cannot prove the tracked delta stays inside the allowed protocol-management scope, it must refuse instead of broadening merge-done mutation implicitly.
