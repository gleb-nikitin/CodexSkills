#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


PUSH_MARKER_RE = re.compile(r"\|\s*git-publish skill\s*\|\s*push\b.*\|\s*success\s*$")


def read_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [ln.rstrip("\n") for ln in text.splitlines()]


def is_content_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("#"):
        return False
    return True


def lines_since_last_success(lines: list[str]) -> list[str]:
    last_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if PUSH_MARKER_RE.search(lines[i]):
            last_idx = i
            break
    tail = lines[last_idx + 1 :] if last_idx != -1 else lines
    return [ln for ln in tail if is_content_line(ln)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Print log.md lines since last successful git-publish marker.")
    ap.add_argument("--log", default="log.md", help="Path to log file (default: ./log.md)")
    ap.add_argument("--max", type=int, default=200, help="Max lines to print (default: 200)")
    args = ap.parse_args()

    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = Path(os.getcwd()) / log_path

    lines = read_lines(log_path)
    out = lines_since_last_success(lines)[: max(args.max, 0)]

    if not out:
        return 0

    for ln in out:
        sys.stdout.write(ln + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

