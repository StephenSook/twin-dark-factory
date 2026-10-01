#!/usr/bin/env python3
"""Regression checks for the exact judged-room roster gate."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "factory" / "tools" / "check_room_participants.py"
SEATS = ["coordinator", "modeler", "builder", "surface", "gatekeeper", "auditor"]
failures = []


def listing(seats):
    lines = [
        f"stephensookra/{seat} [member] role text (Agent; id={index:08x}-0000-4000-8000-{index:012x})"
        for index, seat in enumerate(seats, 1)
    ]
    lines.append("stephensookra [owner] Stephen Sookra (User; id=90000000-0000-4000-8000-000000000000)")
    return "\n".join(lines) + "\n"


def check(label, seats, want, expected_text):
    with tempfile.TemporaryDirectory() as raw:
        path = pathlib.Path(raw) / "seats.json"
        path.write_text(json.dumps({seat: {"harness": "test"} for seat in SEATS}))
        result = subprocess.run(
            [sys.executable, str(TOOL), str(path)],
            input=listing(seats),
            capture_output=True,
            text=True,
        )
    output = result.stdout + result.stderr
    got = result.returncode == 0
    if got == want and expected_text in output:
        print(f"ok   {label}")
    else:
        failures.append(label)
        print(f"BAD  {label}")
        print(output)


check("exact six-seat roster passes", SEATS, True, "exactly 6 configured agents")
check("missing auditor fails", SEATS[:-1], False, "missing=['auditor']")
check("an extra agent fails", SEATS + ["intruder"], False, "extra=['intruder']")
check("temporary toy handle fails for judged room", ["coordinator-cx", *SEATS[1:]], False,
      "missing=['coordinator']")
check("duplicate handle fails", SEATS + ["auditor"], False, "duplicate agent handles")
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
