# Git Protocol Split Spec

## 1. Purpose

Define a narrow protocol split inside the existing `git-publish` skill for `/Users/glebnikitin/work/rss/skills`.

This spec adds four explicit user-invoked protocols:
- `комит`
- `ребейз`
- `пуш`
- `мердж дан`

This is not a general git redesign.
It is a targeted correction so the implementation matches the real user workflow:
- `комит` saves a local safe state
- `ребейз` is an optional local cleanup tool
- `пуш` publishes the saved local work to GitHub via PR
- `мердж дан` finalizes the merged PR cycle

The current healthy publish engine must remain intact where possible.
The current one-normal-commit PR result must remain intact.

## 2. This Spec Updates Existing `git-publish`

This spec updates the existing skill at:
- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/run`
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_publish.py`
- `/Users/glebnikitin/work/rss/skills/agent/git-publish-current-state.md`

It does not define a new skill.

Protocol selection is explicit.
The user's command word chooses the protocol.
The implementation must not infer one protocol from another.

## 3. Protocol Table

| command | intent | mutates repo? | creates commit? | pushes? | opens PR? | runs hygiene? | writes tracked log? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `комит` | save one local rollback point | yes | yes, one local commit | no | no | no | no |
| `ребейз` | optional local unpublished-history cleanup | yes | yes, rewritten local commit object(s) | no | no | no | no |
| `пуш` | publish saved local work to GitHub | yes | yes, one normal publish commit | yes | yes in `pr` mode; no in `no-pr` mode | no | yes, current publish marker behavior |
| `мердж дан` | verify merged PR cycle, run hygiene, append merge confirmation record | yes | no | no | no | yes | yes, one appended project-log line |

## 4. Shared Engine Rules

1. All protocols operate on one explicit repo path.
   The repo path must be absolute.
   The workspace root `/Users/glebnikitin/work` must still be refused for this skill.

2. All mutating protocols must refuse unresolved conflicts.

3. The implementation must resolve the repo default branch using the same source as current `git-publish`.
   In current repos this is expected to be `main`.

4. Project log path resolution stays unchanged:
   - prefer `./agent/log.md`
   - fallback `./log.md`

5. `пуш` remains the only protocol allowed to call the existing publish engine.
   `комит`, `ребейз`, and `мердж дан` must not call `publish`.

6. `комит` must reuse the exact current `prepare` classifier.
   `пуш` may use that same classifier when building publish input from local work.
   An approximate reimplementation is not allowed.

7. Manual pre-staging is never inherited.
   If a protocol stages files itself, it must start from a clean index and stage only its own explicit path list.
   No protocol may rely on `git add -A` or `git add .`.

8. No protocol may silently broaden the include set beyond current publish safety.
   Current narrow handling of untracked files, untracked directories, `.DS_Store`, `.claude`, `dist`, and suspicious secret-like files must not be weakened unless the implementation can justify the same safety level.

9. No protocol may silently switch to another protocol.
   Example:
   - `комит` must not escalate into `пуш`
   - `ребейз` must not trigger publication
   - `мердж дан` must not create a publish commit

## 5. `комит` Protocol

### Intent

Create one local safe-state checkpoint so the user can roll back if later work goes wrong.

This protocol is local only.
It is not publish.

### Preconditions

The protocol must refuse if any of the following is true:
- repository is not a valid git repo
- HEAD is detached
- index already contains staged changes
- there are unresolved conflicts

Tracked unstaged changes and safe includable untracked files are allowed because they are the intended commit input.

### File Selection

`комит` must reuse the exact current `prepare` classifier.

Required behavior:
1. Run the current classifier without mutating the repo.
2. Build `included` and `excluded` lists with the same path-level decisions and exclusion reasons that `prepare` would produce today.
3. The commit include set is exactly `included`.
4. Paths in `excluded` must not be committed.
5. Existing staged state must not be reused.

If the classifier returns no includable paths, `комит` must return a clean no-op result.

### Preview Rule

Preview is required.

Before mutation, the protocol must print:
- included files
- excluded files and reasons
- final commit message

No second approval round-trip is required.
The user's explicit `комит` command is the authorization to create the local commit.

### Commit Rule

Minimum supported commit model:
- stage exactly the computed include set
- create exactly one local commit
- use the fixed commit message `wip: local checkpoint`
- do not push
- do not open a PR
- do not write to the project log

This protocol must remain low-noise.

## 6. `ребейз` Protocol

### Intent

Optional local unpublished-history cleanup only.

This protocol is useful, but not central to the workflow.
It is not the foundation of `пуш`.
`пуш` must still work without requiring `ребейз` first.

### Preconditions

The protocol must refuse if any of the following is true:
- HEAD is detached
- current branch is the default branch
- index contains staged changes
- worktree contains tracked unstaged changes
- there are unresolved conflicts

### Rewrite Boundary

The rewrite set must be computed deterministically:

1. If the current branch has an upstream tracking branch, the rewrite set is:
   commits reachable from `HEAD` and not reachable from `@{u}`.

2. If the current branch has no upstream tracking branch, the rewrite set is:
   commits reachable from `HEAD` and not reachable from the merge-base of `HEAD` and the default branch.

This makes the protected boundary explicit:
- commits already published upstream are protected
- commits reachable from the default branch are protected
- only local unpublished commits are rewriteable

If the rewrite set is empty, `ребейз` must return a clean no-op result.

### Supported Non-Interactive Rewrite Model

The minimum supported model is squash-only cleanup.
No generic interactive rebase is required.

Required behavior:
1. If the rewrite set contains exactly one commit:
   rewrite only that one commit's message non-interactively.

2. If the rewrite set contains more than one commit:
   replace the entire rewrite set with exactly one new commit on top of the protected boundary.

3. The final rewritten commit message must be derived deterministically from the newest commit in the rewrite set:
   - start from that commit's existing message
   - strip one leading `fixup! ` or `squash! ` prefix from the subject if present
   - if the resulting subject is empty, fall back to `wip: local checkpoint`

Not supported:
- interactive editor steps
- reorder
- split
- partial drop
- edit pauses
- rewriting pushed commits
- rewriting default-branch history

### Failure Rule

If the rewrite hits a conflict or any other failure:
- abort the rewrite
- restore the original `HEAD`
- leave no in-progress rebase state behind

## 7. `пуш` Protocol

### Intent

Publish the saved local work to GitHub.

This is the main external delivery protocol.
It is self-authorizing.
The user's explicit `пуш` command is already authorization to publish.
User review happens on the created PR before merge.

### Required Behavior

The implementation must preserve all of the following:
- `publish` is the only mutating publish step
- one publish action creates exactly one normal publish commit in the PR branch
- explicit staging only
- current PR output behavior
- current rollback hint behavior
- current project-log success marker behavior
- explicit `пуш без пр` / `push no pr` / `push without pr` handling

### Publish Input Model

This is the critical rule.

`пуш` must be able to publish accumulated local unpublished work from the current branch.
That includes the common case where:
- the user previously ran `комит`
- the worktree is now clean
- the meaningful unpublished state exists as local commits, not as unstaged files

So `пуш` must not no-op just because the worktree is clean.
If local unpublished commits exist on the current branch, they are valid publish input.

### Required Self-Authorizing Flow

In PR mode, the required flow is:
1. identify the local unpublished work to be published from the current branch
2. internally derive the publish scope and reportable summary for that work
3. if current safety checks pass, create the publish branch
4. materialize one normal publish commit representing the publishable local work
5. push the branch and create the PR
6. report what was published
7. the user reviews the PR before merge

The protocol must not require an extra approval round after internal preparation.

If a standalone `prepare` command still exists for inspection or debugging, it is optional and must not be the required approval gate for normal `пуш`.

### Relationship With `комит`

`комит` and `пуш` are intentionally connected:
- `комит` saves local work safely
- `пуш` publishes that saved local work later

This is expected and normal.
It is not a protocol violation.

### Relationship With `ребейз`

`ребейз` is optional.
It may make local unpublished history cleaner before `пуш`, but `пуш` must not depend on it.

### Required Reporting

Runtime output after successful `пуш` should report at least:
- mode
- repo
- base
- branch
- commit SHA
- what local work or file scope was published
- log path
- PR URL in PR mode
- rollback hint

### No-PR Mode

Direct push to the default branch remains allowed only when the user explicitly requests:
- `пуш без пр`
- `push no pr`
- `push without pr`

This spec does not redesign that path.

## 8. `мердж дан` Protocol

### Intent

Finish one PR publish cycle after the user says the merge happened.

This protocol has four required outcomes:
- verify the merge really happened
- run post-merge hygiene
- check that files still look right after the cycle
- record a tracked repo-log line that the merge was confirmed

### Applicability

`мердж дан` applies only when the most recent successful `пуш` marker for this repo is in `mode=pr`.

It is not the completion step for `mode=no-pr`.
If the most recent successful publish marker for this repo is `mode=no-pr`, `мердж дан` must refuse with a clear message.

### Merge-Verification Anchor

The relevant merge is defined exactly as follows:

1. Resolve the active project log path using the current project-log rules.
2. Read the most recent publish success marker of any mode:
   `git-publish skill | push mode=<pr|no-pr> branch=<branch> base=<base> | success`
3. Require that this most recent marker is `mode=pr`.
   If it is `mode=no-pr`, refuse as not applicable.
4. Extract:
   - `anchor_branch`
   - `anchor_base`
   from that same most recent marker.
5. This `(anchor_branch, anchor_base)` pair is the only merge-verification anchor for the protocol run.

Additional consistency check:
- if the current branch before cleanup is not the default branch, it must equal `anchor_branch`
- if the current branch is neither `anchor_branch` nor the default branch, the protocol must refuse as ambiguous

The implementation must not invent another target branch or PR.

### Merge Verification

The protocol must verify exactly one PR identified by:
- head branch = `anchor_branch`
- base branch = `anchor_base`

Verification succeeds only when:
- exactly one matching PR can be resolved by the existing GitHub lookup path (`gh` or current API fallback)
- that PR is marked merged

Verification failure cases:
- no matching PR
- more than one ambiguous matching PR
- PR exists but is not merged

On verification failure:
- do not run hygiene
- do not append the merge-confirmation log line

### Hygiene And File Check

Before hygiene, the protocol must require:
- no staged changes
- no tracked unstaged changes
- no unresolved conflicts

Harmless local untracked files may remain only when current hygiene rules already allow them.
Real checkout/update conflicts from untracked files still block hygiene.

After successful merge verification:
- run the existing hygiene flow
- if needed, remove leftover feature branch tails locally and remotely
- verify that the expected project files still look correct after the cycle
- then append the merge-confirmed log line

The file check may use whatever lightweight verification the current system supports at implementation time, but it must not weaken the existing cleanup safety.

### Final State Target

Required local target after hygiene:
- current branch is the default branch
- local default branch equals `origin/<default>`
- the local `anchor_branch` no longer exists

Best-effort only:
- remote `anchor_branch` deletion
- a fully clean worktree, because the required tracked merge-confirmation log line is appended after hygiene

### Required Tracked Log Write

After successful merge verification and successful hygiene, append exactly one line to the active project log:

```text
YYYY-MM-DD HH:MM | git-publish skill | merge-confirmed branch=<anchor_branch> base=<anchor_base> | user confirmed merged; hygiene=applied; remote_branch=<gone|present|unknown>
```

Rules:
- append only
- current write-time timestamp only
- never backfill
- do not create a separate commit for this line

This tracked log append is intentional.
It is acceptable for `мердж дан` to leave the repo dirty by this one tracked log delta because the user contract explicitly requires a repo-log record of merge confirmation.
This is part of the system design, not an error condition.
Agents must not treat this post-cleanup tracked log delta as an incident, regression, or reason to undo the protocol result.
It is the expected signal that the system moved into the next untracked step after merge finalization.

The protocol must report that remaining tracked delta clearly in runtime output.

## 9. Logging Rules

1. `пуш` logging remains unchanged.
   The existing success marker format stays intact:

```text
YYYY-MM-DD HH:MM | git-publish skill | push mode=<pr|no-pr> branch=<name> base=<name> | success
```

2. `комит` must not write tracked log lines.

3. `ребейз` must not write tracked log lines.

4. `мердж дан` must append the exact `merge-confirmed ...` line defined in this spec after successful verification and hygiene.

5. No protocol may rewrite or delete old project-log lines.

6. Runtime output stays factual and low-noise.
   Minimum runtime reporting:
   - `комит`: success, no-op, or failure
   - `ребейз`: success, no-op, or failure
   - `пуш`: existing success/failure output plus publish summary
   - `мердж дан`: merge anchor used, hygiene result, remote branch status, and notice that the tracked log line was appended

## 10. Failure Semantics

1. Fail closed.
   If preconditions are not met, stop before mutation unless the protocol definition explicitly allows a no-op result.

2. `комит`
   - staged-index inheritance is a hard failure
   - if no includable paths exist, return no-op
   - on commit failure, do not leave extra staged paths behind

3. `ребейз`
   - if the rewrite set is empty, return no-op
   - on any rewrite failure, restore the original `HEAD`
   - do not leave `.git/rebase-*` state behind

4. `пуш`
   - if there is no publishable local work, return clear no-op
   - if local unpublished work exists, do not silently skip it
   - if publish materialization fails, do not leave a half-published branch state without reporting failure clearly

5. `мердж дан`
   - if there is no valid PR-mode anchor, stop
   - if merge verification fails, stop before hygiene
   - if hygiene fails, do not append the merge-confirmation log line
   - if remote branch deletion is not confirmed, treat that as a reported best-effort gap, not an automatic protocol failure

## 11. Validation Matrix

Minimum validation matrix:

1. `комит` with tracked modifications and safe includable untracked files:
   exact current classifier is reused, preview is shown, one local commit is created, no push happens.

2. `комит` with pre-staged index content:
   protocol refuses before mutation.

3. `комит` with only excluded or unclear untracked files:
   protocol returns clean no-op.

4. `ребейз` on the default branch:
   protocol refuses before mutation.

5. `ребейз` with one local unpublished commit on a feature branch:
   protocol rewrites only that commit message non-interactively.

6. `ребейз` with multiple local unpublished commits on a feature branch:
   protocol replaces them with exactly one new local commit and does not touch pushed history.

7. `ребейз` conflict path:
   protocol restores original `HEAD` and leaves no in-progress rebase state.

8. `пуш` with normal tracked or supported untracked work saved locally on the current branch:
   protocol publishes that saved local work through a PR and still produces one normal publish commit.

9. `пуш` when local unpublished commits exist but the worktree is clean:
   protocol still publishes the saved local work instead of no-oping.

10. `пуш` when there is truly no unpublished local work to publish:
   protocol returns clear no-op.

11. `мердж дан` immediately after a successful PR merge on the last published feature branch:
    protocol resolves the last PR-mode success marker, verifies that exact PR was merged, runs hygiene, verifies files still look correct, and appends the required `merge-confirmed ...` log line.

12. `мердж дан` when the most recent success marker is `mode=no-pr`:
    protocol refuses as not applicable.

13. `мердж дан` when the current branch before cleanup is unrelated to the last PR-mode success marker:
    protocol refuses as ambiguous.

14. `мердж дан` when hygiene succeeds but remote feature branch deletion is not confirmed:
    protocol still succeeds, appends the merge-confirmation log line with `remote_branch=present` or `unknown`, and reports the remaining manual/best-effort step.

15. Existing publish-flow regression tests still pass:
    one normal publish commit, PR creation, success marker append, rollback hint, and post-merge hygiene behavior are preserved.

## 12. Acceptance Criteria

This spec is satisfied only if all of the following are true:

1. `комит` is implementation-ready:
   exact file classifier reuse is required, preview is mandatory, and one fixed local checkpoint commit is created.

2. `ребейз` is implementation-ready:
   the supported non-interactive model is explicitly limited to deterministic reword-or-squash cleanup of local unpublished commits only, and it remains optional.

3. `пуш` is implementation-ready:
   it is self-authorizing, it publishes saved local work from the current branch through PR, and it no longer depends on dirty worktree state as the only publish input.

4. `пуш` keeps the current healthy publish result:
   one normal publish commit, explicit staging, PR behavior, rollback reporting, and current publish-marker behavior remain intact.

5. `мердж дан` is implementation-ready:
   the merge anchor is explicit, merge verification is explicit, hygiene rules are explicit, file verification remains part of finalization, and merge confirmation is appended to the tracked repo log after success.

6. The spec stays narrow.
   It does not broaden into generic interactive rebase support, a separate git platform, or a larger workflow redesign.
