# Runbook

## When to Load
- Load only when executing, building, or validating.

## Commands
- Check roadmap state:
  - `sed -n '1,120p' /Users/glebnikitin/work/rss/skills/agent/roadmap/state.md`
- Infra bootstrap v2 config validation:
  - `/Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/run validate-config --config /Users/glebnikitin/work/rss/skills/infra-bootstrap/references/config.example.json`
- Infra bootstrap v2 setup:
  - `/Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/run setup --config /Users/glebnikitin/work/rss/skills/infra-bootstrap/references/config.example.json`
- Infra bootstrap legacy flow:
  - `/Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/run legacy setup --dataset <name> --server <server_name>`
- Quick syntax validation:
  - `python3 -m py_compile /Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/bootstrap_v2.py /Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/infra_bootstrap.py`
  - `bash -n /Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/run`

## Notes
- `git-publish` operational rules live in `git-publish/SKILL.md`.
- Archived donor implementation is available at `archive/git-publish-v4.5-donor/` when recovery/reference is needed.
