#!/usr/bin/env python3
"""Regression checks for the external room meter and its agent client."""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "factory" / "tools" / "room_meter.py"
SPEC = importlib.util.spec_from_file_location("room_meter", TOOL)
ROOM_METER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROOM_METER)
failures = []
ROOM = "10000000-0000-4000-8000-000000000001"

IDS = [
    "00000001-0000-4000-8000-000000000001",
    "00000002-0000-4000-8000-000000000002",
    "00000003-0000-4000-8000-000000000003",
]


def page(number, total, messages, mutation=7, limit=2, room=ROOM):
    return {
        "page": number,
        "limit": limit,
        "total_pages": total,
        "last_included_mutation_sequence": mutation,
        "messages": [
            {
                "id": item,
                "chat_id": room,
                "inserted_at": f"2026-01-01T00:00:{IDS.index(item) + 1:02d}.000000Z",
                "content": "never persist this",
            }
            for item in messages
        ],
    }


def check(label, condition):
    if condition:
        print(f"ok   {label}")
    else:
        failures.append(label)
        print(f"BAD  {label}")


def expect_error(label, callback, contains):
    try:
        callback()
    except ROOM_METER.MeterError as exc:
        check(label, contains in str(exc))
    else:
        failures.append(label)
        print(f"BAD  {label}: no error")


single = ROOM_METER.collect_snapshot(lambda number: page(number, 1, IDS[:2]), ROOM)
check("one-page count is exact", single["count"] == 2)
check("one-page anchor is newest message by time", single["anchor_id"] == IDS[1])

pages = {
    1: page(1, 2, IDS[:2], limit=2),
    2: page(2, 2, IDS[2:], limit=2),
}
multiple = ROOM_METER.collect_snapshot(lambda number: pages[number], ROOM)
check("multi-page count includes the last-page remainder", multiple["count"] == 3)
check("multi-page anchor comes from the newest item on page one", multiple["anchor_id"] == IDS[1])

expect_error(
    "a response containing another room fails closed",
    lambda: ROOM_METER.collect_snapshot(
        lambda number: page(number, 1, IDS[:2], room="20000000-0000-4000-8000-000000000002"),
        ROOM,
    ),
    "another room",
)

calls = []


def stabilizing_fetch(number):
    calls.append(number)
    attempt = (len(calls) - 1) // 2
    mutation = 10 if attempt == 0 and number == 1 else 11
    return page(number, 2, IDS[:2] if number == 1 else IDS[2:], mutation=mutation)


real_time = ROOM_METER.time.time
ticks = iter((100.0, 200.0))
ROOM_METER.time.time = lambda: next(ticks)
try:
    stabilized = ROOM_METER.collect_snapshot(stabilizing_fetch, ROOM)
finally:
    ROOM_METER.time.time = real_time
check("pagination drift retries and stabilizes", stabilized["mutation_sequence"] == 11)
check("pagination drift used a second snapshot attempt", calls == [1, 2, 1, 2])
check("snapshot age starts at the successful attempt", stabilized["snapshot_started_at_epoch"] == 200.0)

drift_calls = []


def drifting_fetch(number):
    drift_calls.append(number)
    return page(number, 2, IDS[:2] if number == 1 else IDS[2:], mutation=len(drift_calls))


expect_error(
    "persistent pagination drift fails closed",
    lambda: ROOM_METER.collect_snapshot(drifting_fetch, ROOM),
    "changed during every snapshot",
)

empty_last = {
    1: page(1, 2, IDS[:2]),
    2: page(2, 2, []),
}
expect_error(
    "an empty reported last page fails closed",
    lambda: ROOM_METER.collect_snapshot(lambda number: empty_last[number], ROOM),
    "lengths are inconsistent",
)


def in_flight_snapshot_check():
    with tempfile.TemporaryDirectory() as raw:
        repo = pathlib.Path(raw) / "result"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        paths = ROOM_METER.runtime_paths(repo)
        paths["runtime"].mkdir(parents=True)
        instance_id = "30000000-0000-4000-8000-000000000003"
        now = time.time()
        ROOM_METER.atomic_json(paths["meta"], {
            "instance_id": instance_id,
            "pid": os.getpid(),
            "process_start_token": ROOM_METER.process_start_token(os.getpid()),
            "room_id": ROOM,
            "started_at_epoch": now - 1,
            "expires_at_epoch": now + 60,
        })

        def write_state(anchor, snapshot_started, observed):
            ROOM_METER.atomic_json(paths["state"], {
                "schema_version": 1,
                "instance_id": instance_id,
                "room_id": ROOM,
                "snapshot_started_at_epoch": snapshot_started,
                "observed_at_epoch": observed,
                "expires_at_epoch": now + 60,
                "count": 2,
                "anchor_id": anchor,
            })

        write_state(IDS[0], now - 60, now - 59.9)

        def publish_states():
            time.sleep(0.05)
            write_state(IDS[1], now - 0.1, time.time())
            time.sleep(0.35)
            fresh_started = time.time()
            write_state(IDS[2], fresh_started, fresh_started + 0.001)

        writer = threading.Thread(target=publish_states)
        writer.start()
        state, _age = ROOM_METER.wait_for_next_state(repo, 3, 2)
        writer.join()
        check(
            "client waits through stale and pre-request snapshots",
            state["anchor_id"] == IDS[2],
        )


in_flight_snapshot_check()


def instance_swap_check():
    initial = {
        "instance_id": "30000000-0000-4000-8000-000000000003",
        "room_id": ROOM,
    }
    replacement = {
        "instance_id": "40000000-0000-4000-8000-000000000004",
        "room_id": "20000000-0000-4000-8000-000000000002",
        "snapshot_started_at_epoch": time.time() + 1,
    }
    real_live_meta = ROOM_METER.read_live_meta
    real_fresh_state = ROOM_METER.read_fresh_state
    ROOM_METER.read_live_meta = lambda repo, expected_room=None: ({}, initial)
    ROOM_METER.read_fresh_state = lambda repo, max_age: (replacement, 0)
    try:
        expect_error(
            "client refuses an observer instance swap during its wait",
            lambda: ROOM_METER.wait_for_next_state("unused", 3, 1),
            "process changed",
        )
    finally:
        ROOM_METER.read_live_meta = real_live_meta
        ROOM_METER.read_fresh_state = real_fresh_state


instance_swap_check()


def integration_checks():
    with tempfile.TemporaryDirectory() as raw:
        tmp = pathlib.Path(raw)
        repo = tmp / "result"
        checks = tmp / "checks"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        fake = tmp / "fake-band"
        secret = "MESSAGE-CONTENT-MUST-NOT-REACH-LOG"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            f"expected = ['room', 'messages', '{ROOM}', '--page', '1', '--json']\n"
            "if sys.argv[1:] != expected:\n"
            "    print('unexpected argv', file=sys.stderr)\n"
            "    raise SystemExit(23)\n"
            f"messages = [{{'id': '{IDS[0]}', 'chat_id': '{ROOM}', "
            f"'inserted_at': '2026-01-01T00:00:01.000000Z', 'content': '{secret}'}}, "
            f"{{'id': '{IDS[1]}', 'chat_id': '{ROOM}', "
            "'inserted_at': '2026-01-01T00:00:02.000000Z', 'content': 'second'}]\n"
            "print(json.dumps({'page': 1, 'limit': 100, 'total_pages': 1, "
            "'last_included_mutation_sequence': 19, 'messages': messages}))\n"
        )
        fake.chmod(0o700)
        start = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "start",
                "--repo",
                str(repo),
                "--room",
                ROOM,
                "--checks",
                str(checks),
                "--band-bin",
                str(fake),
                "--interval",
                "0.2",
                "--max-seconds",
                "20",
                "--startup-timeout",
                "5",
                "--max-age",
                "3",
            ],
            capture_output=True,
            text=True,
        )
        started = start.returncode == 0 and "READY" in start.stdout
        check("start waits for a real first snapshot", started)
        if not started:
            print(start.stdout)
            print(start.stderr)
            if (checks / "room-meter.log").exists():
                print((checks / "room-meter.log").read_text())
            return
        client = repo / ".git" / "factory" / "count"
        read = subprocess.run([str(client)], capture_output=True, text=True)
        expected = f"ROOM COUNT 2 OF 10000 AFTER {IDS[1]}"
        check("installed client returns an anchored count", read.returncode == 0 and read.stdout.strip() == expected)
        state = json.loads((repo / ".git" / "factory" / "room-meter-state.json").read_text())
        check("state is pinned to the configured room", state["room_id"] == ROOM)
        status = subprocess.run(
            [sys.executable, str(TOOL), "status", "--repo", str(repo), "--room", ROOM],
            capture_output=True,
            text=True,
        )
        check("status confirms the expected room", status.returncode == 0 and f"room={ROOM}" in status.stdout)
        short_status = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "status",
                "--repo",
                str(repo),
                "--room",
                ROOM,
                "--min-remaining-seconds",
                "30",
            ],
            capture_output=True,
            text=True,
        )
        check(
            "status refuses an observer without enough remaining lifetime",
            short_status.returncode != 0 and "remaining lifetime" in short_status.stderr,
        )
        wrong_status = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "status",
                "--repo",
                str(repo),
                "--room",
                "20000000-0000-4000-8000-000000000002",
            ],
            capture_output=True,
            text=True,
        )
        check("status refuses a different expected room", wrong_status.returncode != 0 and "different room" in wrong_status.stderr)
        check("state holds no message content", secret not in json.dumps(state))
        time.sleep(0.3)
        log = (checks / "room-meter.log").read_text()
        check("observer log holds metadata but no message content", "snapshot count=2" in log and secret not in log)
        second = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "start",
                "--repo",
                str(repo),
                "--room",
                ROOM,
                "--checks",
                str(checks),
                "--band-bin",
                str(fake),
                "--startup-timeout",
                "1",
            ],
            capture_output=True,
            text=True,
        )
        check("a second start refuses the live observer", second.returncode != 0 and "already live" in second.stderr)
        stop = subprocess.run(
            [sys.executable, str(TOOL), "stop", "--repo", str(repo), "--timeout", "5"],
            capture_output=True,
            text=True,
        )
        check("stop retires the detached observer", stop.returncode == 0 and "STOPPED" in stop.stdout)
        check("stop removes live process metadata", not (repo / ".git" / "factory" / "room-meter.pid.json").exists())
        after = subprocess.run([str(client)], capture_output=True, text=True)
        check("client fails closed after the observer stops", after.returncode != 0 and "metadata is missing" in after.stderr)


integration_checks()
check("default observer lifetime is twelve hours", ROOM_METER.DEFAULT_MAX_SECONDS == 43_200.0)
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
