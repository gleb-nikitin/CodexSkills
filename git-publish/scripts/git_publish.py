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


JUNK_BASENAMES = {".DS_Store"}
SAFE_UNTRACKED_BASENAMES = {"AGENTS.md", "README.md", "SKILL.md"}
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
PLAN_DIR = Path(tempfile.gettempdir()) / "git-publish-plans"
SCRIPT_DIR = Path(__file__).resolve().parent


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


def current_branch() -> str:
    return out(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def ensure_branch_from_base(branch: str, base_ref: str, remote: str, base_sha: str) -> None:
    location, sha = branch_exists(branch, remote)
    if location != "missing" and sha != base_sha:
        raise RuntimeError(
            f"Target branch '{branch}' already exists at {sha[:12]}, expected base {base_sha[:12]}; rerun prepare."
        )
    if current_branch() == branch:
        return
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


def stage_log_marker(project_root: Path, marker: str) -> str:
    log_path = resolve_project_log_path(project_root)
    append_project_log(log_path, marker)
    rel_log = os.path.relpath(log_path, project_root)
    run(["git", "add", "--", rel_log])
    return rel_log


def repo_state_fingerprint(project_root: Path, entries: list[StatusEntry]) -> dict[str, dict[str, str]]:
    return {entry.path: entry_fingerprint(project_root, entry) for entry in entries}


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
    repo_path = Path(repo_arg).expanduser().resolve()
    if not repo_path.exists():
        raise RuntimeError(f"--repo path does not exist: {repo_path}")
    try:
        return git_repo_root(repo_path)
    except Exception as exc:
        raise RuntimeError(f"Not a git repo: {repo_path}") from exc


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
    entries = parse_status_z(out(["git", "status", "--porcelain=1", "-z"], cwd=project_root))
    included, excluded = classify_entries(project_root, entries)
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


def require_clean_index(project_root: Path) -> None:
    if not git_ok(["git", "diff", "--cached", "--quiet"], cwd=project_root):
        raise RuntimeError("Staged changes already exist; publish requires a clean index before applying the prepared plan.")


def verify_publish_plan(project_root: Path, plan: dict) -> list[StatusEntry]:
    if str(project_root) != plan["repo_root"]:
        raise RuntimeError(f"Plan repo mismatch: expected {plan['repo_root']}, got {project_root}")
    current_head = out(["git", "rev-parse", "HEAD"], cwd=project_root)
    if current_head != plan["head_sha"]:
        raise RuntimeError("HEAD changed after prepare; rerun prepare.")
    _, current_base_sha = compute_base_ref(plan["remote"], plan["base"])
    if current_base_sha != plan["base_sha"]:
        raise RuntimeError(f"Base branch '{plan['base']}' moved after prepare; rerun prepare.")
    current_entries = parse_status_z(out(["git", "status", "--porcelain=1", "-z"], cwd=project_root))
    current_state = repo_state_fingerprint(project_root, current_entries)
    if current_state != plan["state"]:
        raise RuntimeError("Repo changes drifted after prepare; rerun prepare.")
    return current_entries


def publish(plan: dict, json_output: bool) -> int:
    project_root = Path(plan["repo_root"])
    os.chdir(project_root)

    require_clean_index(project_root)
    current_entries = verify_publish_plan(project_root, plan)
    included_entries = [entry for entry in current_entries if entry.path in set(plan["included_paths"])]
    if not included_entries:
        raise RuntimeError("Prepared plan contains no includable paths; nothing to publish.")

    if plan["mode"] == "pr":
        ensure_branch_from_base(plan["branch"], plan["base_ref"], plan["remote"], plan["base_sha"])
    else:
        if current_branch() != plan["base"]:
            raise RuntimeError(f"Expected to publish from base branch '{plan['base']}', but HEAD is '{current_branch()}'.")

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


def prepare(args: argparse.Namespace, json_output: bool) -> int:
    if args.repo.strip():
        repo_path = Path(args.repo).expanduser().resolve()
        if not repo_path.exists():
            print(f"--repo path does not exist: {repo_path}", file=sys.stderr)
            return 2
        os.chdir(repo_path)

    try:
        project_root = require_git_repo()
    except Exception as exc:
        print(f"Not a git repo: {exc}", file=sys.stderr)
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
    parser = argparse.ArgumentParser(prog="git-publish", description="Deterministic git publish with explicit prepare and publish phases.")
    parser.add_argument("--action", choices=["prepare", "publish"], required=True)
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
