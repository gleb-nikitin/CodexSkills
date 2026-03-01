# Skills Workspace Handoff

## Scope

- Workspace: `/Users/glebnikitin/work/rss/skills`
- Internal maintainer folder: `/Users/glebnikitin/work/rss/skills/agent`
- Public agent entrypoint: `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`

## State To Carry Forward

- The serious `git-publish` stabilization phase is finished.
- The accepted production workflow is:
  1. `prepare`
  2. user review
  3. `publish`
  4. user merges PR
  5. agent runs post-merge cleanup
- The one-commit PR flow is working in production.
- Post-merge local cleanup is part of the standard protocol.

## Current Repo State

Treat repo state as live, not frozen in this file.

Before acting, verify locally:
- current branch
- current HEAD
- `git status --short`
- whether any feature branch from the last publish/cleanup cycle still exists

Do not assume this file contains the latest worktree snapshot.

## Source Of Truth Files

Use these in this order:
1. `/Users/glebnikitin/work/rss/skills/AGENTS.md`
2. `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`
3. `/Users/glebnikitin/work/rss/skills/agent/git-publish-current-state.md`
4. `/Users/glebnikitin/work/rss/skills/agent/git-roadmap.md`
5. `/Users/glebnikitin/work/rss/skills/agent/log.md`

## What Is Already Solved

- One publish action creates one normal commit
- No standalone marker-only commit
- PR body keeps pre-publish log context
- Untracked directories do not crash `prepare`
- Recursive file-level planning now works for brand new untracked project directories
- `publish` rejects repo/mode mismatch between CLI and saved plan
- Legacy one-shot no-op behavior is preserved on empty include sets

## What Is Still Deferred

- runtime-only enforcement of some policy rules
- durable plan storage outside `/tmp`
- automated remote feature branch deletion after merge

See `/Users/glebnikitin/work/rss/skills/agent/git-roadmap.md` for the deferred list.

## Practical Rule For Next Agent

Do not reload old spec/review history unless a current problem forces it.

For normal work, `git-publish/SKILL.md` should be enough.
