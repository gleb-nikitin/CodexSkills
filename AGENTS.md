# Agent Policy v3

## Managed generated File
Manual edits are prohibited.

## Scope
- Project data path for files that must not go to git: `/Users/glebnikitin/disk/<this-folder-name>/`
- Server data-path for web-facing interfaces: `/Users/glebnikitin/work/server/<this-folder-name>/`
- This folder and subfolders.
- Never traverse outside unless user request or task requires an allowed external path.

## Shared resources
Load only if needed. Index of available resources: `/Users/glebnikitin/work/rss/index.md`

## GIT operations
use: `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md`

## Rule Priority
1. User instructions.
2. Local in-scope `AGENTS.md`.

## Safety
- Warn if user request leads to unsafe, destructive, or policy-conflicting actions.

## Cold Start
1. Read `./agent/specs/roadmap/state.md`.
2. If `active_spec` is not `none`, open that spec before making changes.
3. `state.md` is the freshest current-state file. Trust it first; other context files may lag behind.

## Context Files

### Lazy-Load Policy
- Don't load: context, historical docs or how-to files by default.
- Load only when active task explicitly requires.
- Any file whose name contains `human` is not for LLM use; do not load it unless the user explicitly asks.

### Context Files
- `./agent/docs/kb.md` — lazy-load index for references, handoff notes, and known debt. Load when needed.
- `./agent/docs/arch.md` — ≤ 180 lines. Architecture, stack, boundaries. Load for design/runtime changes.
- `./agent/docs/run.md` — commands and validation. Load when executing, building, or validating.
- `./agent/docs/context.md` — ≤ 120 lines. Snapshot and current focus only.
- Keep all context files compact and suitable for no-history sessions.
- Maintain lazy-load index in `kb.md`.
- Before deleting legacy context files: verify coverage of commands, learnings, regressions, diagnostics.
- Missing coverage blocks deletion.

### How To
- `./agent/how-to/index.md` - Load when planning a spec. Index of known problems with links to full proven solution context including working code (if needed).
- add a file on spec acceptance if you experienced problems while executing other agents need to know about or user requests it.

### Roadmap
- `./agent/specs/roadmap/state.md` — current active spec pointer and important notes for next no-history session. Links to next planned specs after completion of current spec for multi-spec que.
- `./agent/specs/roadmap/archive.md` — completed specs (newest first). Don't load until needed.
- `./agent/specs/roadmap/intent.md` — project goals and direction. Load when planing a spec.

### Spec Lifecycle
- Specs live at `./agent/specs/NNN-kebab-name.md`.
- One active spec at a time.
- If `roadmap/state.md` and active spec conflict: stop and ask user.
- Spec execution: stop only if required input is missing or an assumption would change behavior.

### On Spec Completion
1. Ask for spec acceptance. After the spec is accepted proceed to 2.
2. Copy completed entry to `./agent/specs/roadmap/archive.md` (newest first).
3. Rewrite `./agent/specs/roadmap/state.md` fully (active_spec, last_finished, next_spec, queue).
4. Update `./agent/docs/kb.md` session handoff block.
5. Append `milestone` entry to `./agent/log.md`.

### Session Handoff (in kb.md)
- Format:
  - date:
  - what changed:
  - why:
  - risks:
  - next checks:
- Updated on every spec completion or significant change.

## Execution model protocols

### Discuss protocol
- This is the default mode.
- Don't change anything besides context files to finilize discussion results.
- Brainstorm with user to prepare all the important context files.
- Intent first. Carefully log the intents in `./agent/specs/roadmap/intent.md`.
- Global intents: project goals
- Planned intents: project trajectory
- If a desicion or action gets the project closer to global intents it's a sucess.
- Moving towards global intents is the ultimate sucess criteria.

### Overlord protocol
- protocol is activated when a user askes for overlored mode or to execute single/multiple specs in roadmap
- ask questions if needed before start
- you are the CTO now and all decisions are yours
- user may not respond till the job is done
- stop only if something needs critical user input
- load full project context; `intent.md` is your priority as sucess
- don't write specs or execute, spawn agents to perform tasks
- you can accept a spec as done and move on to the next
- user accepts final results
- after no active intents are left fallback to discuss protocol

### Plan protocol
- protocol is activated when user or agent asks for new spec to be designed
- load needed project context
- user/agent task is your priority as sucess, `intent.md` is secondary priority.
- bugfixes must be added to a spec before it is closed by acceptance.
- if asked to execute while in plan mode switch to Overloard Protocol.

### Execute protocol
- protocol is activated when you are in default discuss protocol and asked to execute
- ask questions if possible and needed before executing unless instructed not to ask questions
- if you are given a ready spec: your task is to execute it
- if there is no ready spec execute the tasks and log the execution result in the opened spec

## Logging
- Format: `YYYY-MM-DD HH:MM | category | action | result`
- Categories (log meaningful events only):
  - `milestone` — completed phase or deliverable.
  - `validation` — check result with outcome.
  - `policy` — rule applied that changed execution path.
  - `incident` — unexpected failure, error, or deviation from plan.
- Do not log micro-steps, context loads, file reads, or routine tool calls.
- Timestamps: current write-time only. No backfill or retroactive timestamps.

## Baseline Defaults
- Documentation/logs/context files: English, concise, LLM-efficient.
- If blocked and user unavailable: stop execution and log blocking reason.
- Never repeat the same failed action more than twice without new input.
- Verify paths, files, and dependencies before executing scripts.
- Agent may propose improvements but must not execute non-requested improvements without approval.
