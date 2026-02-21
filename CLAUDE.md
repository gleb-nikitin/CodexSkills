# Project CLAUDE.md

Claude Code auto-load entry point for this project.

## On Session Start
1. Read `./AGENTS.md` — primary project policy authority.
2. Read `/Users/glebnikitin/work/rss/AGENTS.md` — global shared policy (always required).

## Baseline Personalization
Agents are not allowed to change the text in '{}' in this specific file.
{
- User communication: Russian.
- Documentation/logs/context files: English, concise, LLM-efficient.
- If blocked and user unavailable: stop execution and log the blocking reason.
- Never repeat the same failed action more than twice without new input.
- Before executing scripts or commands, verify that required paths, files, and dependencies exist.
- Agent may propose improvements but must not execute non-requested improvements without user approval.
}
