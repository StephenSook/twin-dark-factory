#!/usr/bin/env python3
"""Validate a fresh percentage reading without contacting a model."""

from __future__ import annotations

import math
import sys
import time
from datetime import datetime, timezone


def parse_observed_at(value: str) -> float:
    """Accept Unix seconds or an ISO 8601 timestamp."""
    try:
        return float(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()


def validate(
    used_percent: str,
    observed_at: str,
    maximum_percent: str,
    maximum_age_seconds: str,
    now: float | None = None,
) -> None:
    used = float(used_percent)
    observed = parse_observed_at(observed_at)
    maximum = float(maximum_percent)
    maximum_age = float(maximum_age_seconds)
    current = time.time() if now is None else now
    values = (used, observed, maximum, maximum_age, current)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("meter values must be finite")
    if not 0 <= used < maximum:
        raise ValueError("usage is outside the allowed range")
    age = current - observed
    if not -60 <= age <= maximum_age:
        raise ValueError("meter timestamp is stale or too far in the future")


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: check_usage_meter.py <used-percent> <observed-at> "
            "<maximum-percent> <maximum-age-seconds>",
            file=sys.stderr,
        )
        return 2
    try:
        validate(*argv[1:])
    except (ValueError, OverflowError) as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1
    print("PASS  usage meter is fresh and below the refusal threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
