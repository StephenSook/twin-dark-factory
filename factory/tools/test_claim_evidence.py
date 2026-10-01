#!/usr/bin/env python3
"""Regression tests for the public-claim evidence checker."""
import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECKER = ROOT / "factory" / "tools" / "check_claim_evidence.py"
SPECS = [
    ("executable_model", "modeler", "The executable model covered the accepted operations."),
    ("differential_comparison", "gatekeeper", "The differential comparison matched every sampled operation."),
    ("concurrency_probe", "gatekeeper", "The concurrency probe completed with fifty overlapping requests."),
    ("planted_fault", "gatekeeper", "The planted fault was detected before the clean rerun."),
    ("third_family_audit", "auditor", "The independent audit found no behaviour-changing misreading."),
]


def fixture():
    messages = []
    claims = []
    for number, (claim_id, sender, quote) in enumerate(SPECS, start=1):
        message_id = f"{number:08x}-0000-4000-8000-{number:012x}"
        messages.append({
            "id": message_id,
            "messageType": "text",
            "senderType": "Agent",
            "senderName": sender,
            "content": quote,
        })
        claims.append({
            "id": claim_id,
            "room_message_id": message_id,
            "sender": sender,
            "quote": quote,
        })
    return {"messages": messages}, {"claims": claims}


def run(label, mutate, want):
    room, evidence = fixture()
    mutate(room, evidence)
    with tempfile.TemporaryDirectory() as tmp:
        room_path = pathlib.Path(tmp) / "room.json"
        evidence_path = pathlib.Path(tmp) / "claim-evidence.json"
        room_path.write_text(json.dumps(room))
        evidence_path.write_text(json.dumps(evidence))
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(room_path), str(evidence_path)],
            capture_output=True,
            text=True,
        )
    got = result.returncode == 0
    if got == want:
        print(f"ok   {label}")
    else:
        print(f"BAD  {label}")
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(1)


run("five distinct verbatim citations pass", lambda _r, _e: None, True)
run("a missing central claim fails", lambda _r, e: e["claims"].pop(), False)
run("a composed quote fails", lambda _r, e: e["claims"][0].update(quote="A sentence not in the room message."), False)
run("the third-family claim must cite the auditor", lambda _r, e: e["claims"][-1].update(sender="gatekeeper"), False)
run("one message cannot stand in for two claims", lambda _r, e: e["claims"][1].update(
    room_message_id=e["claims"][0]["room_message_id"],
    sender=e["claims"][0]["sender"],
    quote=e["claims"][0]["quote"],
), False)
