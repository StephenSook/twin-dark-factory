"""Regression checks for the room-cap gate and FACTORY.md room provenance."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECK_ROOM = ROOT / "factory" / "tools" / "check_room.py"
FLOOR_DATA = ROOT / "factory" / "tools" / "floor_data.py"
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
    anchor = messages[-1]["id"]
    messages.append(message(len(messages) + 1, "tool_result"))
    if announce_lean:
        messages.append(message(len(messages) + 1, "text", content="LEAN MODE"))
    messages.append(message(
        len(messages) + 1,
        "text",
        content=f"stage report\nROOM COUNT {snapshot:,} OF 10000 AFTER {anchor}",
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


def run_floor_verdict_checks():
    room = export([
        message(1, "text", "Human", "human", "dispatch"),
        message(2, "text", sender="modeler", content="ACCEPT aaaaaaa model coverage"),
        message(3, "text", sender="coordinator", content="REJECT bbbbbbb relayed decision"),
        message(4, "text", sender="stephensookra/gatekeeper", content="REJECT ccccccc failing burst"),
        message(5, "text", sender="stephensookra/gatekeeper", content="ACCEPT ddddddd stage accepted"),
        message(6, "text", sender="auditor", content="ACCEPT eeeeeee audit closed"),
        message(7, "text", sender="stephensookra/builder", content="fixed the rejected revision"),
    ])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        room_path = tmp / "room.json"
        log_path = tmp / "commits.log"
        floor_path = tmp / "floor.json"
        room_path.write_text(json.dumps(room))
        log_path.write_text(
            f"{'f' * 40}\x1fbuilder\x1f2026-01-01T00:00:01+00:00\x1ffix burst handling\n"
            "stage-1/app.py\n"
        )
        result = subprocess.run(
            [sys.executable, str(FLOOR_DATA), str(room_path), str(log_path), str(floor_path)],
            capture_output=True,
            text=True,
        )
        floor = json.loads(floor_path.read_text()) if floor_path.exists() else {}
    verdicts = [
        (event["from"], verdict["verdict"], verdict["rev"])
        for event in floor.get("events", [])
        for verdict in event["verdicts"]
    ]
    expected = [
        ("gatekeeper", "REJECT", "ccccccc"),
        ("gatekeeper", "ACCEPT", "ddddddd"),
    ]
    totals = floor.get("totals", {})
    good = (
        result.returncode == 0
        and verdicts == expected
        and totals.get("rejects") == 1
        and totals.get("accepts") == 1
        and totals.get("seat_commits") == 1
        and totals.get("rejects_followed_by_seat_commit") == 1
        and floor.get("stage_first_commit_s") == {"1": 1.0}
    )
    if good:
        print("ok   floor data counts only gatekeeper verdicts")
    else:
        failures.append("floor data gatekeeper verdicts")
        print("BAD  floor data counted a non-gatekeeper verdict")
        print(result.stdout)
        print(result.stderr)
        print(verdicts)
        print(totals)


run_room("boundary report below lean threshold", boundary_room(), True)
duplicate_accept = boundary_room()
duplicate_accept["messages"].insert(
    2,
    message(99_999, "text", sender="gatekeeper", content="ACCEPT abcdef1234567890"),
)
duplicate_anchor = duplicate_accept["messages"][3]["id"]
duplicate_accept["messages"][-1]["content"] = (
    f"stage report\nROOM COUNT 4 OF 10000 AFTER {duplicate_anchor}"
)
run_room("short and full forms of one accepted revision count once", duplicate_accept, True)
run_room("accepted stage without boundary report", export([
    message(1, "text", "Human", "human", "dispatch"),
    message(2, "text", sender="gatekeeper", content="ACCEPT abcdef1"),
]), False, expected="has one coordinator ROOM COUNT report")

pre_accept_anchor = export([
    message(1, "text", "Human", "human", "dispatch"),
    message(2, "thought"),
    message(3, "text", sender="gatekeeper", content="ACCEPT abcdef1"),
    message(4, "text", content=f"ROOM COUNT 2 OF 10000 AFTER {message(2, 'thought')['id']}"),
])
run_room("an exact anchor from before ACCEPT fails", pre_accept_anchor, False,
         expected="snapshot follows ACCEPT")
run_room("6,000 snapshot with lean announcement", boundary_room(6_000, True), True)
run_room("6,000 snapshot without lean announcement", boundary_room(6_000, False), False,
         expected="coordinator announced LEAN MODE")

underreported = boundary_room(6_000, False)
underreported["messages"][-1]["content"] = (
    f"stage report\nROOM COUNT 5,982 OF 10000 AFTER {underreported['messages'][5_999]['id']}"
)
run_room("an undercount cannot reuse a later boundary anchor", underreported, False,
         expected="anchor is exported message")

lean_only_in_report = boundary_room(6_000, False)
lean_anchor = lean_only_in_report["messages"][5_999]["id"]
lean_only_in_report["messages"][-1]["content"] = (
    f"LEAN MODE\nROOM COUNT 6,000 OF 10000 AFTER {lean_anchor}"
)
run_room("lean words inside the report are not an announcement", lean_only_in_report, False,
         expected="coordinator announced LEAN MODE")

wrong_anchor = boundary_room()
wrong_anchor["messages"][-1]["content"] = (
    f"stage report\nROOM COUNT 3 OF 10000 AFTER {wrong_anchor['messages'][1]['id']}"
)
run_room("a correct count paired with the wrong anchor fails", wrong_anchor, False,
         expected="anchor is exported message")

off_by_one = boundary_room()
off_by_one["messages"][-1]["content"] = (
    f"stage report\nROOM COUNT 2 OF 10000 AFTER {off_by_one['messages'][2]['id']}"
)
run_room("a count off by one fails even with the real boundary anchor", off_by_one, False,
         expected="anchor is exported message")

reused_anchor_messages = [
    message(1, "text", "Human", "human", "dispatch"),
    message(2, "text", sender="gatekeeper", content="ACCEPT abcdef1"),
    message(3, "tool_call"),
    message(4, "tool_result"),
    message(5, "text", content=f"ROOM COUNT 3 OF 10000 AFTER {message(3, 'tool_call')['id']}"),
    message(6, "text", sender="gatekeeper", content="ACCEPT bcdef12"),
    message(7, "tool_call"),
    message(8, "tool_result"),
    message(9, "text", content=f"ROOM COUNT 7 OF 10000 AFTER {message(3, 'tool_call')['id']}"),
]
run_room("two stages cannot reuse one stale boundary anchor", export(reused_anchor_messages), False,
         expected="each ROOM COUNT report uses a distinct boundary anchor")

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
run_floor_verdict_checks()
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
