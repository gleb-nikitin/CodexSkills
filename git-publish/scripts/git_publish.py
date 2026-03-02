#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


JUNK_BASENAMES = {".DS_Store"}
SAFE_UNTRACKED_BASENAMES = {"AGENTS.md", "README.md", "SKILL.md", ".gitignore"}
SAFE_UNTRACKED_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".css",
    ".go",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
UNTRACKED_DIR_REASONS = {
    ".claude": "excluded-local",
    "dist": "excluded-build",
}
CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
CHECKPOINT_COMMIT_MESSAGE = "wip: local checkpoint"
WORKSPACE_ROOT = Path("/Users/glebnikitin/work").resolve()
PLAN_DIR = Path(tempfile.gettempdir()) / "git-publish-plans"
SCRIPT_DIR = Path(__file__).resolve().parent
PUSH_SUCCESS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \| git-publish skill \| "
    r"push mode=(?P<mode>pr|no-pr) branch=(?P<branch>\S+) base=(?P<base>\S+) \| success$"
)


def run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture_output: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture_output,
        check=check,
    )


def out(cmd: list[str], *, cwd: Path | None = None) -> str:
    return run(cmd, cwd=cwd).stdout.strip()


def git_ok(cmd: list[str], *, cwd: Path | None = None) -> bool:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def require_git_repo() -> Path:
    return Path(out(["git", "rev-parse", "--show-toplevel"]))


def git_repo_root(candidate: Path) -> Path:
    return Path(out(["git", "-C", str(candidate), "rev-parse", "--show-toplevel"]))


def default_remote_branch(remote: str) -> str:
    try:
        info = out(["git", "remote", "show", remote])
        match = re.search(r"HEAD branch:\s*(\S+)", info)
        if match:
            head_branch = match.group(1).strip()
            if head_branch and head_branch != "(unknown)":
                return head_branch
    except Exception:
        pass
    for branch in ("main", "master"):
        if git_ok(["git", "show-ref", "--verify", f"refs/heads/{branch}"]):
            return branch
    return "main"


def now_ts() -> str:
    return out(["date", "+%Y-%m-%d %H:%M"])


def resolve_project_log_path(project_root: Path) -> Path:
    agent_log = project_root / "agent" / "log.md"
    root_log = project_root / "log.md"
    if agent_log.exists():
        return agent_log
    if root_log.exists():
        return root_log
    return agent_log


def append_project_log(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def is_junk_path(path: str) -> bool:
    return Path(path).name in JUNK_BASENAMES


def is_unclear_path(path: str) -> bool:
    p = Path(path)
    basename = p.name.lower()
    suffix = p.suffix.lower()
    if basename in {".env", ".env.local"}:
        return True
    if suffix in {".key", ".pem", ".p12", ".pfx"}:
        return True
    return False


def is_safe_untracked_path(path: str) -> bool:
    p = Path(path)
    if p.name in SAFE_UNTRACKED_BASENAMES:
        return True
    return p.suffix.lower() in SAFE_UNTRACKED_SUFFIXES


def untracked_dir_reason(path: str) -> str | None:
    for part in Path(path).parts:
        reason = UNTRACKED_DIR_REASONS.get(part.lower())
        if reason:
            return reason
    return None


@dataclass(frozen=True)
class StatusEntry:
    code: str
    path: str
    orig_path: str | None = None


def parse_status_z(status_z: str) -> list[StatusEntry]:
    parts = status_z.split("\0")
    entries: list[StatusEntry] = []
    index = 0
    while index < len(parts):
        raw = parts[index]
        index += 1
        if not raw or len(raw) < 3:
            continue
        code = raw[:2]
        rest = raw[2:]
        if rest and rest[0] in (" ", "\t"):
            rest = rest[1:]
        path = rest
        orig_path: str | None = None
        if "R" in code and index < len(parts):
            orig_path = parts[index]
            index += 1
        entries.append(StatusEntry(code=code, path=path, orig_path=orig_path))
    return entries


def git_status_entries(project_root: Path, *, untracked_all: bool = False, pathspec: str | None = None) -> list[StatusEntry]:
    cmd = ["git", "status", "--porcelain=1", "-z"]
    if untracked_all:
        cmd.append("--untracked-files=all")
    if pathspec:
        cmd.extend(["--", pathspec])
    return parse_status_z(out(cmd, cwd=project_root))


def collect_status_entries(project_root: Path) -> list[StatusEntry]:
    expanded: list[StatusEntry] = []
    seen: set[tuple[str, str, str | None]] = set()
    for entry in git_status_entries(project_root):
        full_path = project_root / entry.path
        if entry.code == "??" and full_path.is_dir() and not full_path.is_symlink():
            nested_entries = git_status_entries(project_root, untracked_all=True, pathspec=entry.path)
            if nested_entries:
                for nested_entry in nested_entries:
                    key = (nested_entry.code, nested_entry.path, nested_entry.orig_path)
                    if key not in seen:
                        seen.add(key)
                        expanded.append(nested_entry)
                continue
        key = (entry.code, entry.path, entry.orig_path)
        if key not in seen:
            seen.add(key)
            expanded.append(entry)
    return expanded


def file_fingerprint(project_root: Path, path: str) -> str:
    full_path = project_root / path
    if not full_path.exists():
        return "missing"
    if full_path.is_dir():
        return "dir"
    try:
        blob = out(["git", "hash-object", "--", path], cwd=project_root)
    except Exception:
        digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
        return f"sha256:{digest}"
    return f"git:{blob}"


def path_exists_at_revision(project_root: Path, revision: str, path: str) -> bool:
    return git_ok(["git", "cat-file", "-e", f"{revision}:{path}"], cwd=project_root)


def entry_fingerprint(project_root: Path, entry: StatusEntry) -> dict[str, str]:
    data = {"code": entry.code, "path": entry.path, "path_fingerprint": file_fingerprint(project_root, entry.path)}
    if entry.orig_path:
        data["orig_path"] = entry.orig_path
        data["orig_path_fingerprint"] = file_fingerprint(project_root, entry.orig_path)
    return data


def chunked(seq: list[str], size: int = 50) -> list[list[str]]:
    return [seq[index : index + size] for index in range(0, len(seq), size)]


def has_ref(ref: str) -> bool:
    return git_ok(["git", "show-ref", "--verify", ref])


def ref_commit(ref: str) -> str | None:
    if not git_ok(["git", "rev-parse", "--verify", ref]):
        return None
    return out(["git", "rev-parse", ref])


def branch_exists(branch: str, remote: str) -> tuple[str, str | None]:
    local_sha = ref_commit(f"refs/heads/{branch}")
    if local_sha:
        return ("local", local_sha)
    remote_sha = ref_commit(f"refs/remotes/{remote}/{branch}")
    if remote_sha:
        return ("remote", remote_sha)
    return ("missing", None)


def is_detached_head(project_root: Path) -> bool:
    return out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root) == "HEAD"


def require_attached_head(project_root: Path, protocol: str) -> None:
    if is_detached_head(project_root):
        raise RuntimeError(f"{protocol} requires HEAD to be attached to a branch.")


def require_no_conflicts(project_root: Path, protocol: str) -> None:
    entries = git_status_entries(project_root)
    if any(entry.code in CONFLICT_CODES for entry in entries):
        raise RuntimeError(f"{protocol} requires all merge conflicts to be resolved first.")


def require_no_tracked_unstaged(project_root: Path, protocol: str) -> None:
    if not git_ok(["git", "diff", "--quiet"], cwd=project_root):
        raise RuntimeError(f"{protocol} requires no tracked unstaged changes.")


def tracked_path_exists(project_root: Path, rel_path: str) -> bool:
    return git_ok(["git", "ls-files", "--error-unmatch", "--", rel_path], cwd=project_root)


def reset_index_paths(project_root: Path, paths: list[str]) -> None:
    unique_paths = sorted(set(paths))
    for group in chunked(unique_paths):
        run(["git", "reset", "--quiet", "HEAD", "--"] + group, cwd=project_root)


def soft_reset_head(project_root: Path, target: str) -> None:
    run(["git", "reset", "--quiet", "--soft", target], cwd=project_root, capture_output=False)


def current_branch(project_root: Path | None = None) -> str:
    return out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)


def ensure_branch_from_base(branch: str, base_ref: str, remote: str, base_sha: str) -> None:
    location, sha = branch_exists(branch, remote)
    current = current_branch()
    if current == branch:
        current_sha = out(["git", "rev-parse", "HEAD"])
        if current_sha != base_sha:
            raise RuntimeError(
                f"Target branch '{branch}' is currently checked out at {current_sha[:12]}, expected base {base_sha[:12]}; rerun prepare."
            )
        return
    if location != "missing" and sha != base_sha:
        raise RuntimeError(
            f"Target branch '{branch}' already exists at {sha[:12]}, expected base {base_sha[:12]}; rerun prepare."
        )
    if location == "local":
        run(["git", "checkout", "--quiet", branch], capture_output=False)
        return
    if location == "remote":
        run(["git", "checkout", "--quiet", "-B", branch, f"{remote}/{branch}"], capture_output=False)
        return
    run(["git", "checkout", "--quiet", "-b", branch, base_ref], capture_output=False)


def stage_explicit(entries: list[StatusEntry]) -> None:
    tracked_paths: list[str] = []
    untracked_paths: list[str] = []
    for entry in entries:
        if entry.code == "??":
            untracked_paths.append(entry.path)
        else:
            tracked_paths.append(entry.path)
    for group in chunked(tracked_paths):
        run(["git", "add", "-u", "--"] + group)
    for group in chunked(untracked_paths):
        run(["git", "add", "--"] + group)


def staged_is_empty() -> bool:
    return subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0


def collect_log_context(project_root: Path) -> str:
    helper = SCRIPT_DIR / "log_since_last_push.py"
    log_path = resolve_project_log_path(project_root)
    if helper.exists():
        proc = run(["python3", str(helper), "--log", str(log_path), "--max", "80"], check=False)
        return (proc.stdout or "").strip() or "(no log lines)"
    return "(helper missing)"


def commit_range_classifier_snapshot(project_root: Path, boundary_sha: str, changed_paths: list[str]) -> tuple[list[dict], list[dict]]:
    synthetic_entries: list[StatusEntry] = []
    for path in changed_paths:
        code = "M " if path_exists_at_revision(project_root, boundary_sha, path) else "??"
        synthetic_entries.append(StatusEntry(code=code, path=path))
    return classify_entries(project_root, synthetic_entries)


def build_pr_body(plan: dict, log_context: str) -> str:
    included = plan["included_paths"] or ["(none)"]
    excluded_items = plan["excluded_items"] or []
    lines = [
        "Summary",
        f"- mode: {plan['mode']}",
        f"- base: {plan['base']}",
        f"- branch: {plan['branch']}",
        "",
        "Included files",
        *[f"- {path}" for path in included],
        "",
        "Excluded files",
    ]
    if excluded_items:
        lines.extend(f"- {item['path']} ({item['reason']})" for item in excluded_items)
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "Log context since last successful git-publish",
            log_context,
            "",
            "Merge note",
            "- Merge with standard GitHub 'Merge pull request'.",
            "- Rollback after merge: use `git revert -m 1 <merge_commit_sha>` for a merge commit or `git revert <commit_sha>` for a direct single-commit landing.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def gh_pr_create(base: str, head: str, title: str, body_file: Path) -> str | None:
    helper = SCRIPT_DIR / "create_pr_gh.sh"
    if not helper.exists():
        return None
    proc = run([str(helper), base, head, title, str(body_file)], check=False)
    if proc.returncode != 0:
        return None
    url = (proc.stdout or "").strip()
    if not url or url in {"[]", "null"} or url.startswith("[skip]"):
        return None
    return url


def api_pr_create(base: str, head: str, title: str, body: str) -> str | None:
    helper = SCRIPT_DIR / "create_pr.py"
    if not helper.exists():
        return None
    proc = run(
        ["python3", str(helper), "--base", base, "--head", head, "--title", title, "--body", body],
        check=False,
    )
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def parse_github_owner_repo(remote_url: str) -> tuple[str, str] | None:
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", remote_url.strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")


def manual_pr_url(remote: str, base: str, head: str) -> str | None:
    try:
        remote_url = out(["git", "remote", "get-url", remote])
    except Exception:
        return None
    owner_repo = parse_github_owner_repo(remote_url)
    if not owner_repo:
        return None
    owner, repo = owner_repo
    return f"https://github.com/{owner}/{repo}/compare/{base}...{head}?expand=1"


def github_token_from_keychain(service: str, account: str) -> str:
    try:
        value = subprocess.check_output(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("macOS 'security' tool not found; cannot read Keychain token.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Keychain item not found for service={service!r} account={account!r}."
        ) from exc
    return value.strip()


def github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    account = os.environ.get("CODEX_GITHUB_TOKEN_KEYCHAIN_ACCOUNT", os.environ.get("USER", "")).strip()
    service = os.environ.get("CODEX_GITHUB_TOKEN_KEYCHAIN_SERVICE", "codex_github_token").strip()
    if not account:
        raise RuntimeError("Missing GitHub token: set GITHUB_TOKEN or configure a keychain account.")
    return github_token_from_keychain(service, account)


def github_api_request(url: str, *, token: str) -> list[dict]:
    request = urllib.request.Request(url, method="GET")
    request.add_header("Accept", "application/vnd.github+json")
    if token.startswith(("ghp_", "github_pat_")):
        request.add_header("Authorization", f"Bearer {token}")
    else:
        request.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected GitHub API response when resolving pull requests.")
    return payload


def stage_log_marker(project_root: Path, marker: str) -> str:
    log_path = resolve_project_log_path(project_root)
    append_project_log(log_path, marker)
    rel_log = os.path.relpath(log_path, project_root)
    run(["git", "add", "--", rel_log])
    return rel_log


def repo_state_fingerprint(project_root: Path, entries: list[StatusEntry]) -> dict[str, dict[str, str]]:
    return {entry.path: entry_fingerprint(project_root, entry) for entry in entries}


def classifier_snapshot(project_root: Path) -> tuple[list[StatusEntry], list[dict], list[dict]]:
    entries = collect_status_entries(project_root)
    included, excluded = classify_entries(project_root, entries)
    return entries, included, excluded


def classify_entries(project_root: Path, entries: list[StatusEntry]) -> tuple[list[dict], list[dict]]:
    included: list[dict] = []
    excluded: list[dict] = []
    for entry in entries:
        item = {
            "path": entry.path,
            "code": entry.code,
            "orig_path": entry.orig_path,
            "fingerprint": entry_fingerprint(project_root, entry),
        }
        if is_junk_path(entry.path):
            item["reason"] = "excluded-junk"
            excluded.append(item)
            continue
        if entry.code == "??" and is_unclear_path(entry.path):
            item["reason"] = "excluded-unclear"
            excluded.append(item)
            continue
        if entry.code == "??":
            dir_reason = untracked_dir_reason(entry.path)
            if dir_reason:
                item["reason"] = dir_reason
                excluded.append(item)
                continue
        if entry.code == "??" and not is_safe_untracked_path(entry.path):
            item["reason"] = "excluded-untracked"
            excluded.append(item)
            continue
        included.append(item)
    return included, excluded


def derive_topic(project_root: Path, topic: str) -> str:
    raw = topic.strip() or project_root.name
    return re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-") or "update"


def compute_base_ref(remote: str, base: str) -> tuple[str, str]:
    remote_ref = f"refs/remotes/{remote}/{base}"
    remote_sha = ref_commit(remote_ref)
    if remote_sha:
        return (f"{remote}/{base}", remote_sha)
    local_ref = f"refs/heads/{base}"
    local_sha = ref_commit(local_ref)
    if local_sha:
        return (base, local_sha)
    raise RuntimeError(f"Base branch '{base}' is not available locally or as {remote}/{base}.")


def default_commit_message(topic: str) -> str:
    return f"chore: {topic}"


def default_pr_title(topic: str) -> str:
    return f"{topic}: publish"


def plan_payload(plan: dict) -> bytes:
    return json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")


def plan_token(plan: dict) -> str:
    return hashlib.sha256(plan_payload(plan)).hexdigest()[:16]


def save_plan(plan: dict) -> tuple[str, Path]:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    token = plan_token(plan)
    plan_path = PLAN_DIR / f"{token}.json"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return token, plan_path


def load_plan(plan_arg: str) -> dict:
    candidate = Path(plan_arg)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    digest_candidate = PLAN_DIR / f"{plan_arg}.json"
    if digest_candidate.exists():
        return json.loads(digest_candidate.read_text(encoding="utf-8"))
    padded = plan_arg + "=" * (-len(plan_arg) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise RuntimeError(f"Unable to read plan: {plan_arg}") from exc
    return json.loads(raw.decode("utf-8"))


def resolve_requested_repo_root(repo_arg: str) -> Path:
    if not repo_arg.strip():
        raise RuntimeError("Missing required flag: --repo <absolute-path>")
    repo_path = Path(repo_arg).expanduser()
    if not repo_path.is_absolute():
        raise RuntimeError("--repo must be an absolute path.")
    repo_path = repo_path.resolve()
    if not repo_path.exists():
        raise RuntimeError(f"--repo path does not exist: {repo_path}")
    try:
        project_root = git_repo_root(repo_path)
    except Exception as exc:
        raise RuntimeError(f"Not a git repo: {repo_path}") from exc
    if project_root == WORKSPACE_ROOT:
        raise RuntimeError(f"Workspace root '{WORKSPACE_ROOT}' must not be used as --repo.")
    return project_root


def validate_plan_request(plan: dict, requested_repo_root: Path, requested_mode: str) -> None:
    plan_repo_root = Path(plan["repo_root"]).resolve()
    if requested_repo_root != plan_repo_root:
        raise RuntimeError(
            f"Plan repo mismatch: requested {requested_repo_root}, plan targets {plan_repo_root}. Rerun prepare."
        )
    if requested_mode != plan["mode"]:
        raise RuntimeError(
            f"Plan mode mismatch: requested {requested_mode}, plan targets {plan['mode']}. Rerun prepare."
        )


def build_prepare_plan(
    *,
    project_root: Path,
    repo_arg: str,
    mode: str,
    topic: str,
    remote: str,
    base: str,
    commit_message: str,
    pr_title: str,
) -> dict:
    entries, included, excluded = classifier_snapshot(project_root)
    branch = base if mode == "no-pr" else f"codex/{topic}"
    base_ref, base_sha = compute_base_ref(remote, base)
    log_path = resolve_project_log_path(project_root)
    repo_display = repo_arg or str(project_root)
    plan = {
        "mode": mode,
        "repo": repo_display,
        "repo_root": str(project_root),
        "remote": remote,
        "base": base,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "branch": branch,
        "topic": topic,
        "commit_message": commit_message,
        "pr_title": pr_title,
        "log_path": os.path.relpath(log_path, project_root),
        "included_paths": [item["path"] for item in included],
        "excluded_paths": [item["path"] for item in excluded],
        "excluded_items": [{"path": item["path"], "reason": item["reason"], "code": item["code"]} for item in excluded],
        "log_context": collect_log_context(project_root),
        "entries": [asdict(entry) for entry in entries],
        "state": repo_state_fingerprint(project_root, entries),
        "head_sha": out(["git", "rev-parse", "HEAD"], cwd=project_root),
    }
    token, plan_path = save_plan(plan)
    plan["plan_id"] = token
    plan["plan_path"] = str(plan_path)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def split_z_paths(raw: str) -> list[str]:
    return [part for part in raw.split("\0") if part]


def local_publish_range(project_root: Path, remote: str, base: str) -> dict:
    branch = current_branch(project_root)
    default_branch = base.strip() or default_remote_branch(remote)
    if branch == default_branch:
        boundary_ref, boundary_sha = compute_base_ref(remote, default_branch)
        boundary_desc = boundary_ref
    else:
        upstream = upstream_tracking_ref(project_root)
        if upstream:
            boundary_ref = upstream
            boundary_sha = out(["git", "rev-parse", upstream], cwd=project_root)
            boundary_desc = upstream
        else:
            boundary_ref, _ = compute_base_ref(remote, default_branch)
            boundary_sha = out(["git", "merge-base", "HEAD", boundary_ref], cwd=project_root)
            boundary_desc = f"merge-base(HEAD, {boundary_ref})"
    rev_range = f"{boundary_sha}..HEAD"
    commits = [line for line in out(["git", "rev-list", "--reverse", rev_range], cwd=project_root).splitlines() if line.strip()]
    changed_paths = split_z_paths(
        out(["git", "diff", "--name-only", "--diff-filter=ACDMRTUXB", "-z", rev_range], cwd=project_root)
    )
    return {
        "source_branch": branch,
        "default_branch": default_branch,
        "boundary_ref": boundary_ref,
        "boundary_sha": boundary_sha,
        "boundary_desc": boundary_desc,
        "commits": commits,
        "changed_paths": changed_paths,
        "head_sha": out(["git", "rev-parse", "HEAD"], cwd=project_root),
    }


def build_commit_range_push_plan(
    *,
    project_root: Path,
    repo_arg: str,
    mode: str,
    topic: str,
    remote: str,
    base: str,
    commit_message: str,
    pr_title: str,
    publish_range: dict,
) -> dict:
    branch = base if mode == "no-pr" else f"codex/{topic}"
    base_ref, base_sha = compute_base_ref(remote, base)
    log_path = resolve_project_log_path(project_root)
    repo_display = repo_arg or str(project_root)
    included, excluded = commit_range_classifier_snapshot(
        project_root, publish_range["boundary_sha"], publish_range["changed_paths"]
    )
    return {
        "source_kind": "commit-range",
        "mode": mode,
        "repo": repo_display,
        "repo_root": str(project_root),
        "remote": remote,
        "base": base,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "branch": branch,
        "topic": topic,
        "commit_message": commit_message,
        "pr_title": pr_title,
        "log_path": os.path.relpath(log_path, project_root),
        "included_paths": [item["path"] for item in included],
        "excluded_paths": [item["path"] for item in excluded],
        "excluded_items": [{"path": item["path"], "reason": item["reason"], "code": item["code"]} for item in excluded],
        "log_context": collect_log_context(project_root),
        "head_sha": publish_range["head_sha"],
        "source_branch": publish_range["source_branch"],
        "source_boundary_sha": publish_range["boundary_sha"],
        "source_boundary_desc": publish_range["boundary_desc"],
        "source_commits": publish_range["commits"],
    }


def human_prepare_output(plan: dict) -> str:
    lines = [
        f"mode: {plan['mode']}",
        f"repo: {plan['repo_root']}",
        f"base: {plan['base']}",
        f"branch: {plan['branch']}",
        f"commit_message: {plan['commit_message']}",
        f"pr_title: {plan['pr_title']}",
        f"log_path: {plan['log_path']}",
        f"plan_path: {plan['plan_path']}",
        "included_files:",
    ]
    if plan["included_paths"]:
        lines.extend(f"  - {path}" for path in plan["included_paths"])
    else:
        lines.append("  - (none)")
    lines.append("excluded_files:")
    if plan["excluded_items"]:
        lines.extend(f"  - {item['path']} [{item['reason']}]" for item in plan["excluded_items"])
    else:
        lines.append("  - (none)")
    return "\n".join(lines)


def rollback_hint() -> str:
    return (
        "If GitHub merge creates a merge commit: git revert -m 1 <merge_commit_sha>; "
        "if GitHub lands a single commit directly: git revert <commit_sha>"
    )


def human_publish_output(result: dict) -> str:
    lines = [
        f"mode: {result['mode']}",
        f"repo: {result['repo_root']}",
        f"base: {result['base']}",
        f"branch: {result['branch']}",
        f"commit_sha: {result['commit_sha']}",
        f"log_path: {result['log_path']}",
        "included_files:",
    ]
    if result["included_paths"]:
        lines.extend(f"  - {path}" for path in result["included_paths"])
    else:
        lines.append("  - (none)")
    if result.get("pr_url") is not None:
        lines.append(f"pr_url: {result['pr_url']}")
    lines.append(f"rollback_hint: {result['rollback_hint']}")
    return "\n".join(lines)


def human_push_noop_output(result: dict) -> str:
    lines = [
        "action: push",
        f"status: {result['status']}",
        f"mode: {result['mode']}",
        f"repo: {result['repo_root']}",
        f"base: {result['base']}",
        f"branch: {result['branch']}",
        f"log_path: {result['log_path']}",
    ]
    append_path_block(lines, "included_files:", result["included_paths"])
    append_excluded_block(lines, result["excluded_items"])
    lines.append("note: no publishable local work was found.")
    return "\n".join(lines)


def require_clean_index(project_root: Path, protocol: str = "publish") -> None:
    if not git_ok(["git", "diff", "--cached", "--quiet"], cwd=project_root):
        raise RuntimeError(f"Staged changes already exist; {protocol} requires a clean index before mutation.")


def verify_publish_plan(project_root: Path, plan: dict) -> list[StatusEntry]:
    if str(project_root) != plan["repo_root"]:
        raise RuntimeError(f"Plan repo mismatch: expected {plan['repo_root']}, got {project_root}")
    current_head = out(["git", "rev-parse", "HEAD"], cwd=project_root)
    if current_head != plan["head_sha"]:
        raise RuntimeError("HEAD changed after prepare; rerun prepare.")
    _, current_base_sha = compute_base_ref(plan["remote"], plan["base"])
    if current_base_sha != plan["base_sha"]:
        raise RuntimeError(f"Base branch '{plan['base']}' moved after prepare; rerun prepare.")
    current_entries = collect_status_entries(project_root)
    current_state = repo_state_fingerprint(project_root, current_entries)
    if current_state != plan["state"]:
        raise RuntimeError("Repo changes drifted after prepare; rerun prepare.")
    return current_entries


def verify_commit_range_plan(project_root: Path, plan: dict) -> None:
    current_head = out(["git", "rev-parse", "HEAD"], cwd=project_root)
    if current_head != plan["head_sha"]:
        raise RuntimeError("HEAD changed after push preparation; rerun push.")
    _, current_base_sha = compute_base_ref(plan["remote"], plan["base"])
    if current_base_sha != plan["base_sha"]:
        raise RuntimeError(f"Base branch '{plan['base']}' moved after push preparation; rerun push.")
    if current_branch(project_root) != plan["source_branch"]:
        raise RuntimeError(
            f"push expected source branch '{plan['source_branch']}', but HEAD is on '{current_branch(project_root)}'."
        )
    if not plan.get("source_commits"):
        raise RuntimeError("No local unpublished commits remain to publish.")


def cherry_pick_no_commit(project_root: Path, commits: list[str]) -> None:
    proc = run(["git", "cherry-pick", "--no-commit"] + commits, cwd=project_root, check=False)
    if proc.returncode == 0:
        return
    run(["git", "cherry-pick", "--abort"], cwd=project_root, check=False, capture_output=False)
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    raise RuntimeError(stderr or stdout or "Failed to materialize local unpublished commits for push.")


def restore_paths_from_head(project_root: Path, paths: list[str]) -> None:
    unique_paths = sorted(set(paths))
    for group in chunked(unique_paths):
        run(["git", "restore", "--quiet", "--source=HEAD", "--staged", "--worktree", "--"] + group, cwd=project_root)


def realign_default_branch_after_commit_range_publish(project_root: Path, plan: dict) -> None:
    if plan["source_branch"] != plan["base"]:
        return
    if current_branch(project_root) == plan["base"]:
        raise RuntimeError("Internal error: default branch is still checked out during publish-branch realignment.")
    run(["git", "branch", "--quiet", "-f", plan["base"], plan["base_ref"]], cwd=project_root)


def append_path_block(lines: list[str], label: str, paths: list[str]) -> None:
    lines.append(label)
    if paths:
        lines.extend(f"  - {path}" for path in paths)
    else:
        lines.append("  - (none)")


def append_excluded_block(lines: list[str], excluded_items: list[dict]) -> None:
    lines.append("excluded_files:")
    if excluded_items:
        lines.extend(f"  - {item['path']} [{item['reason']}]" for item in excluded_items)
    else:
        lines.append("  - (none)")


def commit_preview_output(project_root: Path, branch: str, included_paths: list[str], excluded_items: list[dict]) -> str:
    lines = [
        "preview:",
        "  action: commit",
        f"  repo: {project_root}",
        f"  branch: {branch}",
        f"  commit_message: {CHECKPOINT_COMMIT_MESSAGE}",
        "  included_files:",
    ]
    if included_paths:
        lines.extend(f"    - {path}" for path in included_paths)
    else:
        lines.append("    - (none)")
    lines.append("  excluded_files:")
    if excluded_items:
        lines.extend(f"    - {item['path']} [{item['reason']}]" for item in excluded_items)
    else:
        lines.append("    - (none)")
    return "\n".join(lines)


def human_commit_output(result: dict) -> str:
    lines = [
        "action: commit",
        f"status: {result['status']}",
        f"repo: {result['repo_root']}",
        f"branch: {result['branch']}",
        f"commit_message: {result['commit_message']}",
    ]
    if result.get("commit_sha"):
        lines.append(f"commit_sha: {result['commit_sha']}")
    append_path_block(lines, "included_files:", result["included_paths"])
    append_excluded_block(lines, result["excluded_items"])
    return "\n".join(lines)


def load_commit_message(revision: str, project_root: Path) -> str:
    return out(["git", "log", "-1", "--format=%B", revision], cwd=project_root)


def normalize_rebase_message(message: str) -> str:
    lines = message.splitlines()
    subject = lines[0] if lines else ""
    for prefix in ("fixup! ", "squash! "):
        if subject.startswith(prefix):
            subject = subject[len(prefix) :]
            break
    if not subject.strip():
        subject = CHECKPOINT_COMMIT_MESSAGE
    body = "\n".join(lines[1:]).rstrip()
    if body:
        return f"{subject}\n\n{body}\n"
    return subject + "\n"


def git_commit_with_message(project_root: Path, message: str, *, amend: bool = False) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
        handle.write(message if message.endswith("\n") else message + "\n")
        message_path = Path(handle.name)
    try:
        cmd = ["git", "commit", "--quiet"]
        if amend:
            cmd.append("--amend")
        cmd.extend(["-F", str(message_path)])
        run(cmd, cwd=project_root, capture_output=False)
    finally:
        try:
            message_path.unlink()
        except OSError:
            pass


def upstream_tracking_ref(project_root: Path) -> str | None:
    proc = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=project_root,
        check=False,
    )
    value = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return None
    return value or None


def local_rewrite_plan(project_root: Path, remote: str, base_arg: str) -> dict:
    default_branch = base_arg.strip() or default_remote_branch(remote)
    branch = current_branch(project_root)
    if branch == default_branch:
        raise RuntimeError(f"rebase refuses to rewrite the default branch '{default_branch}'.")
    upstream = upstream_tracking_ref(project_root)
    if upstream:
        boundary = upstream
        boundary_sha = out(["git", "rev-parse", upstream], cwd=project_root)
        boundary_desc = upstream
    else:
        base_ref, _ = compute_base_ref(remote, default_branch)
        boundary_sha = out(["git", "merge-base", "HEAD", base_ref], cwd=project_root)
        boundary_desc = f"merge-base(HEAD, {base_ref})"
    revision_range = f"{boundary_sha}..HEAD"
    proc = run(["git", "rev-list", "--reverse", revision_range], cwd=project_root, check=False)
    commits = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    return {
        "branch": branch,
        "default_branch": default_branch,
        "boundary_sha": boundary_sha,
        "boundary_desc": boundary_desc,
        "rewrite_commits": commits,
    }


def human_rebase_output(result: dict) -> str:
    lines = [
        "action: rebase",
        f"status: {result['status']}",
        f"repo: {result['repo_root']}",
        f"branch: {result['branch']}",
        f"default_branch: {result['default_branch']}",
        f"boundary: {result['boundary']}",
        f"rewrite_strategy: {result['rewrite_strategy']}",
        f"rewrite_count: {result['rewrite_count']}",
        f"commit_message: {result['commit_message']}",
    ]
    if result.get("old_head"):
        lines.append(f"old_head: {result['old_head']}")
    if result.get("new_head"):
        lines.append(f"new_head: {result['new_head']}")
    return "\n".join(lines)


def latest_publish_anchor(project_root: Path) -> dict:
    log_path = resolve_project_log_path(project_root)
    if not log_path.exists():
        raise RuntimeError("No project log found; merge-done cannot resolve the last publish marker.")
    rel_log = os.path.relpath(log_path, project_root)
    for raw_line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        line = raw_line.strip()
        match = PUSH_SUCCESS_RE.match(line)
        if match:
            return {
                "mode": match.group("mode"),
                "branch": match.group("branch"),
                "base": match.group("base"),
                "log_path": log_path,
                "log_rel_path": rel_log,
                "line": line,
            }
    raise RuntimeError("No successful git-publish push marker found in the active project log.")


def gh_lookup_pull_requests(owner: str, repo: str, head: str, base: str) -> list[dict] | None:
    try:
        auth = run(["gh", "auth", "status", "-h", "github.com"], check=False)
    except FileNotFoundError:
        return None
    if auth.returncode != 0:
        return None
    query = urllib.parse.urlencode({"state": "all", "head": f"{owner}:{head}", "base": base})
    proc = run(["gh", "api", f"repos/{owner}/{repo}/pulls?{query}"], check=False)
    if proc.returncode != 0:
        return None
    payload = json.loads(proc.stdout or "[]")
    if not isinstance(payload, list):
        return None
    return payload


def api_lookup_pull_requests(owner: str, repo: str, head: str, base: str) -> list[dict]:
    query = urllib.parse.urlencode({"state": "all", "head": f"{owner}:{head}", "base": base})
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?{query}"
    return github_api_request(url, token=github_token())


def matching_pull_requests(project_root: Path, remote: str, head: str, base: str) -> tuple[str, str, list[dict]]:
    remote_url = out(["git", "remote", "get-url", remote], cwd=project_root)
    owner_repo = parse_github_owner_repo(remote_url)
    if not owner_repo:
        raise RuntimeError(f"Remote '{remote}' is not a supported GitHub remote; merge-done cannot verify PR merge state.")
    owner, repo = owner_repo
    payload = gh_lookup_pull_requests(owner, repo, head, base)
    if payload is None:
        payload = api_lookup_pull_requests(owner, repo, head, base)
    matches = []
    for item in payload:
        matches.append(
            {
                "number": item.get("number"),
                "url": item.get("html_url"),
                "merged": bool(item.get("merged_at")),
                "merged_at": item.get("merged_at"),
                "head": item.get("head", {}).get("ref"),
                "head_sha": item.get("head", {}).get("sha"),
                "base": item.get("base", {}).get("ref"),
            }
        )
    return owner, repo, matches


def marker_commit_sha(project_root: Path, log_rel_path: str, marker_line: str) -> str:
    proc = run(
        ["git", "log", "--all", "--format=%H", "-F", "-S", marker_line, "--", log_rel_path],
        cwd=project_root,
        check=False,
    )
    commits = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not commits:
        raise RuntimeError("Could not resolve the publish commit that introduced the latest success marker.")
    if len(commits) > 1:
        raise RuntimeError("Latest success marker maps to multiple commits; merge-done anchor is ambiguous.")
    return commits[0]


def verify_merged_pull_request(project_root: Path, remote: str, head: str, base: str, expected_head_sha: str) -> dict:
    _, _, matches = matching_pull_requests(project_root, remote, head, base)
    if not matches:
        raise RuntimeError(f"No GitHub pull request matches head '{head}' and base '{base}'.")
    matches = [match for match in matches if (match.get("head_sha") or "") == expected_head_sha]
    if not matches:
        raise RuntimeError(
            f"No GitHub pull request for head '{head}' and base '{base}' matches publish commit {expected_head_sha[:12]}."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple GitHub pull requests match head '{head}', base '{base}', and publish commit {expected_head_sha[:12]}."
        )
    match = matches[0]
    if not match["merged"]:
        target = match["url"] or f"#{match['number']}"
        raise RuntimeError(f"Pull request {target} for head '{head}' and base '{base}' is not merged.")
    return match


def run_hygiene(project_root: Path, remote: str) -> None:
    helper = SCRIPT_DIR / "git_hygiene.sh"
    if not helper.exists():
        raise RuntimeError("git_hygiene.sh is missing; merge-done cannot run hygiene.")
    proc = run([str(helper), "--repo", str(project_root), "--remote", remote, "--apply"], cwd=project_root, check=False)
    if proc.returncode == 0:
        return
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    raise RuntimeError(stderr or stdout or "git_hygiene.sh failed during merge-done.")


def ensure_default_branch_state(project_root: Path, remote: str, default_branch: str) -> None:
    branch = current_branch(project_root)
    if branch != default_branch:
        run(["git", "checkout", "--quiet", default_branch], cwd=project_root, capture_output=False)
    remote_ref = f"refs/remotes/{remote}/{default_branch}"
    remote_sha = ref_commit(remote_ref)
    if not remote_sha:
        raise RuntimeError(f"Remote default branch '{remote}/{default_branch}' is not available after hygiene.")
    local_ref = f"refs/heads/{default_branch}"
    local_sha = ref_commit(local_ref)
    if local_sha != remote_sha:
        run(["git", "merge", "--ff-only", f"{remote}/{default_branch}"], cwd=project_root, capture_output=False)
        local_sha = ref_commit(local_ref)
    if local_sha != remote_sha:
        raise RuntimeError(f"Local '{default_branch}' does not match '{remote}/{default_branch}' after hygiene.")


def delete_local_branch(project_root: Path, branch: str) -> None:
    if current_branch(project_root) == branch:
        raise RuntimeError(f"Cannot delete current branch '{branch}'.")
    if ref_commit(f"refs/heads/{branch}"):
        run(["git", "branch", "--quiet", "-D", branch], cwd=project_root)


def remote_branch_state(project_root: Path, remote: str, branch: str) -> str:
    proc = run(["git", "ls-remote", "--heads", remote, branch], cwd=project_root, check=False)
    if proc.returncode != 0:
        return "unknown"
    return "present" if (proc.stdout or "").strip() else "gone"


def remote_branch_status_after_cleanup(project_root: Path, remote: str, branch: str) -> str:
    state = remote_branch_state(project_root, remote, branch)
    if state != "present":
        return state
    proc = run(["git", "push", "--quiet", remote, "--delete", branch], cwd=project_root, check=False)
    if proc.returncode != 0:
        refreshed = remote_branch_state(project_root, remote, branch)
        return refreshed if refreshed in {"gone", "present"} else "unknown"
    return remote_branch_state(project_root, remote, branch)


def human_merge_done_output(result: dict) -> str:
    lines = [
        "action: merge-done",
        f"status: {result['status']}",
        f"repo: {result['repo_root']}",
        f"default_branch: {result['default_branch']}",
        f"anchor_branch: {result['anchor_branch']}",
        f"anchor_base: {result['anchor_base']}",
        f"anchor_log_path: {result['log_path']}",
        f"hygiene: {result['hygiene']}",
        f"remote_branch: {result['remote_branch']}",
        f"tracked_delta: {result['tracked_delta']}",
    ]
    if result.get("pr_url"):
        lines.append(f"pr_url: {result['pr_url']}")
    lines.append("note: merge-confirmed log line appended and intentionally left as a tracked worktree delta.")
    return "\n".join(lines)


def publish(plan: dict, json_output: bool) -> int:
    project_root = Path(plan["repo_root"])
    os.chdir(project_root)

    require_no_conflicts(project_root, "publish")
    require_clean_index(project_root, "publish")
    source_kind = plan.get("source_kind", "worktree")
    if source_kind == "commit-range":
        verify_commit_range_plan(project_root, plan)
        if plan["mode"] == "no-pr":
            raise RuntimeError("push no-pr does not support publish-from-local-commits on a clean worktree; rerun with PR mode.")
        if not plan.get("source_commits"):
            raise RuntimeError("Prepared push contains no local unpublished commits; nothing to publish.")
        ensure_branch_from_base(plan["branch"], plan["base_ref"], plan["remote"], plan["base_sha"])
        cherry_pick_no_commit(project_root, plan["source_commits"])
        restore_paths_from_head(project_root, plan.get("excluded_paths", []))
        if staged_is_empty():
            raise RuntimeError("Nothing staged after materializing local unpublished commits.")
        log_rel_path = stage_log_marker(
            project_root,
            f"{now_ts()} | git-publish skill | push mode={plan['mode']} branch={plan['branch']} base={plan['base']} | success",
        )
        run(["git", "commit", "--quiet", "-m", plan["commit_message"]], capture_output=False)
        commit_sha = out(["git", "rev-parse", "HEAD"], cwd=project_root)
        run(["git", "push", "--quiet", "-u", plan["remote"], plan["branch"]], capture_output=False)
        realign_default_branch_after_commit_range_publish(project_root, plan)
    else:
        current_entries = verify_publish_plan(project_root, plan)
        included_entries = [entry for entry in current_entries if entry.path in set(plan["included_paths"])]
        if not included_entries:
            raise RuntimeError("Prepared plan contains no includable paths; nothing to publish.")

        if plan["mode"] == "pr":
            ensure_branch_from_base(plan["branch"], plan["base_ref"], plan["remote"], plan["base_sha"])
        else:
            branch = current_branch(project_root)
            if branch != plan["base"]:
                raise RuntimeError(f"Expected to publish from base branch '{plan['base']}', but HEAD is '{branch}'.")

        stage_explicit(included_entries)
        if staged_is_empty():
            raise RuntimeError("Nothing staged after applying the prepared include set.")

        marker = (
            f"{now_ts()} | git-publish skill | push mode={plan['mode']} "
            f"branch={plan['branch']} base={plan['base']} | success"
        )
        log_rel_path = stage_log_marker(project_root, marker)
        run(["git", "commit", "--quiet", "-m", plan["commit_message"]], capture_output=False)
        commit_sha = out(["git", "rev-parse", "HEAD"], cwd=project_root)

        if plan["mode"] == "pr":
            run(["git", "push", "--quiet", "-u", plan["remote"], plan["branch"]], capture_output=False)
        else:
            run(["git", "push", "--quiet", plan["remote"], plan["base"]], capture_output=False)

    pr_url: str | None = None
    if plan["mode"] == "pr":
        body = build_pr_body(plan, plan.get("log_context", "(no log lines)"))
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(body)
            body_path = Path(handle.name)
        try:
            pr_url = gh_pr_create(plan["base"], plan["branch"], plan["pr_title"], body_path)
            if not pr_url:
                pr_url = api_pr_create(plan["base"], plan["branch"], plan["pr_title"], body)
        finally:
            try:
                body_path.unlink()
            except OSError:
                pass
        if not pr_url:
            pr_url = manual_pr_url(plan["remote"], plan["base"], plan["branch"])

    result = {
        "mode": plan["mode"],
        "repo": plan["repo"],
        "repo_root": plan["repo_root"],
        "base": plan["base"],
        "branch": plan["branch"],
        "commit_sha": commit_sha,
        "pr_url": pr_url,
        "included_paths": plan["included_paths"],
        "log_path": log_rel_path,
        "rollback_hint": rollback_hint(),
    }
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(human_publish_output(result))
    return 0


def push_action(args: argparse.Namespace, json_output: bool) -> int:
    project_root = resolve_requested_repo_root(args.repo)
    os.chdir(project_root)
    require_no_conflicts(project_root, "push")

    remote = args.remote
    base = args.base.strip() or default_remote_branch(remote)
    topic = derive_topic(project_root, args.topic)
    worktree_plan = build_prepare_plan(
        project_root=project_root,
        repo_arg=args.repo.strip(),
        mode=args.mode,
        topic=topic,
        remote=remote,
        base=base,
        commit_message=args.message.strip() or default_commit_message(topic),
        pr_title=args.pr_title.strip() or default_pr_title(topic),
    )
    plan = worktree_plan
    if not plan["included_paths"]:
        publish_range = local_publish_range(project_root, remote, base)
        if publish_range["commits"]:
            plan = build_commit_range_push_plan(
                project_root=project_root,
                repo_arg=args.repo.strip(),
                mode=args.mode,
                topic=topic,
                remote=remote,
                base=base,
                commit_message=args.message.strip() or default_commit_message(topic),
                pr_title=args.pr_title.strip() or default_pr_title(topic),
                publish_range=publish_range,
            )
    if not plan["included_paths"]:
        result = {
            "action": "push",
            "status": "no-op",
            "mode": worktree_plan["mode"],
            "repo_root": worktree_plan["repo_root"],
            "base": worktree_plan["base"],
            "branch": worktree_plan["branch"],
            "log_path": worktree_plan["log_path"],
            "included_paths": worktree_plan["included_paths"],
            "excluded_items": worktree_plan["excluded_items"],
            "rollback_hint": rollback_hint(),
        }
        if json_output:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(human_push_noop_output(result))
        return 0
    return publish(plan, json_output)


def commit_checkpoint(args: argparse.Namespace, json_output: bool) -> int:
    project_root = resolve_requested_repo_root(args.repo)
    os.chdir(project_root)
    require_attached_head(project_root, "commit")
    require_no_conflicts(project_root, "commit")
    require_clean_index(project_root, "commit")

    entries, included, excluded = classifier_snapshot(project_root)
    branch = current_branch(project_root)
    included_paths = [item["path"] for item in included]
    preview = commit_preview_output(project_root, branch, included_paths, excluded)
    print(preview, file=sys.stderr if json_output else sys.stdout, flush=True)

    result = {
        "action": "commit",
        "status": "no-op" if not included_paths else "success",
        "repo_root": str(project_root),
        "branch": branch,
        "commit_message": CHECKPOINT_COMMIT_MESSAGE,
        "commit_sha": None,
        "included_paths": included_paths,
        "excluded_items": [{"path": item["path"], "reason": item["reason"], "code": item["code"]} for item in excluded],
    }
    if not included_paths:
        if json_output:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(human_commit_output(result))
        return 0

    included_set = set(included_paths)
    included_entries = [entry for entry in entries if entry.path in included_set]
    staged = False
    committed = False
    try:
        stage_explicit(included_entries)
        staged = True
        if staged_is_empty():
            raise RuntimeError("commit staged nothing after applying the classifier include set.")
        run(["git", "commit", "--quiet", "-m", CHECKPOINT_COMMIT_MESSAGE], cwd=project_root, capture_output=False)
        committed = True
    except Exception:
        if staged and not committed:
            reset_index_paths(project_root, included_paths)
        raise

    result["commit_sha"] = out(["git", "rev-parse", "HEAD"], cwd=project_root)
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(human_commit_output(result))
    return 0


def rebase_local_history(args: argparse.Namespace, json_output: bool) -> int:
    project_root = resolve_requested_repo_root(args.repo)
    os.chdir(project_root)
    require_attached_head(project_root, "rebase")
    require_no_conflicts(project_root, "rebase")
    require_clean_index(project_root, "rebase")
    require_no_tracked_unstaged(project_root, "rebase")

    rewrite = local_rewrite_plan(project_root, args.remote, args.base)
    commits = rewrite["rewrite_commits"]
    newest_message = normalize_rebase_message(load_commit_message(commits[-1], project_root)) if commits else ""
    strategy = "reword" if len(commits) == 1 else "squash"
    result = {
        "action": "rebase",
        "status": "no-op" if not commits else "success",
        "repo_root": str(project_root),
        "branch": rewrite["branch"],
        "default_branch": rewrite["default_branch"],
        "boundary": rewrite["boundary_desc"],
        "rewrite_strategy": strategy,
        "rewrite_count": len(commits),
        "commit_message": newest_message.rstrip("\n"),
        "old_head": None,
        "new_head": None,
    }
    if not commits:
        if json_output:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(human_rebase_output(result))
        return 0

    old_head = out(["git", "rev-parse", "HEAD"], cwd=project_root)
    result["old_head"] = old_head
    try:
        if len(commits) == 1:
            git_commit_with_message(project_root, newest_message, amend=True)
        else:
            soft_reset_head(project_root, rewrite["boundary_sha"])
            git_commit_with_message(project_root, newest_message)
    except Exception as exc:
        soft_reset_head(project_root, old_head)
        raise RuntimeError(f"rebase failed and restored original HEAD {old_head[:12]}: {exc}") from exc

    result["new_head"] = out(["git", "rev-parse", "HEAD"], cwd=project_root)
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(human_rebase_output(result))
    return 0


def merge_done(args: argparse.Namespace, json_output: bool) -> int:
    project_root = resolve_requested_repo_root(args.repo)
    os.chdir(project_root)
    default_branch = args.base.strip() or default_remote_branch(args.remote)
    anchor = latest_publish_anchor(project_root)
    if anchor["mode"] != "pr":
        raise RuntimeError("merge-done applies only after a PR-mode push; the most recent successful push was mode=no-pr.")

    require_attached_head(project_root, "merge-done")
    branch_before = current_branch(project_root)
    if branch_before not in {default_branch, anchor["branch"]}:
        raise RuntimeError(
            f"merge-done is ambiguous on branch '{branch_before}'; expected '{anchor['branch']}' or '{default_branch}'."
        )

    anchor_commit = marker_commit_sha(project_root, anchor["log_rel_path"], anchor["line"])
    pr = verify_merged_pull_request(project_root, args.remote, anchor["branch"], anchor["base"], anchor_commit)

    require_no_conflicts(project_root, "merge-done")
    require_clean_index(project_root, "merge-done")
    require_no_tracked_unstaged(project_root, "merge-done")

    run_hygiene(project_root, args.remote)
    ensure_default_branch_state(project_root, args.remote, default_branch)
    if anchor["branch"] != default_branch:
        delete_local_branch(project_root, anchor["branch"])
    if ref_commit(f"refs/heads/{anchor['branch']}"):
        raise RuntimeError(f"Local branch '{anchor['branch']}' still exists after hygiene.")
    remote_status = remote_branch_status_after_cleanup(project_root, args.remote, anchor["branch"])

    if not tracked_path_exists(project_root, anchor["log_rel_path"]):
        raise RuntimeError("Active project log must already be tracked before merge-done can append merge confirmation.")
    marker = (
        f"{now_ts()} | git-publish skill | merge-confirmed branch={anchor['branch']} base={anchor['base']} | "
        f"user confirmed merged; hygiene=applied; remote_branch={remote_status}"
    )
    append_project_log(anchor["log_path"], marker)

    tracked_dirty = sorted(
        {entry.path for entry in git_status_entries(project_root) if entry.code not in {"??", "!!"}}
    )
    if tracked_dirty != [anchor["log_rel_path"]]:
        raise RuntimeError(
            "merge-done expected the remaining tracked delta to be exactly the active project log after append."
        )

    result = {
        "action": "merge-done",
        "status": "success",
        "repo_root": str(project_root),
        "default_branch": default_branch,
        "anchor_branch": anchor["branch"],
        "anchor_base": anchor["base"],
        "log_path": anchor["log_rel_path"],
        "hygiene": "applied",
        "remote_branch": remote_status,
        "tracked_delta": anchor["log_rel_path"],
        "pr_url": pr.get("url"),
    }
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(human_merge_done_output(result))
    return 0


def prepare(args: argparse.Namespace, json_output: bool) -> int:
    try:
        project_root = resolve_requested_repo_root(args.repo)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    os.chdir(project_root)
    remote = args.remote
    base = args.base.strip() or default_remote_branch(remote)
    topic = derive_topic(project_root, args.topic)
    plan = build_prepare_plan(
        project_root=project_root,
        repo_arg=args.repo.strip(),
        mode=args.mode,
        topic=topic,
        remote=remote,
        base=base,
        commit_message=args.message.strip() or default_commit_message(topic),
        pr_title=args.pr_title.strip() or default_pr_title(topic),
    )
    if json_output:
        payload = {key: value for key, value in plan.items() if key not in {"entries", "state", "head_sha", "repo_root"}}
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(human_prepare_output(plan))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="git-publish",
        description="Deterministic git publish with explicit prepare/publish and local commit/rebase/merge-done protocols.",
    )
    parser.add_argument("--action", choices=["prepare", "publish", "push", "commit", "rebase", "merge-done"], required=True)
    parser.add_argument("--mode", choices=["pr", "no-pr"], default="pr")
    parser.add_argument("--topic", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base", default="")
    parser.add_argument("--message", default="")
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.action == "prepare":
            return prepare(args, args.json)
        if args.action == "commit":
            return commit_checkpoint(args, args.json)
        if args.action == "rebase":
            return rebase_local_history(args, args.json)
        if args.action == "merge-done":
            return merge_done(args, args.json)
        if args.action == "push":
            return push_action(args, args.json)
        if not args.plan:
            print("Missing required flag: --plan <file-or-token>", file=sys.stderr)
            return 2
        requested_repo_root = resolve_requested_repo_root(args.repo)
        plan = load_plan(args.plan)
        validate_plan_request(plan, requested_repo_root, args.mode)
        return publish(plan, args.json)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        print(stderr or f"Command failed: {' '.join(shlex.quote(part) for part in exc.cmd)}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
