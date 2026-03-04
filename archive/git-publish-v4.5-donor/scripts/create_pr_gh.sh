#!/usr/bin/env bash
set -euo pipefail

BASE="${1:?Usage: create_pr_gh.sh <base> <head> <title> [body_file]}"
HEAD="${2:?Usage: create_pr_gh.sh <base> <head> <title> [body_file]}"
TITLE="${3:?Usage: create_pr_gh.sh <base> <head> <title> [body_file]}"
BODY_FILE="${4:-}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh not installed" >&2
  exit 2
fi

gh auth status -h github.com >/dev/null 2>&1 || {
  echo "gh is not authenticated (run: gh auth login)" >&2
  exit 2
}

# If a PR already exists for this head branch, just print its URL.
EXISTING_URL="$(gh pr list --head "$HEAD" --state open --json url --jq '.[0].url' 2>/dev/null || true)"
if [[ -n "${EXISTING_URL:-}" && "${EXISTING_URL:-null}" != "null" ]]; then
  echo "$EXISTING_URL"
  exit 0
fi

# If there are no commits between base and head, PR creation will fail. Treat as no-op.
ENC_HEAD="${HEAD//\//%2F}"
COMPARE_STATUS="$(gh api "repos/{owner}/{repo}/compare/${BASE}...${ENC_HEAD}" --jq '.ahead_by|tostring' 2>/dev/null || echo "")"
if [[ -n "${COMPARE_STATUS:-}" && "${COMPARE_STATUS:-}" == "0" ]]; then
  echo "[skip] no commits ahead of ${BASE} for ${HEAD}" >&2
  exit 0
fi

if [[ -n "$BODY_FILE" ]]; then
  gh pr create --base "$BASE" --head "$HEAD" --title "$TITLE" --body-file "$BODY_FILE"
else
  gh pr create --base "$BASE" --head "$HEAD" --title "$TITLE" --body ""
fi
