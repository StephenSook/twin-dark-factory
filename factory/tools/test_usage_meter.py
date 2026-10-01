#!/usr/bin/env python3
"""Tests for the preflight usage-meter validator."""

import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "factory" / "tools"))

from check_usage_meter import validate  # noqa: E402


def expect_failure(*args: str, now: float) -> None:
    try:
        validate(*args, now=now)
    except (ValueError, OverflowError):
        return
    raise AssertionError(f"expected failure for {args!r}")


now = 2_000_000_000.0
validate("0", str(now), "10", "600", now=now)
validate("9.99", "2033-05-18T03:32:50Z", "10", "600", now=now)
expect_failure("10", str(now), "10", "600", now=now)
expect_failure("9", str(now - 601), "10", "600", now=now)
expect_failure("9", str(now + 61), "10", "600", now=now)
expect_failure("nan", str(now), "10", "600", now=now)
expect_failure("", str(now), "10", "600", now=now)

preflight = ROOT / "factory" / "tools" / "preflight.sh"
subprocess.run(["bash", "-n", str(preflight)], check=True)
source = preflight.read_text()
assert "NOTE  " not in source
assert "CLAUDE_WEEKLY_USED_PERCENT" in source
assert "CLAUDE_METER_AT" in source
assert 'check_usage_meter.py" "$cl" "$cl_at" 10 600' in source

print("ok   fresh low usage passes; stale, malformed and high usage fail")
