#!/usr/bin/env python3
"""Tests for the Codex capacity gate used by the preflight."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "factory" / "tools" / "check_codex_capacity.py"
sys.path.insert(0, str(TOOL.parent))

from check_codex_capacity import decide  # noqa: E402


def meter(used, credits=None):
    record = {"primary": {"used_percent": used, "window_minutes": 10080}}
    if credits is not None:
        record["credits"] = credits
    return record


def bought(balance):
    return {"has_credits": True, "unlimited": False, "balance": balance}


cases = [
    ("low plan usage passes", meter(57.0), True),
    ("plan at the threshold without credits fails", meter(60.0), False),
    ("exhausted plan without credits fails", meter(96.0, {"has_credits": False, "balance": "0"}), False),
    ("exhausted plan with enough credits passes", meter(96.0, bought("2500")), True),
    ("exhausted plan with exactly the floor passes", meter(96.0, bought("2000")), True),
    ("exhausted plan with too few credits fails", meter(96.0, bought("1999.9")), False),
    ("has_credits false ignores a balance", meter(96.0, {"has_credits": False, "balance": "9000"}), False),
    ("malformed balance fails", meter(96.0, bought("lots")), False),
    ("infinite balance fails", meter(96.0, bought("inf")), False),
    ("missing usage fails", {"primary": {}}, False),
    ("boolean usage fails", meter(True), False),
    ("usage above 100 fails", meter(101.0), False),
    ("missing record fails", None, False),
    ("low five-hour window cannot hide a spent week", {
        "primary": {"used_percent": 3.0, "window_minutes": 300},
        "secondary": {"used_percent": 96.0, "window_minutes": 10080}}, False),
    ("weekly window in secondary with headroom passes", {
        "primary": {"used_percent": 3.0, "window_minutes": 300},
        "secondary": {"used_percent": 20.0, "window_minutes": 10080}}, True),
    ("record without a weekly window fails", {
        "primary": {"used_percent": 3.0, "window_minutes": 300}}, False),
    ("malformed secondary window fails", {
        "primary": {"used_percent": 3.0, "window_minutes": 10080}, "secondary": "x"}, False),
]
for label, record, expected in cases:
    ok, message = decide(record)
    assert ok is expected, f"{label}: got {ok} ({message})"
    print(f"ok   {label}")

# The command line reads only the newest record and prints one PASS or FAIL line.
with tempfile.TemporaryDirectory() as tmp:
    day = pathlib.Path(tmp) / "2026" / "10" / "01"
    day.mkdir(parents=True)
    rollout = day / "rollout-a.jsonl"
    rows = [
        {"payload": {"rate_limits": meter(96.0, {"has_credits": False, "balance": "0"})}},
        {"payload": {"type": "message"}},
        {"payload": {"rate_limits": meter(96.0, bought("2500"))}},
    ]
    rollout.write_text("".join(json.dumps(row) + "\n" for row in rows))
    done = subprocess.run([sys.executable, str(TOOL), tmp], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.startswith("PASS  "), done.stdout + done.stderr
    rollout.write_text(json.dumps(rows[0]) + "\n")
    done = subprocess.run([sys.executable, str(TOOL), tmp], capture_output=True, text=True)
    assert done.returncode == 1 and done.stdout.startswith("FAIL  "), done.stdout + done.stderr
    empty = subprocess.run([sys.executable, str(TOOL), str(day / "none")], capture_output=True, text=True)
    assert empty.returncode == 1 and "missing" in empty.stdout, empty.stdout
    # A passing record goes stale after 30 minutes.
    rollout.write_text(json.dumps(rows[2]) + "\n")
    old = rollout.stat().st_mtime - 1801
    os.utime(rollout, (old, old))
    stale = subprocess.run([sys.executable, str(TOOL), tmp], capture_output=True, text=True)
    assert stale.returncode == 1 and "stale" in stale.stdout, stale.stdout
    # An unreadable newest file gives exactly one FAIL line, never a traceback.
    rollout.write_bytes(b'{"payload": {"rate_limits": \xff}}\n')
    broken = subprocess.run([sys.executable, str(TOOL), tmp], capture_output=True, text=True)
    lines = (broken.stdout + broken.stderr).splitlines()
    assert broken.returncode == 1 and len(lines) == 1 and lines[0].startswith("FAIL  "), lines
print("ok   command line reads a fresh newest record, refuses stale or unreadable stores in one line")

preflight = (ROOT / "factory" / "tools" / "preflight.sh").read_text()
assert 'check_codex_capacity.py" 2>&1) && pass' in preflight
assert "used_percent" not in preflight
print("ok   preflight delegates the Codex gate to the tested checker")
