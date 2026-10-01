#!/usr/bin/env python3
"""Regression checks for stale and wrongly bound BAND seat runtimes."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "factory" / "tools" / "check_seat_runtime.py"
ROOM = "10000000-0000-4000-8000-000000000001"
failures = []


def runtime(cwd, transport="codex-app-server", model="gpt-6-astra"):
    return {
        "spawn": {"cwd": str(cwd), "auth_mode": "inherit"},
        "thread": {"model": model},
        "transport": transport,
    }


def check(label, mutate, want, expected):
    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        repo = root / "result"
        stale = root / "stale"
        repo.mkdir()
        stale.mkdir()
        seats = root / "seats.json"
        seats.write_text(json.dumps({"modeler": {"harness": "Codex", "model": "gpt-6-astra"}}))
        status = {
            "state": "connected",
            "peer": {"host_sessions": [
                {"id": "modeler", "room": "", "runtime": runtime(repo)},
                {"id": f"modeler-{ROOM}", "room": ROOM, "runtime": runtime(repo)},
            ]},
        }
        mutate(status, stale)
        result = subprocess.run(
            [sys.executable, str(TOOL), str(repo), ROOM, "modeler", str(seats)],
            input=json.dumps(status),
            capture_output=True,
            text=True,
        )
    output = result.stdout + result.stderr
    if (result.returncode == 0) == want and expected in output:
        print(f"ok   {label}")
    else:
        failures.append(label)
        print(f"BAD  {label}")
        print(output)


check("matching parked and room runtime passes", lambda _s, _p: None, True, "parked and room-bound")
check("stale room runtime cwd fails", lambda s, p: s["peer"]["host_sessions"][1]["runtime"]["spawn"].update(cwd=str(p)),
      False, "does not resolve")
check("missing room binding fails", lambda s, _p: s["peer"]["host_sessions"].pop(),
      False, "0 runtimes bound")
check("wrong transport fails", lambda s, _p: s["peer"]["host_sessions"][0]["runtime"].update(transport="opencode"),
      False, "transport")
check("API-key auth fails", lambda s, _p: s["peer"]["host_sessions"][1]["runtime"]["spawn"].update(auth_mode="api_key"),
      False, "auth mode")
check("missing model identifier fails", lambda s, _p: s["peer"]["host_sessions"][0]["runtime"]["thread"].pop("model"),
      False, "model identifier is missing")
check("wrong model identifier fails", lambda s, _p: s["peer"]["host_sessions"][1]["runtime"]["thread"].update(model="other-model"),
      False, "does not contain")
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
