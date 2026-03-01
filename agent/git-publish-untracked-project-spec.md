# git-publish Untracked Project Directory Spec

## Status

Closed on 2026-03-01 after the focused `git-publish` update shipped and passed the required validation matrix.

Implemented result:
- `prepare` now expands brand new untracked project directories recursively instead of reporting the whole directory as one `excluded-untracked` item
- safe text/code/doc files inside those directories can now be included at file level, including `.gitignore`
- obvious local/build/junk paths are excluded at file level with explicit reasons for `.claude/`, `dist/`, and `.DS_Store`
- `publish` still stages only the approved included files itself
- manual pre-staging is still unnecessary and still rejected because `publish` requires a clean index
- drift detection still fails when prepared untracked content changes before publish
- tracked-change workflows, one-commit publish semantics, and PR-mode rollback/output behavior were preserved

## Goal

Allow `git-publish` to create a normal PR from a brand new untracked project directory when only a selected subset of files should be included.

Current pain point:
- a new untracked directory is currently classified as one directory-level `excluded-untracked` item
- `prepare` does not expand it into file-level candidates
- manual pre-staging cannot be used as a workaround because `publish` intentionally requires a clean index

Desired outcome:
- an agent can run `prepare`
- review file-level include/exclude results for a new project directory
- run `publish`
- get one normal commit and one normal PR without breaking current safety rules

## Example Scenario

Problematic real-world case:
- `/Users/glebnikitin/work/code/tests/3-code-editor`

Desired include examples:
- project docs/specs
- `index.html`
- `src/main.ts`
- `tsconfig.json`
- `.gitignore`

Desired exclude examples:
- `.claude/`
- `dist/`
- `.DS_Store`

## Scope

Files allowed to change in the implementation:
- `/Users/glebnikitin/work/rss/skills/git-publish/scripts/git_publish.py`
- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
- `/Users/glebnikitin/work/rss/skills/agent/git-publish-current-state.md`

This spec file itself:
- `/Users/glebnikitin/work/rss/skills/agent/git-publish-untracked-project-spec.md`

## Non-Goals

Do not include these in this spec:
- publish-flow redesign
- changes to one-commit publish semantics
- relaxation of clean-index requirements for `publish`
- manual pre-staging workflows
- `git_hygiene` changes
- remote branch deletion automation

## Keep These Invariants

- `prepare -> review -> publish` remains the standard flow
- one publish action still creates exactly one normal commit
- no marker-only commit
- `publish` still requires a clean index before applying the prepared plan
- explicit staging only inside `publish`
- drift checks remain in place
- PR creation flow remains unchanged
- success marker remains inside the main publish commit
- tracked-change behavior that already works must not regress

## Required Behavior Change

### 1. Recursive planning for untracked directories

When `prepare` sees an untracked directory, it must no longer treat the whole directory as a single `excluded-untracked` item.

Instead:
- inspect the directory contents recursively
- classify contained paths at file level
- emit included and excluded items as concrete project-relative paths

Example desired output shape:
- included:
  - `3-code-editor/index.html`
  - `3-code-editor/src/main.ts`
  - `3-code-editor/tsconfig.json`
  - `3-code-editor/.gitignore`
- excluded:
  - `3-code-editor/.claude/` or contained paths under it
  - `3-code-editor/dist/` or contained paths under it
  - `3-code-editor/.DS_Store`

## 2. Inclusion model for new project files

Use a conservative default.

For files discovered inside a new untracked directory:
- include only narrow safe text/code/doc files by default
- exclude junk paths
- exclude unclear/sensitive paths
- exclude obvious local/build/artifact directories and their contents
- exclude anything not matched by the safe include model

This must preserve the current safety posture.

## 3. Directory-level exclude behavior

The implementation must support directory-level exclusions for obvious local/build directories.

Minimum examples to handle well:
- `.claude/`
- `dist/`
- `.DS_Store`

The spec does not require a perfect global ignore engine.
A small explicit directory/file exclusion model is acceptable if it solves the real workflow cleanly.

## 4. Optional `.gitignore` awareness

This is allowed, but not required, in the first implementation.

If the implementation can safely and minimally use a project-local `.gitignore` as part of filtering, that is acceptable.
But do not make the whole fix depend on building a complex ignore interpreter.

The priority is:
- recursive file-level planning
- safe include defaults
- obvious junk/build/local exclusions

## 5. Publish semantics for approved files

After `prepare`, `publish` must still:
- stage only the approved included paths
- create one normal commit
- avoid any requirement for manual pre-staging

The new capability must come from better prepare-time planning, not from relaxing publish safety.

## 6. Review output expectations

For a new untracked project directory, `prepare` output must make review practical.

The user/agent should be able to see:
- which specific files from the new directory will be included
- which specific files or subpaths are excluded
- why they are excluded

A directory-level `excluded-untracked` line for the entire project is no longer sufficient for this scenario.

## 7. Drift semantics

Do not weaken current drift protection.

The implementation may need more detailed fingerprints for recursively planned untracked content.
That is acceptable and expected.

But the rule must remain:
- if the prepared repo state changed materially before publish, publish fails and requires a fresh `prepare`

## Validation Expectations

Minimum validation matrix:

1. New untracked directory with safe source/doc files only:
   - `prepare` emits file-level included paths
   - `publish` succeeds
2. New untracked directory with mixed safe files and junk/local artifacts:
   - safe files included
   - junk/local artifacts excluded with reasons
3. `.claude/` inside the new directory is excluded
4. `dist/` inside the new directory is excluded
5. `.DS_Store` inside the new directory is excluded as junk
6. Manual pre-staging remains unnecessary and still rejected by `publish`
7. Existing tracked-change workflow still behaves as before
8. One publish action still creates exactly one normal commit
9. PR mode still creates a normal PR with the same rollback/output behavior
10. Drift detection still fails when prepared untracked content changes before publish

## Acceptance Criteria

This spec is satisfied when:
- an agent can publish a brand new project directory through `git-publish`
- only the intended safe files are included
- junk/build/local paths from that new directory are excluded cleanly
- no manual out-of-band staging is needed
- current tracked-change workflows do not regress
- one-commit PR behavior remains intact

## Notes For Implementer

Keep this minimal and pragmatic.

The target is not a perfect generic ignore engine.
The target is a reliable planning model for the common repo workflow:
- a new project directory starts untracked
- the agent needs to include only the right files
- the PR should still be created through the normal guarded `git-publish` flow
