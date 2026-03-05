#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request


def run(*cmd: str) -> str:
    return subprocess.check_output(list(cmd), text=True).strip()


def parse_github_owner_repo(remote_url: str) -> tuple[str, str]:
    # Supports:
    # - git@github.com:owner/repo.git
    # - https://github.com/owner/repo.git
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", remote_url.strip())
    if not m:
        raise ValueError(f"Unsupported remote URL: {remote_url!r}")
    return m.group("owner"), m.group("repo")


def github_request(url: str, token: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    # GitHub accepts either "token" (classic) or "Bearer" (fine-grained). Use Bearer if looks like ghp_/github_pat_.
    if token.startswith(("ghp_", "github_pat_")):
        req.add_header("Authorization", f"Bearer {token}")
    else:
        req.add_header("Authorization", f"token {token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {e.code}: {body}") from e


def token_from_keychain(service: str, account: str) -> str:
    # macOS only. Returns token without printing it.
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as e:
        raise RuntimeError("macOS 'security' tool not found; cannot read Keychain token.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Keychain item not found for service={service!r} account={account!r}."
        ) from e
    return out.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a GitHub PR for the current repo via API.")
    ap.add_argument("--base", required=True, help="Base branch (e.g. master)")
    ap.add_argument("--head", required=True, help="Head branch (e.g. codex/my-branch)")
    ap.add_argument("--title", required=True, help="PR title")
    ap.add_argument("--body", default="", help="PR body")
    ap.add_argument("--remote", default="origin", help="Git remote name (default: origin)")
    ap.add_argument(
        "--keychain-service",
        default=os.environ.get("CODEX_GITHUB_TOKEN_KEYCHAIN_SERVICE", "codex_github_token"),
        help="macOS Keychain service name (default: codex_github_token)",
    )
    ap.add_argument(
        "--keychain-account",
        default=os.environ.get("CODEX_GITHUB_TOKEN_KEYCHAIN_ACCOUNT", os.environ.get("USER", "")),
        help="macOS Keychain account name (default: $USER)",
    )
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        if not args.keychain_account:
            print(
                "Missing GITHUB_TOKEN and no keychain account provided (set --keychain-account).",
                file=sys.stderr,
            )
            return 2
        try:
            token = token_from_keychain(args.keychain_service, args.keychain_account)
        except Exception as e:
            print(str(e), file=sys.stderr)
            print("Set GITHUB_TOKEN or store a token in macOS Keychain.", file=sys.stderr)
            return 2

    remote_url = run("git", "remote", "get-url", args.remote)
    owner, repo = parse_github_owner_repo(remote_url)

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    payload = {"title": args.title, "head": args.head, "base": args.base, "body": args.body}
    pr = github_request(url, token, payload)

    html_url = pr.get("html_url")
    if html_url:
        print(html_url)
        return 0

    print(json.dumps(pr, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
