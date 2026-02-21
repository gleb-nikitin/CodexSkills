#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


JUNK_BASENAMES = {".DS_Store"}
SCRIPT_DIR = Path(__file__).resolve().parent


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=check)


def out(cmd: list[str], *, cwd: Path | None = None) -> str:
    return run(cmd, cwd=cwd).stdout.strip()


def require_git_repo() -> Path:
    top = out(["git", "rev-parse", "--show-toplevel"])
    return Path(top)


def default_remote_branch(remote: str) -> str:
    # Prefer "git remote show" because it works without network.
    try:
        info = out(["git", "remote", "show", remote])
        m = re.search(r"HEAD branch:\s*(\S+)", info)
        if m:
            head_branch = m.group(1).strip()
            if head_branch and head_branch != "(unknown)":
                return head_branch
    except Exception:
        pass
    # Fallbacks
    for b in ("main", "master"):
        try:
            out(["git", "show-ref", "--verify", f"refs/heads/{b}"])
            return b
        except Exception:
            continue
    return "main"


def now_ts() -> str:
    return out(["date", "+%Y-%m-%d %H:%M"])


def append_project_log(project_root: Path, line: str) -> None:
    log_path = project_root / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def is_junk_path(p: str) -> bool:
    return Path(p).name in JUNK_BASENAMES


@dataclass(frozen=True)
class StatusEntry:
    code: str
    path: str
    orig_path: str | None = None


def parse_status_z(status_z: str) -> list[StatusEntry]:
    # Porcelain v1 -z entries:
    # XY SP path\0
    # For renames: XY SP path\0orig_path\0
    parts = status_z.split("\0")
    entries: list[StatusEntry] = []
    i = 0
    while i < len(parts):
        raw = parts[i]
        i += 1
        if not raw:
            continue
        if len(raw) < 3:
            # Unexpected, but don't crash the whole publish.
            continue
        code = raw[:2]
        rest = raw[2:]
        # Git porcelain uses a single separator (space) after XY, but be defensive:
        # some configs/edges may produce multiple spaces or tabs.
        if rest and rest[0] in (" ", "\t"):
            rest = rest[1:]
        path = rest
        orig: str | None = None
        if code[0] == "R" or code[1] == "R":
            if i < len(parts):
                orig = parts[i]
                i += 1
        entries.append(StatusEntry(code=code, path=path, orig_path=orig))
    return entries


def staged_is_empty() -> bool:
    r = subprocess.run(["git", "diff", "--staged", "--quiet"])
    return r.returncode == 0


def chunked(seq: list[str], size: int = 50) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def has_ref(ref: str) -> bool:
    return subprocess.run(["git", "show-ref", "--verify", ref]).returncode == 0


def ensure_branch(branch: str, base: str, remote: str) -> None:
    current = out(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if current == branch:
        return
    if has_ref(f"refs/heads/{branch}"):
        run(["git", "checkout", branch])
        return
    remote_branch_ref = f"{remote}/{branch}"
    if has_ref(f"refs/remotes/{remote_branch_ref}"):
        run(["git", "checkout", "-B", branch, remote_branch_ref])
        return
    # Create from remote/base if available, else local base.
    remote_base_ref = f"{remote}/{base}"
    if has_ref(f"refs/remotes/{remote_base_ref}"):
        run(["git", "checkout", "-B", branch, remote_base_ref])
    else:
        run(["git", "checkout", "-B", branch, base])


def stage_explicit(entries: list[StatusEntry]) -> None:
    tracked_changes: list[str] = []
    new_files: list[str] = []

    for e in entries:
        if is_junk_path(e.path):
            continue
        x, y = e.code[0], e.code[1]
        # Untracked
        if e.code == "??":
            new_files.append(e.path)
            continue
        # Anything else: treat as tracked change (incl deletions/renames)
        if x != " " or y != " ":
            tracked_changes.append(e.path)

    for grp in chunked(tracked_changes):
        # Explicit paths only; stages modifications/deletions for tracked files.
        run(["git", "add", "-u", "--"] + grp)

    for grp in chunked(new_files):
        run(["git", "add", "--"] + grp)


def build_pr_body(project_root: Path, base: str, head: str) -> str:
    lines: list[str] = []
    lines.append("Changes (git):")
    try:
        diffstat = out(["git", "diff", "--stat", f"origin/{base}..{head}"])
    except Exception:
        diffstat = out(["git", "diff", "--stat", f"{base}..{head}"])
    lines.append(diffstat or "(no diffstat)")
    lines.append("")
    lines.append("Log since last git-publish marker:")
    helper = SCRIPT_DIR / "log_since_last_push.py"
    if helper.exists():
        p = run(["python3", str(helper), "--log", str(project_root / "log.md"), "--max", "80"], check=False)
        txt = (p.stdout or "").strip()
        lines.append(txt if txt else "(no log lines)")
    else:
        lines.append("(helper missing)")
    return "\n".join(lines).rstrip() + "\n"


def gh_pr_create(base: str, head: str, title: str, body_file: Path) -> str | None:
    helper = SCRIPT_DIR / "create_pr_gh.sh"
    if not helper.exists():
        return None
    p = run([str(helper), base, head, title, str(body_file)], check=False)
    if p.returncode != 0:
        return None
    url = (p.stdout or "").strip()
    return url or None


def api_pr_create(base: str, head: str, title: str, body: str) -> str | None:
    helper = SCRIPT_DIR / "create_pr.py"
    if not helper.exists():
        return None
    p = run(
        ["python3", str(helper), "--base", base, "--head", head, "--title", title, "--body", body],
        check=False,
    )
    if p.returncode != 0:
        return None
    url = (p.stdout or "").strip()
    return url or None


def commit_log_marker(project_root: Path, marker: str, remote: str, branch: str) -> None:
    append_project_log(project_root, marker)
    run(["git", "add", "--", "log.md"])
    if staged_is_empty():
        return
    run(["git", "commit", "-m", "chore: git-publish marker"])
    run(["git", "push", remote, branch])


def main() -> int:
    ap = argparse.ArgumentParser(prog="git-publish", description="Deterministic git publish (branch+PR by default).")
    ap.add_argument("--mode", choices=["pr", "no-pr"], default="pr")
    ap.add_argument("--topic", default="", help="Branch topic slug (default: auto)")
    ap.add_argument(
        "--repo",
        default="",
        help="Path to git repo (recommended: repo root). If set, execution is anchored to this repo.",
    )
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--base", default="", help="Base branch (default: remote HEAD branch)")
    ap.add_argument("--message", default="", help="Commit message (default: auto)")
    ap.add_argument("--pr-title", default="", help="PR title (default: auto)")
    ap.add_argument("--dry-run", action="store_true", help="Print what would happen without committing/pushing.")
    args = ap.parse_args()

    if args.repo.strip():
        repo_path = Path(args.repo).expanduser().resolve()
        if not repo_path.exists():
            print(f"--repo path does not exist: {repo_path}", file=sys.stderr)
            return 2
        os.chdir(repo_path)

    try:
        project_root = require_git_repo()
    except Exception as e:
        print(f"Not a git repo: {e}", file=sys.stderr)
        return 2

    os.chdir(project_root)
    remote = args.remote
    base = args.base.strip() or default_remote_branch(remote)

    mode = args.mode
    topic = args.topic.strip()
    if not topic:
        # Derive from folder name for determinism.
        topic = Path(project_root).name
    topic = re.sub(r"[^a-z0-9-]+", "-", topic.lower()).strip("-") or "update"
    target_branch = base
    if mode == "pr":
        target_branch = f"codex/{topic}"

    status_z = out(["git", "status", "--porcelain=1", "-z"])
    entries = parse_status_z(status_z)
    if not entries:
        print("No changes to publish.")
        return 0

    if args.dry_run:
        print(f"mode={mode} base={base} remote={remote} branch={target_branch}")
        print("paths:")
        for e in entries:
            print(f"  {e.code} {e.path}")
        return 0

    if mode == "pr":
        ensure_branch(target_branch, base, remote)
    else:
        # no-pr: publish directly to base branch
        ensure_branch(base, base, remote)
        target_branch = base

    status_z = out(["git", "status", "--porcelain=1", "-z"])
    entries = parse_status_z(status_z)
    if not entries:
        print("No changes to publish.")
        return 0

    stage_explicit(entries)
    if staged_is_empty():
        print("Nothing staged after filtering; refusing to commit.", file=sys.stderr)
        return 2

    msg = args.message.strip() or f"chore: {topic}"
    run(["git", "commit", "-m", msg])

    # Push
    if mode == "pr":
        run(["git", "push", "-u", remote, target_branch])
    else:
        run(["git", "push", remote, base])

    pr_url: str | None = None
    if mode == "pr":
        body = build_pr_body(project_root, base, target_branch)
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(body)
            body_path = Path(f.name)
        try:
            title = args.pr_title.strip() or f"{topic}: publish"
            pr_url = gh_pr_create(base, target_branch, title, body_path)
            if not pr_url:
                pr_url = api_pr_create(base, target_branch, title, body)
        finally:
            try:
                body_path.unlink()
            except Exception:
                pass

    # Log marker (append-only). Never include secrets.
    ts = now_ts()
    pr_part = f" pr={pr_url}" if pr_url else ""
    marker = f"{ts} | git-publish skill | push mode={mode} branch={target_branch} base={base}{pr_part} | success"
    commit_log_marker(project_root, marker, remote, target_branch)

    if pr_url:
        print(pr_url)
    else:
        if mode == "pr":
            print(f"PR not auto-created; open: https://github.com/<owner>/<repo>/pull/new/{shlex.quote(target_branch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
