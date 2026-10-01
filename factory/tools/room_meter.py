#!/usr/bin/env python3
"""Run a pre-dispatch observer that gives agents exact, anchored room counts.

The observer owns BAND's Human API before the dispatch. Agents only read its fresh
state through the client installed under the result repository's .git directory.
No message content is written to disk or printed.
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
import uuid

ROOM_LIMIT = 10_000
DEFAULT_INTERVAL = 15.0
DEFAULT_MAX_AGE = 45.0
DEFAULT_MAX_SECONDS = 43_200.0
DEFAULT_STARTUP_TIMEOUT = 150.0


class MeterError(RuntimeError):
    """A safe error that never carries room message content."""


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(value, sort_keys=True) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def runtime_paths(repo):
    root = pathlib.Path(repo).resolve()
    git_dir = root / ".git"
    if not git_dir.is_dir():
        raise MeterError(f"result repository has no .git directory: {root}")
    runtime = git_dir / "factory"
    return {
        "repo": root,
        "runtime": runtime,
        "meta": runtime / "room-meter.pid.json",
        "state": runtime / "room-meter-state.json",
        "stop": runtime / "room-meter.stop.json",
        "client": runtime / "count",
    }


def load_json(path, label):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise MeterError(f"{label} is missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MeterError(f"{label} is unreadable") from exc


def process_start_token(pid):
    path = pathlib.Path(f"/proc/{pid}/stat")
    try:
        fields = path.read_text().split()
    except OSError:
        return None
    return fields[21] if len(fields) > 21 else None


def process_is_live(meta):
    try:
        pid = int(meta["pid"])
        os.kill(pid, 0)
    except (KeyError, TypeError, ValueError, ProcessLookupError, PermissionError):
        return False
    expected = meta.get("process_start_token")
    observed = process_start_token(pid)
    return expected is None or observed is None or str(expected) == str(observed)


def validate_uuid(value, label):
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MeterError(f"{label} is not a UUID") from exc
    if str(parsed) != str(value).lower():
        raise MeterError(f"{label} is not a canonical UUID")


def validate_page(page, expected_page):
    if not isinstance(page, dict):
        raise MeterError("BAND returned a non-object page")
    try:
        number = int(page["page"])
        limit = int(page["limit"])
        total_pages = int(page["total_pages"])
        messages = page["messages"]
        mutation = page["last_included_mutation_sequence"]
    except (KeyError, TypeError, ValueError) as exc:
        raise MeterError("BAND page metadata is incomplete") from exc
    if number != expected_page or limit <= 0 or total_pages <= 0:
        raise MeterError("BAND page metadata is inconsistent")
    if not isinstance(messages, list) or len(messages) > limit or mutation is None:
        raise MeterError("BAND page contents are inconsistent")
    return limit, total_pages, messages, mutation


def validate_messages(messages, expected_room):
    validated = []
    seen = set()
    for message in messages:
        if not isinstance(message, dict):
            raise MeterError("BAND returned a non-object message")
        message_id = message.get("id")
        validate_uuid(message_id, "message id")
        if message_id in seen:
            raise MeterError("BAND returned duplicate message ids in one page")
        seen.add(message_id)
        if message.get("chat_id") != expected_room:
            raise MeterError("BAND returned a message from another room")
        inserted_at = message.get("inserted_at")
        try:
            parsed = dt.datetime.fromisoformat(str(inserted_at).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise MeterError("BAND returned an invalid message timestamp") from exc
        if parsed.tzinfo is None:
            raise MeterError("BAND returned a message timestamp without a timezone")
        validated.append((parsed, message_id))
    return validated


def collect_snapshot(fetch_page, expected_room, attempts=3):
    """Return one exact snapshot when first and last pages share a mutation."""
    for _ in range(attempts):
        snapshot_started = time.time()
        first = fetch_page(1)
        limit, total_pages, newest, first_mutation = validate_page(first, 1)
        last = first if total_pages == 1 else fetch_page(total_pages)
        last_limit, last_total, oldest, last_mutation = validate_page(last, total_pages)
        stable = (
            limit == last_limit
            and total_pages == last_total
            and first_mutation == last_mutation
        )
        if not stable:
            continue
        if not oldest or (total_pages > 1 and len(newest) != limit):
            raise MeterError("BAND page lengths are inconsistent with pagination")
        newest_messages = validate_messages(newest, expected_room)
        oldest_messages = validate_messages(oldest, expected_room)
        if total_pages > 1 and ({item[1] for item in newest_messages}
                                & {item[1] for item in oldest_messages}):
            raise MeterError("BAND first and last pages overlap")
        count = limit * (total_pages - 1) + len(oldest)
        if count <= 0 or count > ROOM_LIMIT or not newest:
            raise MeterError("BAND room count is outside the supported range")
        latest_time = max(item[0] for item in newest_messages)
        latest = [item for item in newest_messages if item[0] == latest_time]
        if len(latest) != 1:
            raise MeterError("BAND newest page has an ambiguous latest message")
        anchor = latest[0][1]
        return {
            "count": count,
            "anchor_id": anchor,
            "snapshot_started_at_epoch": snapshot_started,
            "mutation_sequence": first_mutation,
            "page_size": limit,
            "total_pages": total_pages,
            "last_page_items": len(oldest),
        }
    raise MeterError("BAND room changed during every snapshot attempt")


def band_fetcher(room_id, band_bin, timeout):
    def fetch(page):
        command = [
            band_bin,
            "room",
            "messages",
            room_id,
            "--page",
            str(page),
            "--json",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MeterError("BAND room query did not complete") from exc
        if result.returncode != 0:
            raise MeterError(f"BAND room query exited {result.returncode}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MeterError("BAND room query returned invalid JSON") from exc

    return fetch


def read_live_meta(repo, expected_room=None):
    paths = runtime_paths(repo)
    meta = load_json(paths["meta"], "room meter metadata")
    if not process_is_live(meta):
        raise MeterError("room meter process is not live")
    validate_uuid(meta.get("room_id"), "room meter room id")
    if expected_room is not None and meta.get("room_id") != expected_room:
        raise MeterError("room meter is attached to a different room")
    return paths, meta


def read_fresh_state(repo, max_age, expected_room=None):
    paths, meta = read_live_meta(repo, expected_room)
    state = load_json(paths["state"], "room meter state")
    if state.get("instance_id") != meta.get("instance_id"):
        raise MeterError("room meter state belongs to another process")
    if state.get("room_id") != meta.get("room_id"):
        raise MeterError("room meter state belongs to another room")
    try:
        snapshot_started = float(state["snapshot_started_at_epoch"])
        observed = float(state["observed_at_epoch"])
        age = time.time() - snapshot_started
        count = int(state["count"])
        expires_at = float(state["expires_at_epoch"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MeterError("room meter state is incomplete") from exc
    if observed < snapshot_started or observed - snapshot_started > max_age:
        raise MeterError("room meter snapshot duration is inconsistent")
    if age < -5 or age > max_age:
        raise MeterError(f"room meter state is stale ({age:.1f} seconds old)")
    if expires_at <= time.time():
        raise MeterError("room meter lifetime has expired")
    if count <= 0 or count > ROOM_LIMIT:
        raise MeterError("room meter count is outside the supported range")
    validate_uuid(state.get("anchor_id"), "room meter anchor")
    return state, max(0.0, age)


def wait_for_next_state(repo, max_age, timeout):
    """Wait a bounded time for an autonomous snapshot newer than this call."""
    _paths, initial_meta = read_live_meta(repo)
    started = time.time()
    checks = max(1, int(timeout / 0.25))
    last_error = None
    for _ in range(checks):
        _paths, current_meta = read_live_meta(repo)
        if current_meta.get("instance_id") != initial_meta.get("instance_id"):
            raise MeterError("room meter process changed during the client wait")
        try:
            state, age = read_fresh_state(repo, max_age)
        except MeterError as exc:
            last_error = exc
        else:
            if (state.get("instance_id") != initial_meta.get("instance_id")
                    or state.get("room_id") != initial_meta.get("room_id")):
                raise MeterError("room meter process changed during the client wait")
            if float(state["snapshot_started_at_epoch"]) > started:
                return state, age
        time.sleep(0.25)
    detail = f": {last_error}" if last_error else ""
    raise MeterError(f"room meter did not publish a new snapshot before timeout{detail}")


def install_client(paths):
    tool = pathlib.Path(__file__).resolve()
    command = " ".join(
        shlex.quote(part)
        for part in (sys.executable, str(tool), "read", "--repo", str(paths["repo"]))
    )
    text = f"#!/bin/sh\nexec {command}\n"
    tmp = paths["client"].with_name(f".{paths['client'].name}.{os.getpid()}.tmp")
    tmp.write_text(text)
    os.chmod(tmp, 0o700)
    os.replace(tmp, paths["client"])


def matching_stop_requested(path, instance_id):
    try:
        request = json.loads(path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    return request.get("instance_id") == instance_id


def wait_with_stop(path, instance_id, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if matching_stop_requested(path, instance_id):
            return True
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    return matching_stop_requested(path, instance_id)


def serve(args):
    validate_uuid(args.room, "room id")
    paths = runtime_paths(args.repo)
    paths["runtime"].mkdir(parents=True, exist_ok=True)
    os.chmod(paths["runtime"], 0o700)
    started_at = time.time()
    expires_at = started_at + args.max_seconds
    meta = {
        "instance_id": args.instance_id,
        "pid": os.getpid(),
        "process_start_token": process_start_token(os.getpid()),
        "room_id": args.room,
        "started_at_epoch": started_at,
        "expires_at_epoch": expires_at,
        "max_seconds": args.max_seconds,
    }
    atomic_json(paths["meta"], meta)
    fetch = band_fetcher(args.room, args.band_bin, args.query_timeout)
    deadline = time.monotonic() + args.max_seconds
    while time.monotonic() < deadline:
        if matching_stop_requested(paths["stop"], args.instance_id):
            break
        try:
            snapshot = collect_snapshot(fetch, args.room)
            now = time.time()
            snapshot.update({
                "schema_version": 1,
                "instance_id": args.instance_id,
                "room_id": args.room,
                "expires_at_epoch": expires_at,
                "observed_at_epoch": now,
                "observed_at": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
            })
            atomic_json(paths["state"], snapshot)
            print(
                f"snapshot count={snapshot['count']} anchor={snapshot['anchor_id']} "
                f"mutation={snapshot['mutation_sequence']}",
                flush=True,
            )
        except MeterError as exc:
            print(f"snapshot error: {exc}", flush=True)
        if wait_with_stop(paths["stop"], args.instance_id, args.interval):
            break
    current = None
    try:
        current = json.loads(paths["meta"].read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    if current and current.get("instance_id") == args.instance_id:
        paths["meta"].unlink(missing_ok=True)
    print("room meter stopped", flush=True)


def start(args):
    validate_uuid(args.room, "room id")
    paths = runtime_paths(args.repo)
    paths["runtime"].mkdir(parents=True, exist_ok=True)
    os.chmod(paths["runtime"], 0o700)
    if paths["meta"].exists():
        old = load_json(paths["meta"], "existing room meter metadata")
        if process_is_live(old):
            raise MeterError("a room meter is already live for this repository")
    for path in (paths["meta"], paths["state"], paths["stop"]):
        path.unlink(missing_ok=True)
    install_client(paths)
    checks = pathlib.Path(args.checks).resolve()
    checks.mkdir(parents=True, exist_ok=True)
    log_path = checks / "room-meter.log"
    instance_id = str(uuid.uuid4())
    command = [
        sys.executable,
        str(pathlib.Path(__file__).resolve()),
        "serve",
        "--repo",
        str(paths["repo"]),
        "--room",
        args.room,
        "--instance-id",
        instance_id,
        "--band-bin",
        args.band_bin,
        "--interval",
        str(args.interval),
        "--max-seconds",
        str(args.max_seconds),
        "--query-timeout",
        str(args.query_timeout),
    ]
    with log_path.open("a") as log:
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    checks_count = max(1, int(args.startup_timeout / 0.25))
    for _ in range(checks_count):
        if child.poll() is not None:
            break
        try:
            state, _ = read_fresh_state(paths["repo"], args.max_age)
        except MeterError:
            time.sleep(0.25)
            continue
        if state.get("instance_id") == instance_id:
            print(
                f"ROOM METER READY room={args.room} count={state['count']} "
                f"anchor={state['anchor_id']} pid={child.pid}"
            )
            return
    if child.poll() is None:
        atomic_json(paths["stop"], {"instance_id": instance_id})
    raise MeterError(f"room meter did not produce a fresh snapshot; inspect {log_path}")


def stop(args):
    paths = runtime_paths(args.repo)
    meta = load_json(paths["meta"], "room meter metadata")
    if not process_is_live(meta):
        raise MeterError("room meter process is not live")
    atomic_json(paths["stop"], {"instance_id": meta["instance_id"]})
    checks_count = max(1, int(args.timeout / 0.25))
    for _ in range(checks_count):
        if not process_is_live(meta):
            paths["meta"].unlink(missing_ok=True)
            paths["stop"].unlink(missing_ok=True)
            print("ROOM METER STOPPED")
            return
        time.sleep(0.25)
    raise MeterError("room meter did not stop before the timeout")


def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    start_parser = sub.add_parser("start")
    start_parser.add_argument("--repo", required=True)
    start_parser.add_argument("--room", required=True)
    start_parser.add_argument("--checks", required=True)
    start_parser.add_argument("--band-bin", default="band")
    start_parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    start_parser.add_argument("--max-age", type=float, default=DEFAULT_MAX_AGE)
    start_parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    start_parser.add_argument("--query-timeout", type=float, default=20.0)
    start_parser.add_argument("--startup-timeout", type=float, default=DEFAULT_STARTUP_TIMEOUT)

    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--repo", required=True)
    serve_parser.add_argument("--room", required=True)
    serve_parser.add_argument("--instance-id", required=True)
    serve_parser.add_argument("--band-bin", default="band")
    serve_parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    serve_parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    serve_parser.add_argument("--query-timeout", type=float, default=20.0)

    for name in ("read", "status"):
        read_parser = sub.add_parser(name)
        read_parser.add_argument("--repo", required=True)
        read_parser.add_argument("--max-age", type=float, default=DEFAULT_MAX_AGE)
        read_parser.add_argument("--room")
        if name == "read":
            read_parser.add_argument("--wait-timeout", type=float, default=DEFAULT_MAX_AGE)
        else:
            read_parser.add_argument("--min-remaining-seconds", type=float, default=0.0)

    stop_parser = sub.add_parser("stop")
    stop_parser.add_argument("--repo", required=True)
    stop_parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.command == "start":
            start(args)
        elif args.command == "serve":
            serve(args)
        elif args.command == "stop":
            stop(args)
        else:
            if args.command == "read":
                state, _age = wait_for_next_state(
                    args.repo, args.max_age, args.wait_timeout
                )
                if args.room is not None and state.get("room_id") != args.room:
                    raise MeterError("room meter is attached to a different room")
                print(
                    f"ROOM COUNT {state['count']} OF 10000 AFTER {state['anchor_id']}"
                )
            else:
                state, age = read_fresh_state(args.repo, args.max_age, args.room)
                remaining = float(state["expires_at_epoch"]) - time.time()
                if remaining < args.min_remaining_seconds:
                    raise MeterError(
                        f"room meter remaining lifetime {remaining:.1f}s is below "
                        f"required {args.min_remaining_seconds:.1f}s"
                    )
                print(
                    f"ROOM METER READY room={state['room_id']} count={state['count']} "
                    f"age={age:.1f}s remaining={remaining:.1f}s pid state matches"
                )
    except MeterError as exc:
        print(f"ROOM METER ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
