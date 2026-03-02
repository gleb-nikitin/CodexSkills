# git-publish Integrity Manifest Spec

## Status

Proposed on 2026-03-02.

This is a narrow spec for the existing `git-publish` skill.
It does not define a new skill.
It does not include implementation.

## Goal

Add one low-noise integrity check layer to the healthy PR publish cycle:
- after `prepare`, but before real `publish`, capture a manifest of the prepared project file scope
- after merge and hygiene, verify that the merged result for that scope still matches what `prepare` selected

This is not a backup system.
This is not full-repo hashing.
This is not a protocol redesign.
It must not turn `пуш` into a two-step approval workflow.

## Scope

This spec is for the current PR flow:
1. user invokes `пуш`
2. `prepare` runs internally
3. the manifest is written for the prepared scope
4. `publish` runs immediately and creates the PR
5. the tool reports what was published
6. the user reviews the PR before merge
7. the user merges the PR
8. `merge-done` runs hygiene
9. integrity verification runs
10. final merge confirmation is appended

`no-pr` stays unchanged in this spec.

## Non-Goals

Do not add any of the following:
- file-copy snapshots
- repo-local manifest storage
- full-repo hashing by default
- retention or archive-management policy
- new publish modes
- weakening of current drift checks, clean-index rules, or hygiene safety checks
- broad changes to project-log semantics beyond what is strictly needed to find the right manifest later

## Keep These Invariants

- user-facing `пуш` remains self-authorizing and does not wait for an extra approval round after internal `prepare`
- internal `prepare -> publish` ordering stays unchanged
- `prepare` stays repo-read-only
- `publish` stays the only mutating publish step
- current classifier and include/exclude behavior stay unchanged
- explicit staging only stays unchanged
- current drift check before publish stays unchanged
- current hygiene behavior stays unchanged except for the added post-hygiene verification step
- manifests are stored only outside project repos

## 1. Purpose Of The Manifest

The manifest is a compact proof of what the internal `prepare` step selected for publication.

Its purpose is:
- record the exact prepared project file scope
- record the expected content hashes for that scope
- let `merge-done` detect unexpected changes introduced by the publish/merge cycle inside that scope

It is not meant to:
- restore files
- keep historical copies
- track unrelated repo state
- replace the current publish drift check

The current publish drift check still protects `prepare -> publish`.
The new manifest protects `prepare -> merge-done`.

## 2. Creation Point

The manifest must be created after `prepare` has finished computing and freezing the prepared plan, but before any real `publish` mutation happens.

Required timing:
- `prepare` computes included and excluded paths as it does today
- `prepare` freezes the plan as it does today
- `prepare` writes one external manifest for that prepared scope
- `prepare` records the manifest reference in the prepared plan used by the same `пуш` cycle

Important boundary:
- `prepare` must not mutate the repo
- writing the manifest to `/disk/git-publish/...` is allowed because it is external artifact creation, not repo mutation

If `prepare` is rerun, it creates a new manifest.
`publish` must use only the manifest reference attached to the prepared plan from that specific `prepare`.

## 3. Manifest Contents

The manifest must stay minimal and JSON-based.
Use `sha256` for content hashing.

Required top-level fields:
- `schema_version`
- `created_at_utc`
- `repo_name`
- `repo_root`
- `origin_url` if available
- `prepare_head`
- `mode`
- `base_branch`
- `target_branch`
- `plan_path` or plan token
- `manifest_path`
- `entries`

Required `entries` model:
- one entry per prepared project-relative path in scope
- plus one `protocol-log` entry when the current publish cycle will append protocol markers to the active project log
- deterministic ordering by relative path

Each entry must contain at least:
- `path`
- `entry_type`
- `expected_state`
- `sha256` for regular file content

Supported entry types for v1:
- `file`
- `delete`
- `protocol-log`
- `unsupported`

Entry rules:
- `file`: path is expected to exist in the merged result and match the stored `sha256`
- `delete`: path is expected to be absent in the merged result; no content hash is required
- `protocol-log`: path is intentionally managed by `git-publish`; do not use blocking hash verification for it
- `unsupported`: current v1 does not block on it; record it only to explain why it was skipped

Minimal useful extra metadata is allowed:
- `size_bytes`
- `executable`

Do not add copied file contents.

Hashing rule:
- the stored hash must represent the exact file bytes that `publish` intends to commit for that path
- do not hash mtimes, inode data, or unrelated metadata

## 4. What Is In Scope

The manifest scope is the prepared publish scope only.

Default rule:
- include only paths from the current `prepare` included set
- plus the active project log path as a special `protocol-log` entry for the current publish cycle

Do not include:
- excluded paths
- ignored paths
- unrelated clean repo files
- the whole repo by default

Special path rules:
- tracked deletions stay in scope as `delete` entries
- renames may be represented as one `delete` entry plus one `file` entry
- the active project log path is a protocol artifact and must be treated specially

## 5. Protocol Artifacts To Exclude Or Treat Specially

The manifest must not try to hash-verify protocol artifacts the same way as normal project files.

Required special handling:
- external plan files under `/tmp/git-publish-plans/...` are never in scope
- manifest files under `/disk/git-publish/...` are never in scope
- the active project log path (`./agent/log.md` or fallback `./log.md`) is `protocol-log`

Reason for special log handling:
- `publish` appends the success marker to that path
- `merge-done` appends the `merge-confirmed ...` line to that path
- a normal pre-publish content hash would otherwise create guaranteed false positives

For `protocol-log` entries:
- do not make content-hash equality a blocking integrity check
- keep relying on the existing publish-marker and merge-confirmation rules for that path

## 6. Storage Layout And Naming

All manifests must be stored centrally under:

`/disk/git-publish/<project-name>/<timestamp>-manifest.json`

Storage rules:
- `<project-name>` is the repo directory basename
- `<timestamp>` is UTC in a sortable filename-safe form such as `20260302T174512Z`
- if a same-second collision occurs, appending `-<prepare_head_short>` is acceptable
- create parent directories as needed
- do not write manifest artifacts inside the project repo

The manifest body must still include `repo_root` and `origin_url` so the file can be sanity-checked even if two repos share the same basename.

## 7. Minimal Durable Reference

`merge-done` cannot rely on `/tmp` plan files still existing.

So this spec requires one minimal durable reference from the publish cycle to the manifest:
- add the manifest filename or manifest id to the successful publish marker
- keep the rest of the marker semantics unchanged

Example shape:

```text
YYYY-MM-DD HH:MM | git-publish skill | push mode=pr branch=<name> base=<name> manifest=<timestamp-manifest> | success
```

This is the smallest durable link that lets `merge-done` find the correct central manifest later without introducing repo-local artifact files.

Older success markers without `manifest=` remain valid.
They simply mean integrity verification is unavailable for that older cycle.

## 8. Publish-Step Interaction

`publish` should remain operationally unchanged.

Required interaction:
- the user-facing `пуш` protocol is: run `prepare` internally, write the manifest, publish immediately to a PR, then report the result
- no extra approval round is required between internal `prepare` and `publish`
- if the implementation keeps a standalone `prepare` entrypoint, it is optional and not the required approval path for normal `пуш`
- `prepare` writes the manifest and stores its reference in the prepared plan
- `publish` validates repo/mode/plan drift exactly as it does today
- `publish` does not recompute or rewrite the manifest content
- `publish` carries the manifest reference into the durable success marker
- after publish, output reports the PR result and the manifest status compactly

This keeps the new layer attached to the existing flow without turning manifest generation into a second publish gate.

## 9. Post-Merge Verification

Verification happens inside `merge-done` after merge has been confirmed and hygiene has run successfully.

Verification target:
- the exact merged result for the PR cycle that produced the anchor publish marker
- not whatever unrelated later changes may have landed on `main`

Required verification steps:
1. resolve the last successful `push mode=pr` marker as `merge-done` already does
2. read `manifest=<...>` from that marker if present
3. load the manifest from `/disk/git-publish/<project-name>/...`
4. resolve the exact merged PR result commit/tree for that publish cycle
5. verify each manifest entry:
   - `file`: path exists and `sha256` matches
   - `delete`: path is absent
   - `protocol-log`: skip blocking hash verification
   - `unsupported`: skip blocking verification

If verification passes:
- continue with the existing final confirmation behavior
- append the normal `merge-confirmed ...` log line

## 10. Failure Semantics

This layer must be useful without making the healthy workflow brittle.

### Warning-only cases

These must warn and continue:
- manifest directory cannot be created
- manifest file cannot be written
- manifest file for an older publish cycle is missing
- manifest file is unreadable or malformed
- a manifest entry type is unsupported in v1
- the exact merged result tree cannot be resolved cleanly for verification
- the anchor publish marker predates this feature and has no `manifest=...`

Warning result:
- `publish` still works as today
- `merge-done` still completes hygiene and may append `merge-confirmed ...`
- output must clearly say `integrity verification skipped` or equivalent

### Blocking cases

These must block final integrity confirmation:
- manifest exists
- verification can run
- one or more `file` entries do not match
- one or more `delete` entries are unexpectedly present

Blocking result:
- `merge-done` exits non-zero
- do not append the final `merge-confirmed ...` line
- report only the mismatched paths plus expected vs actual state

This keeps the new hard stop reserved for real integrity mismatches, not missing infrastructure.

## 11. False-Positive Controls

To keep noise low:
- hash only the prepared included scope
- do not hash the whole repo
- treat the active project log path as protocol-managed
- verify against the exact merged PR result, not a later unrelated `main` state
- do not compare mtimes, timestamps, or filesystem metadata
- report only mismatches and skip reasons, not a giant per-file success dump

If standalone `prepare` output is shown, it should add only compact manifest info:
- manifest path
- manifest status: `ready` or `warning`

User-facing `пуш` output after publish should add only compact manifest info:
- manifest path or id
- manifest status: `ready` or `warning`

Merge-done output should add only compact integrity info:
- verification status: `passed`, `skipped`, or `failed`
- mismatched paths only when failed

## 12. Acceptance Criteria

This spec is satisfied when:
- the current healthy PR publish workflow still works without repo-local artifacts
- user-facing `пуш` remains `prepare internally -> publish to PR -> report result` with PR review before merge, not pre-publish approval after prepare
- `prepare` produces one central hash manifest for the prepared project file scope
- `publish` can carry a durable manifest reference forward without depending on `/tmp`
- `merge-done` can use that manifest to detect post-merge scope mismatches
- protocol-managed log mutations do not create false positives
- missing manifest infrastructure warns instead of breaking normal publish/cleanup
- real scope mismatches block final merge confirmation
