"""Regression checks for the room-cap gate and FACTORY.md room provenance."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECK_ROOM = ROOT / "factory" / "tools" / "check_room.py"
FACTORY_MD = ROOT / "factory" / "tools" / "factory_md.py"
failures = []


def message(number, kind, sender_type="Agent", sender="coordinator", content=""):
    return {
        "id": f"{number:08x}-0000-4000-8000-{number:012x}",
        "insertedAt": "2026-01-01T00:00:00.000Z",
        "messageType": kind,
        "senderId": sender,
        "senderName": sender,
        "senderType": sender_type,
        "content": content,
    }


def export(messages):
    return {
        "exportedAt": "2026-01-01T00:00:01.000Z",
        "room": {"id": "room-test", "title": "test"},
        "messages": messages,
    }


def boundary_room(snapshot=3, announce_lean=False):
    messages = [
        message(1, "text", "Human", "human", "dispatch"),
        message(2, "text", sender="gatekeeper", content="ACCEPT abcdef1"),
    ]
    while len(messages) < snapshot - 1:
        messages.append(message(len(messages) + 1, "thought"))
    messages.append(message(len(messages) + 1, "tool_call"))
    assert len(messages) == snapshot
    messages.append(message(len(messages) + 1, "tool_result"))
    if announce_lean:
        messages.append(message(len(messages) + 1, "text", content="LEAN MODE"))
    messages.append(message(
        len(messages) + 1,
        "text",
        content=f"stage report\nROOM COUNT {snapshot:,} OF 10000",
    ))
    return export(messages)


def run_room(label, room, want, allow_development=False, expected=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "room.json"
        path.write_text(json.dumps(room))
        command = [sys.executable, str(CHECK_ROOM), str(path)]
        if allow_development:
            command.append("--allow-human-after-dispatch")
        result = subprocess.run(command, capture_output=True, text=True)
    got = result.returncode == 0
    output = result.stdout + result.stderr
    if got == want and (expected is None or expected in output):
        print(f"ok   {label}")
    else:
        failures.append(label)
        print(f"BAD  {label}: wanted {'pass' if want else 'fail'}")
        print(result.stdout)
        print(result.stderr)


def run_factory_md_checks():
    room = boundary_room()
    floor = {
        "generated_from": {"room_id": "room-test", "messages": len(room["messages"])},
        "duration_s": 0,
        "events": [],
        "commits": [],
        "totals": {
            "human_messages_after_dispatch": 0,
            "rejects": 0,
            "accepts": 0,
            "handoffs": 0,
            "rejects_followed_by_seat_commit": 0,
            "seat_commits": 0,
            "commits": 0,
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        room_path = tmp / "room.json"
        floor_path = tmp / "floor.json"
        sessions_path = tmp / "sessions.json"
        facts_path = tmp / "facts.json"
        room_path.write_text(json.dumps(room))
        floor_path.write_text(json.dumps(floor))
        sessions_path.write_text('{"sessions": []}')
        facts_path.write_text("{}")
        command = [
            sys.executable, str(FACTORY_MD),
            "--repo", str(ROOT / "factory"),
            "--room", str(room_path),
            "--floor", str(floor_path),
            "--sessions", str(sessions_path),
            "--facts", str(facts_path),
            "--draft",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        room_hash = hashlib.sha256(room_path.read_bytes()).hexdigest()
        expected = f"Room message budget: **{len(room['messages'])} of 10,000**"
        good = result.returncode == 0 and expected in result.stdout and room_hash in result.stdout
        if good:
            print("ok   FACTORY.md count and hash come from room.json")
        else:
            failures.append("FACTORY.md count and hash")
            print("BAD  FACTORY.md count and hash")
            print(result.stdout)
            print(result.stderr)

        floor["generated_from"]["messages"] += 1
        floor_path.write_text(json.dumps(floor))
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0 and "different message counts" in result.stderr:
            print("ok   FACTORY.md refuses a stale floor count")
        else:
            failures.append("FACTORY.md stale floor count")
            print("BAD  FACTORY.md accepted a stale floor count")

        floor["generated_from"]["messages"] -= 1
        floor_path.write_text(json.dumps(floor))
        facts_path.write_text('{"room_sha256": "wrong"}')
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0 and "sha256 differs" in result.stderr:
            print("ok   FACTORY.md refuses a stale room hash")
        else:
            failures.append("FACTORY.md stale room hash")
            print("BAD  FACTORY.md accepted a stale room hash")


run_room("boundary report below lean threshold", boundary_room(), True)
duplicate_accept = boundary_room()
duplicate_accept["messages"].insert(
    2,
    message(99_999, "text", sender="gatekeeper", content="ACCEPT abcdef1234567890"),
)
duplicate_accept["messages"][-1]["content"] = "stage report\nROOM COUNT 4 OF 10000"
run_room("short and full forms of one accepted revision count once", duplicate_accept, True)
run_room("accepted stage without boundary report", export([
    message(1, "text", "Human", "human", "dispatch"),
    message(2, "text", sender="gatekeeper", content="ACCEPT abcdef1"),
]), False, expected="has one coordinator ROOM COUNT report")
run_room("6,000 snapshot with lean announcement", boundary_room(6_000, True), True)
run_room("6,000 snapshot without lean announcement", boundary_room(6_000, False), False,
         expected="coordinator announced LEAN MODE")

underreported = boundary_room(6_000, False)
underreported["messages"][-1]["content"] = "stage report\nROOM COUNT 5,982 OF 10000"
run_room("near-boundary undercount cannot avoid lean mode", underreported, False,
         expected="coordinator announced LEAN MODE")

lean_only_in_report = boundary_room(6_000, False)
lean_only_in_report["messages"][-1]["content"] = "LEAN MODE\nROOM COUNT 6,000 OF 10000"
run_room("lean words inside the report are not an announcement", lean_only_in_report, False,
         expected="coordinator announced LEAN MODE")

over_cap = boundary_room(6_000, True)
while len(over_cap["messages"]) <= 10_000:
    over_cap["messages"].append(message(len(over_cap["messages"]) + 1, "thought"))
run_room("room above hard cap", over_cap, False, expected="room message count is within BAND's hard limit")

missing_text_fields = boundary_room()
del missing_text_fields["messages"][-1]["senderName"]
run_room("text message missing its sender name", missing_text_fields, False,
         expected="every text message has")

run_room("development export may predate budget reports", export([
    message(1, "text", "Human", "human", "dispatch"),
    message(2, "text", sender="gatekeeper", content="ACCEPT abcdef1"),
]), True, allow_development=True)

run_factory_md_checks()
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
