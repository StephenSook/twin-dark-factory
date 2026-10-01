#!/usr/bin/env python3
"""Regression checks for the Factory Floor copy packaged with result repos."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "factory" / "floor" / "index.html"

HEADLINE = '<h1 id="h1">Six agents. One verifiable run.</h1>'
STALE_HEADLINE = '<h1 id="h1">Five agents built it. Nobody touched it.</h1>'
COMMAND = '<code>python tools/floor_data.py room.json . floor.json</code>'
STALE_COMMAND = (
    '<code>python factory/tools/floor_data.py room.json . floor.json</code>'
)


def copy_errors(text: str) -> list[str]:
    """Return errors for stale or missing judge-facing Factory Floor copy."""
    errors: list[str] = []
    if text.count(HEADLINE) != 1 or STALE_HEADLINE in text:
        errors.append("headline must describe the six-seat factory exactly once")
    if text.count(COMMAND) != 1 or STALE_COMMAND in text:
        errors.append("reproduction command must use the packaged tools path exactly once")
    return errors


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    checks = [
        ("current Factory Floor copy", not copy_errors(text)),
        (
            "stale five-agent headline is rejected",
            "headline" in " ".join(copy_errors(text.replace(HEADLINE, STALE_HEADLINE, 1))),
        ),
        (
            "stale repository-relative command is rejected",
            "reproduction command"
            in " ".join(copy_errors(text.replace(COMMAND, STALE_COMMAND, 1))),
        ),
    ]

    failures = 0
    for name, passed in checks:
        print(f"{'ok ' if passed else 'BAD'}  {name}")
        failures += not passed
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
