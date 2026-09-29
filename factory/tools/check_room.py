"""Check that room.json is a complete, unedited BAND export of an unattended run.

  python check_room.py room.json [--allow-human-after-dispatch]

Checks, each printed as PASS or FAIL, exit 1 on any failure:
  - the export has BAND's own top-level keys and per-message fields (a hand-written log does not);
  - every message id is a UUID and ids are unique;
  - messages are in time order with no duplicates;
  - the first text message is the human's dispatch (a truncated export starts mid-run);
  - no human text message follows the dispatch (the run was hands off);
  - prints the file's sha256 and message counts for FACTORY.md.
"""
import collections
import hashlib
import json
import pathlib
import re
import sys

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TOP_KEYS = {"exportedAt", "room", "messages"}
MSG_KEYS = {"id", "insertedAt", "messageType", "senderId", "senderType"}


def main():
    path = pathlib.Path(sys.argv[1])
    allow_human = "--allow-human-after-dispatch" in sys.argv[2:]
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    msgs = raw.get("messages") or []
    failures = []

    def check(ok, label):
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok:
            failures.append(label)

    check(TOP_KEYS <= set(raw), f"export has BAND top-level keys {sorted(TOP_KEYS)}")
    check(bool(msgs), f"export holds messages ({len(msgs)})")
    missing = [m.get("id") for m in msgs if not MSG_KEYS <= set(m)]
    check(not missing, f"every message has {sorted(MSG_KEYS)} ({len(missing)} missing)")
    ids = [m.get("id", "") for m in msgs]
    check(all(UUID.match(i or "") for i in ids), "every message id is a UUID")
    check(len(set(ids)) == len(ids), "message ids are unique")
    times = [m.get("insertedAt", "") for m in msgs]
    check(times == sorted(times), "messages are in time order")

    texts = [m for m in msgs if m.get("messageType") == "text"]
    first = texts[0] if texts else None
    check(first is not None and first.get("senderType") != "Agent",
          "first text message is the human dispatch (export not truncated)")
    humans_after = [m for m in texts[1:] if m.get("senderType") != "Agent"]
    label = f"human text messages after the dispatch: {len(humans_after)}"
    if allow_human:
        print("NOTE  " + label + " (allowed for a development run)")
    else:
        check(not humans_after, label)

    kinds = collections.Counter(m.get("messageType") for m in msgs)
    print(f"INFO  sha256 {hashlib.sha256(raw_bytes).hexdigest()}")
    print(f"INFO  messages {len(msgs)}, by type {dict(sorted(kinds.items()))}")
    if msgs:
        print(f"INFO  span {times[0]} to {times[-1]}")
    if texts:
        last = texts[-1]
        print(f"INFO  last text message from {last.get('senderName') or last.get('senderId')} at "
              f"{last.get('insertedAt')}: confirm it is the final report (an export cut off at the end "
              "starts correctly but stops early)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
