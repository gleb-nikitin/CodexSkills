#!/usr/bin/env bash
set -euo pipefail

REPO=""
APPLY=0
REMOTE=""

is_apply_blocked_by_repo_state() {
  local line
  local x
  local y
  local has_staged=0
  local has_unstaged=0

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue

    x="${line:0:1}"
    y="${line:1:1}"

    case "$x$y" in
      '??'|'!!')
        continue
        ;;
      'UU'|'AA'|'DD'|'AU'|'UA'|'DU'|'UD')
        echo "Refusing --apply with unresolved merge/conflict state. Harmless untracked files are allowed, but conflicts must be resolved first." >&2
        return 0
        ;;
    esac

    if [[ "$x" != " " ]]; then
      has_staged=1
    fi
    if [[ "$y" != " " ]]; then
      has_unstaged=1
    fi
  done < <(git status --porcelain=v1)

  if [[ "$has_staged" -eq 1 ]]; then
    echo "Refusing --apply with staged changes. Harmless untracked files are allowed, but staged state still blocks hygiene." >&2
    return 0
  fi

  if [[ "$has_unstaged" -eq 1 ]]; then
    echo "Refusing --apply with tracked unstaged changes. Harmless untracked files are allowed, but tracked dirty state still blocks hygiene." >&2
    return 0
  fi

  return 1
}

is_untracked_conflict_output() {
  local output="$1"

  case "$output" in
    *"untracked working tree files would be overwritten by checkout"*|\
    *"untracked working tree files would be removed by checkout"*|\
    *"untracked working tree files would be overwritten by merge"*|\
    *"untracked working tree files would be removed by merge"*|\
    *"Updating the following directories would lose untracked files in them:"*)
      return 0
      ;;
  esac

  return 1
}

exit_for_untracked_conflict() {
  local phase="$1"
  local output="$2"

  echo "Cleanup blocked by an actual untracked-file ${phase} conflict. Harmless untracked files are allowed, but this run would overwrite or remove local untracked paths." >&2
  if [[ -n "$output" ]]; then
    printf '%s\n' "$output" >&2
  fi
  exit 2
}

usage() {
  echo "Usage: git_hygiene.sh --repo <path> [--remote <name>] [--apply]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --remote)
      REMOTE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$REPO" ]]; then
  echo "Missing required flag: --repo <path>" >&2
  usage
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 2
fi

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repo: $REPO" >&2
  exit 2
fi

cd "$REPO"

if [[ "$APPLY" -eq 1 ]]; then
  if is_apply_blocked_by_repo_state; then
    exit 2
  fi
fi

current_branch_initial="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"

detect_remote() {
  if [[ -n "$REMOTE" ]]; then
    if git remote | grep -Fxq "$REMOTE"; then
      echo "$REMOTE"
      return
    fi
    echo "Unknown remote: $REMOTE" >&2
    exit 2
  fi

  if [[ -n "$current_branch_initial" ]]; then
    local branch_remote
    branch_remote="$(git config --get "branch.${current_branch_initial}.remote" || true)"
    if [[ -n "$branch_remote" ]] && git remote | grep -Fxq "$branch_remote"; then
      echo "$branch_remote"
      return
    fi
  fi

  if git remote | grep -Fxq "origin"; then
    echo "origin"
    return
  fi

  git remote | head -n 1
}

selected_remote="$(detect_remote)"

tracked_remotes="$(
  git for-each-ref --format='%(upstream:remotename)' refs/heads \
    | awk 'NF' \
    | sort -u
)"

echo "== status =="
git status -sb
echo "== remote =="
if [[ -n "$selected_remote" ]]; then
  echo "$selected_remote"
else
  echo "(none)"
fi

gone_branches="$(
  git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads \
    | awk '$2 ~ /\[gone\]/ {print $1}'
)"

if [[ -n "$gone_branches" ]]; then
  echo "== gone local branches =="
  echo "$gone_branches"
else
  echo "== gone local branches =="
  echo "(none)"
fi

if [[ "$APPLY" -eq 0 ]]; then
  echo "dry-run: no changes applied (use --apply)."
  exit 0
fi

remotes_to_refresh="$tracked_remotes"
if [[ -n "$selected_remote" ]]; then
  remotes_to_refresh="$(printf '%s\n%s\n' "$remotes_to_refresh" "$selected_remote" | awk 'NF' | sort -u)"
fi

if [[ -n "$remotes_to_refresh" ]]; then
  while IFS= read -r remote_name; do
    [[ -z "$remote_name" ]] && continue
    if ! git fetch "$remote_name" --prune --quiet; then
      echo "Fetch failed for remote '$remote_name'; aborting --apply to avoid stale cleanup decisions." >&2
      exit 2
    fi
  done <<< "$remotes_to_refresh"
fi

gone_branches_after_fetch="$(
  git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads \
    | awk '$2 ~ /\[gone\]/ {print $1}'
)"

if git show-ref --verify --quiet refs/heads/main; then
  checkout_stderr="$(mktemp)"
  if git checkout main >/dev/null 2>"$checkout_stderr"; then
    rm -f "$checkout_stderr"
    main_upstream_remote="$(git config --get branch.main.remote || true)"
    main_upstream_merge="$(git config --get branch.main.merge || true)"
    if [[ -n "$main_upstream_remote" ]] && [[ -n "$main_upstream_merge" ]] && git remote | grep -Fxq "$main_upstream_remote"; then
      main_upstream_branch="${main_upstream_merge#refs/heads/}"
      if git show-ref --verify --quiet "refs/remotes/$main_upstream_remote/$main_upstream_branch"; then
        pull_stderr="$(mktemp)"
        if ! git pull --ff-only "$main_upstream_remote" "$main_upstream_branch" 2>"$pull_stderr"; then
          pull_output="$(cat "$pull_stderr")"
          rm -f "$pull_stderr"
          if is_untracked_conflict_output "$pull_output"; then
            exit_for_untracked_conflict "update" "$pull_output"
          fi
          echo "warning: unable to fast-forward main from '$main_upstream_remote/$main_upstream_branch'; continuing cleanup." >&2
        else
          rm -f "$pull_stderr"
        fi
      fi
    elif [[ -n "$selected_remote" ]] && git show-ref --verify --quiet "refs/remotes/$selected_remote/main"; then
      pull_stderr="$(mktemp)"
      if ! git pull --ff-only "$selected_remote" main 2>"$pull_stderr"; then
        pull_output="$(cat "$pull_stderr")"
        rm -f "$pull_stderr"
        if is_untracked_conflict_output "$pull_output"; then
          exit_for_untracked_conflict "update" "$pull_output"
        fi
        echo "warning: unable to fast-forward main from '$selected_remote/main'; continuing cleanup." >&2
      else
        rm -f "$pull_stderr"
      fi
    fi
  else
    checkout_output="$(cat "$checkout_stderr")"
    rm -f "$checkout_stderr"
    if is_untracked_conflict_output "$checkout_output"; then
      exit_for_untracked_conflict "checkout" "$checkout_output"
    fi
    echo "warning: unable to checkout 'main' (possibly used by another worktree); skipping main fast-forward update." >&2
  fi
fi

current_branch_now="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"

if [[ -n "$gone_branches_after_fetch" ]]; then
  while IFS= read -r branch; do
    [[ -z "$branch" || "$branch" == "main" || "$branch" == "$current_branch_now" ]] && continue
    if ! git branch -D "$branch" >/dev/null 2>&1; then
      echo "warning: unable to delete branch '$branch' (possibly checked out in another worktree); skipping." >&2
      continue
    fi
  done <<< "$gone_branches_after_fetch"
fi

echo "== final status =="
git status -sb
