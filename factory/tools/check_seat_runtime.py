#!/usr/bin/env python3
"""Require one seat's parked template and new-room runtime to target the judged repository."""
import json
import pathlib
import sys

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: check_seat_runtime.py <result-repo> <room-id> <seat> <seats.json>"
    )
repo = pathlib.Path(sys.argv[1]).resolve()
room_id, seat = sys.argv[2:4]
configured = json.loads(pathlib.Path(sys.argv[4]).read_text())
if seat not in configured:
    raise SystemExit(f"seat {seat!r} is not configured")
data = json.load(sys.stdin)
peer = data.get("peer") or {}
if data.get("state") != "connected":
    raise SystemExit(f"seat {seat} is not connected")
sessions = peer.get("host_sessions") or []
parked_id = "default" if configured[seat].get("harness") == "OpenCode" else seat
parked = [item for item in sessions if item.get("id") == parked_id and not item.get("room")]
bound = [item for item in sessions if item.get("room") == room_id]
if len(parked) != 1:
    raise SystemExit(f"seat {seat} has {len(parked)} parked templates named {parked_id}")
if len(bound) != 1:
    raise SystemExit(f"seat {seat} has {len(bound)} runtimes bound to room {room_id}")

transport_by_harness = {
    "Claude Code": "claude-code-cli",
    "Codex": "codex-app-server",
    "OpenCode": "opencode",
}
expected_transport = transport_by_harness[configured[seat]["harness"]]
expected_model = configured[seat]["model"].split(" (", 1)[0]
for label, item in (("parked", parked[0]), ("room-bound", bound[0])):
    runtime = item.get("runtime") or {}
    spawn = runtime.get("spawn") or {}
    cwd = spawn.get("cwd")
    if not cwd or pathlib.Path(cwd).resolve() != repo:
        raise SystemExit(f"seat {seat} {label} cwd {cwd!r} does not resolve to {repo}")
    if runtime.get("transport") != expected_transport:
        raise SystemExit(
            f"seat {seat} {label} transport {runtime.get('transport')!r} "
            f"is not {expected_transport!r}"
        )
    if spawn.get("auth_mode") != "inherit":
        raise SystemExit(f"seat {seat} {label} auth mode is not inherit")
    # Claude Code runtimes record the model in their own block; Codex and OpenCode in the thread.
    model_block = "claude_code" if expected_transport == "claude-code-cli" else "thread"
    actual_model = (runtime.get(model_block) or {}).get("model")
    if not isinstance(actual_model, str) or not actual_model:
        raise SystemExit(f"seat {seat} {label} model identifier is missing")
    if expected_model not in actual_model:
        raise SystemExit(
            f"seat {seat} {label} model {actual_model!r} does not contain {expected_model!r}"
        )
print(f"seat {seat} parked and room-bound runtimes target {repo}")
