---
name: infra-bootstrap
description: "Deterministic onboarding for a new Vast.ai GPU server used in SDXL training. Use when Codex must run explicit preflight/bootstrap with a single JSON config: connect to server, verify GPU, ensure remote directories, upload one dataset, ensure base model file, validate Python imports, and write a concise machine-readable report."
---

# Infra Bootstrap (v2)

Default flow is `v2` and requires explicit config.
Old heuristic flow is `legacy` and is not default.

## Trigger Conditions

Use this skill when task is onboarding/preflight of a new Vast.ai GPU server for SDXL.

## Input Contract

Pass one JSON file with explicit fields:
- `server`: `host`, `port`, `ssh_key`
- `remote_dirs`: list of directories to `mkdir -p`
- `dataset`: `local_path`, `remote_path`
- `model`: `local_path`, `remote_path`
- `python_checks`: `python_bin`, `required_imports`

Example schema: `references/config.example.json`

## Commands

Validate config only:

```bash
cd /Users/glebnikitin/Projects/CodexSkills
./skills/infra-bootstrap/scripts/run validate-config --config ./skills/infra-bootstrap/references/config.example.json
```

Run end-to-end v2:

```bash
cd /Users/glebnikitin/Projects/CodexSkills
./skills/infra-bootstrap/scripts/run setup --config ./skills/infra-bootstrap/references/config.example.json
```

Legacy flow (not default):

```bash
cd /Users/glebnikitin/Projects/CodexSkills
./skills/infra-bootstrap/scripts/run legacy setup --dataset <name> --server <server_name>
```

## Safety and Idempotency

- Safe to run repeatedly.
- Default mode never uses delete sync behavior.
- `--destructive` is required to enable `rsync --delete` for dataset sync.
- Fail-fast: report includes `failed_step` and error message.

## Artifact Source Policy

- Production bootstrap uses ready artifacts from Storage Box / persistent storage only.
- This skill does not include model download from Google Drive as part of standard flow.
- Any Google Drive downloader scripts are legacy/pre-prod fallback tools and must be used outside normal bootstrap runs.

## Report Format

`setup` writes one JSON report (default: `./logs/infra/bootstrap_v2_<timestamp>_<runid>.json`):
- `version`, `status`, `started_utc`, `finished_utc`
- `config`, `destructive`
- `steps[]`: `{step, status, details}`
- on failure: `failed_step`, `error`

## Troubleshooting

- `validate_config`: fix missing paths/fields in config.
- `connect_server`: verify SSH host/port/key and network reachability.
- `verify_gpu`: ensure NVIDIA runtime is enabled and `nvidia-smi` works on remote.
- `validate_python_imports`: install missing Python packages in remote environment.
