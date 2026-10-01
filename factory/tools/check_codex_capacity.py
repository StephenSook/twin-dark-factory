#!/usr/bin/env python3
"""Decide whether the Codex account can carry a full run, from its newest meter record.

A run has capacity when the weekly plan meter is below the refusal threshold, or when
the plan is past it but a purchased credit balance covers a full run with margin.
Credits are spent only after the plan limit is reached, so they extend a run that
would otherwise stop mid-stage.
"""

from __future__ import annotations

import glob
import json
import math
import os
import sys
import time

MAX_PLAN_USED_PERCENT = 60.0
# Dev run 1's two Codex seats used 1.79M input, 92.6M cached and 0.35M output tokens,
# about 1,642 credits at the GPT-5.5 rate card. 2,000 leaves a margin above that.
MIN_CREDIT_BALANCE = 2000.0


WEEKLY_WINDOW_MINUTES = 10080
MAX_RECORD_AGE_SECONDS = 1800


def _percent(window: dict) -> float | None:
    used = window.get("used_percent")
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) \
            or not 0 <= used <= 100:
        return None
    return float(used)


def decide(rate_limits: object) -> tuple[bool, str]:
    if not isinstance(rate_limits, dict):
        return False, "Codex meter record is missing"
    windows = [rate_limits.get(name) for name in ("primary", "secondary")]
    windows = [window for window in windows if window is not None]
    if not windows or not all(isinstance(window, dict) for window in windows):
        return False, "Codex weekly usage is missing or malformed"
    readings = [_percent(window) for window in windows]
    if any(reading is None for reading in readings):
        return False, "Codex weekly usage is missing or malformed"
    if not any(window.get("window_minutes") == WEEKLY_WINDOW_MINUTES for window in windows):
        return False, "Codex meter has no weekly window"
    # Gate on the most used window, so a fresh short window cannot hide a spent week.
    used = max(readings)
    if used < MAX_PLAN_USED_PERCENT:
        return True, f"Codex weekly usage {used:g}% (< {MAX_PLAN_USED_PERCENT:g})"
    credits = rate_limits.get("credits")
    if not isinstance(credits, dict) or credits.get("has_credits") is not True:
        return False, f"Codex weekly usage {used:g}% (want < {MAX_PLAN_USED_PERCENT:g}) and no credits"
    try:
        balance = float(credits.get("balance"))
    except (TypeError, ValueError):
        return False, f"Codex weekly usage {used:g}% and the credit balance is malformed"
    if not math.isfinite(balance) or balance < MIN_CREDIT_BALANCE:
        return False, (f"Codex weekly usage {used:g}% and credit balance {balance:g} "
                       f"(want >= {MIN_CREDIT_BALANCE:g})")
    return True, (f"Codex weekly usage {used:g}% with credit balance {balance:g} "
                  f"(>= {MIN_CREDIT_BALANCE:g})")


def newest_rate_limits(root: str, now: float | None = None) -> object:
    """Return the newest record only from the newest session file, which must be fresh."""
    files = sorted(glob.glob(os.path.join(root, "*", "*", "*", "*.jsonl")), key=os.path.getmtime)
    if not files:
        return None
    newest = files[-1]
    current = time.time() if now is None else now
    if current - os.path.getmtime(newest) > MAX_RECORD_AGE_SECONDS:
        raise ValueError("Codex meter record is stale: run a fresh Codex probe first")
    last = None
    for path in [newest]:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if '"rate_limits"' not in line:
                    continue
                try:
                    payload = json.loads(line).get("payload")
                except (json.JSONDecodeError, AttributeError):
                    continue
                if isinstance(payload, dict) and isinstance(payload.get("rate_limits"), dict):
                    last = payload["rate_limits"]
    return last


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: check_codex_capacity.py [codex-sessions-dir]", file=sys.stderr)
        return 2
    root = argv[1] if len(argv) == 2 else os.path.expanduser("~/.codex/sessions")
    try:
        ok, message = decide(newest_rate_limits(root))
    except Exception as exc:  # one FAIL line, never a traceback, whatever went wrong
        ok, message = False, f"Codex meter unreadable: {type(exc).__name__}: {exc}".replace("\n", " ")
    print(("PASS  " if ok else "FAIL  ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
