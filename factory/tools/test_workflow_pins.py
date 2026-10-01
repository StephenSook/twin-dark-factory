#!/usr/bin/env python3
"""Refuse mutable third-party action tags in factory and result workflows."""
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW_DIRS = (ROOT / ".github" / "workflows", ROOT / "factory" / "result-ci")
USE = re.compile(r"^\s*-\s+uses:\s+([^\s#]+)", re.MULTILINE)
PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


failures = []
seen = 0
for directory in WORKFLOW_DIRS:
    for path in sorted(directory.glob("*.yml")):
        for action in USE.findall(path.read_text()):
            seen += 1
            if not PINNED.fullmatch(action):
                failures.append(f"{path.relative_to(ROOT)}: mutable or invalid action reference {action}")

if seen < 11:
    failures.append(f"workflow action reference floor failed: found {seen}, expected at least 11")

if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)

print(f"ok   {seen} workflow action references use immutable 40-character SHAs")
