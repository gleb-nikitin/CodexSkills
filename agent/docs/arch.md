# Architecture

## Purpose
- Maintain deterministic, reusable local skills with explicit contracts and safety-first defaults.
- Current focus domains: safe git publish protocols (`git-publish`) and Vast.ai SDXL server onboarding (`infra-bootstrap`).

## Stack
- Markdown-first skill definitions (`SKILL.md`).
- Python 3 scripts for infra bootstrap orchestration and reporting.
- Bash launcher wrapper (`infra-bootstrap/scripts/run`) for mode dispatch.

## Boundaries
- In scope: this repository (`/Users/glebnikitin/work/rss/skills`) and its subfolders.
- Project non-git data path: `/Users/glebnikitin/disk/skills/`.
- Server-facing data path: `/Users/glebnikitin/work/server/skills/`.
- Do not operate outside scope unless explicitly requested by the user.

## Key Files
- `/Users/glebnikitin/work/rss/skills/AGENTS.md` — local policy and execution model.
- `/Users/glebnikitin/work/rss/skills/git-publish/SKILL.md` — git protocol rules and CLI surface.
- `/Users/glebnikitin/work/rss/skills/infra-bootstrap/SKILL.md` — infra bootstrap contract and usage.
- `/Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/run` — launcher for `bootstrap_v2.py` / legacy mode.
- `/Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/bootstrap_v2.py` — current deterministic bootstrap flow.
- `/Users/glebnikitin/work/rss/skills/infra-bootstrap/scripts/infra_bootstrap.py` — legacy bootstrap flow.
- `/Users/glebnikitin/work/rss/skills/agent/roadmap/state.md` — freshest execution state.
