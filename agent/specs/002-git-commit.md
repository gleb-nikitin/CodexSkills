# Spec 002: git-publish commit

## Context

git-publish skill has a protocol definition (`SKILL.md`) but no implementation — runtime scripts don't exist yet. The v4.5 donor archive (2084-line Python + 284-line bash) is a reference only; we build from scratch.

This spec implements the first and simplest operation: `commit` (local safepoint). Every future operation (`push pr`, `push no-pr`, `merge-done`) builds on this foundation, so we establish the script structure, safety filters, and output conventions here.

## Deliverable

**One file:** `git-publish/scripts/run` (bash, executable)

## Interface

```
run commit --repo /absolute/path [point name words...]
```

- `--repo` is required. Must be absolute path to a git repo. Must not be workspace root (`/Users/glebnikitin/work`).
- Remaining positional args form the point name for the commit message.
- If no point name given: use `wip: local checkpoint`.

## What it does

1. **Validate** `--repo` exists, is a git repo, and is not workspace root.
2. **Collect changes** via `git status --porcelain` (modified, deleted, renamed, untracked).
3. **Filter** each path against the hardcoded exclude list.
4. **Stage** each included file individually (`git add -- <path>`).
5. **Commit** with the point name as message.
6. **Report** results to stdout.

## Exclude rules (from SKILL.md)

Hardcoded exclude patterns — a file is excluded if:
- Basename is `.DS_Store` → reason: `os-junk`
- Path starts with `.claude/` → reason: `local-agent`
- Basename matches `.env` or `.env.*` → reason: `secret`
- Extension is `.pem`, `.key`, `.p12`, or `.pfx` → reason: `secret`
- Path starts with `dist/` → reason: `build-artifact`
- Basename starts with `~` or ends with `.swp`, `.swo` → reason: `editor-temp`

If a file is excluded, report it with the reason.

## Output format (plain text)

**Success:**
```
committed <short-sha>
point: <point-name>
included (N):
  M  path/to/file
  ?  path/to/new-file
excluded (N):
  .DS_Store (os-junk)
  .env.local (secret)
```

**Nothing to commit:**
```
nothing to commit
```

**Error:**
```
error: <message>
```
Errors go to stderr, exit 1.

## Exit codes

- `0` — commit created or nothing to commit
- `1` — error (bad repo, git failure)

## What it does NOT do

- No push, no branch creation, no PR
- No plan files, no JSON output
- No project log writes (caller's responsibility)
- No `rebase` support
- No `--json`, `--remote`, `--base` flags (added with future operations)

## Architecture notes for future operations

The `run` script uses a simple dispatch pattern:
```
case "$ACTION" in
  commit) do_commit ;;
  push)   do_push ;;   # future spec
  merge-done) do_merge_done ;;  # future spec
  *) usage; exit 2 ;;
esac
```

Safety filter functions are shared across all operations. Adding a new operation = adding a new function and a case branch.

## Acceptance criteria

1. `run commit --repo <valid-repo-path>` creates exactly one local commit with all safe changes.
2. `run commit --repo <path> my safepoint name` uses "my safepoint name" as commit message.
3. Excluded files (secrets, junk, build artifacts) are never staged.
4. Output reports SHA, included files, and excluded files with reasons.
5. Nothing-to-commit case exits 0 with message.
6. Invalid repo / non-git-dir / workspace-root all exit 1 with clear error.
7. No push, no branch, no side effects beyond the one commit.

## Verification

```bash
# Setup test repo
TESTREPO=$(mktemp -d)
cd "$TESTREPO" && git init && echo "hello" > file.txt && git add . && git commit -m "init"

# Test 1: basic commit
echo "change" >> file.txt
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run commit --repo "$TESTREPO" test point
# Expect: committed <sha>, point: test point, file.txt included

# Test 2: excluded files
touch .DS_Store .env.local
echo "mod" >> file.txt
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run commit --repo "$TESTREPO" with excludes
# Expect: file.txt included, .DS_Store and .env.local excluded

# Test 3: nothing to commit
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run commit --repo "$TESTREPO"
# Expect: "nothing to commit", exit 0

# Test 4: workspace root rejection
/Users/glebnikitin/work/rss/skills/git-publish/scripts/run commit --repo /Users/glebnikitin/work
# Expect: error, exit 1

# Cleanup
rm -rf "$TESTREPO"
```

## Files to create/modify

| File | Action |
|------|--------|
| `git-publish/scripts/run` | Create (new bash script, ~120 lines) |
| `agent/roadmap/state.md` | Update active_spec to 002 |
| `agent/specs/002-git-commit.md` | Create (copy of this spec) |
