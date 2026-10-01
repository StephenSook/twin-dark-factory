#!/usr/bin/env python3
"""Test the generated result README and the package script's stage boundary."""
import hashlib
import json
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGER = ROOT / "factory" / "tools" / "package_result.sh"


def msg(number, kind, sender, content="", sender_type="Agent"):
    return {
        "id": f"{number:08x}-0000-4000-8000-{number:012x}",
        "insertedAt": f"2026-01-01T00:00:{number:02d}.000Z",
        "messageType": kind,
        "senderId": sender,
        "senderType": sender_type,
        "senderName": sender,
        "content": content,
    }


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    repo = tmp / "result"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True)
    mandates = repo / "mandates"
    mandates.mkdir()
    seats = ["coordinator", "modeler", "builder", "surface", "gatekeeper", "auditor"]
    for seat in seats:
        (mandates / f"{seat}.md").write_text(f"Harness: test\nModel: test/{seat}\n")
    for stage in range(1, 5):
        folder = repo / f"stage-{stage}"
        folder.mkdir()
        (folder / "Dockerfile").write_text("FROM scratch\n")
        (folder / "RUN.md").write_text("run\n")
    subprocess.run(["git", "-C", str(repo), "add", "mandates", "stage-1", "stage-2", "stage-3", "stage-4"], check=True)
    subprocess.run([
        "git", "-C", str(repo), "-c", "user.name=Stephen Sookra",
        "-c", "user.email=owner@example.invalid", "commit", "-qm", "fixture",
    ], check=True)
    stage_hashes = {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for stage in range(1, 5)
        for path in (repo / f"stage-{stage}").iterdir()
    }

    messages = [msg(1, "text", "Stephen Sookra", "dispatch", "Human")]
    quotes = [
        ("executable_model", "modeler", "The executable model covered the accepted operations."),
        ("differential_comparison", "gatekeeper", "The differential comparison matched every sampled operation."),
        ("concurrency_probe", "gatekeeper", "The concurrency probe completed with fifty overlapping requests."),
        ("planted_fault", "gatekeeper", "The planted fault was detected before the clean rerun."),
        ("third_family_audit", "auditor", "The independent audit found no behaviour-changing misreading."),
    ]
    claims = []
    number = 2
    for claim_id, sender, quote in quotes:
        item = msg(number, "text", sender, quote)
        messages.append(item)
        claims.append({"id": claim_id, "room_message_id": item["id"], "sender": sender, "quote": quote})
        number += 1
    messages.extend([msg(number, "thought", "builder"), msg(number + 1, "thought", "surface")])
    number += 2
    for stage in range(1, 5):
        messages.append(msg(number, "text", "gatekeeper", f"ACCEPT {stage:07x}"))
        number += 1
        anchor = msg(number, "tool_call", "coordinator")
        messages.append(anchor)
        count = len(messages)
        number += 1
        messages.append(msg(number, "text", "coordinator", f"ROOM COUNT {count} OF 10000 AFTER {anchor['id']}"))
        number += 1
    messages.append(msg(number, "text", "coordinator", "FINAL REPORT\nrun complete"))
    room = {"exportedAt": "2026-01-01T00:01:00.000Z", "room": {"id": "room-test"}, "messages": messages}
    room_path = tmp / "room.json"
    sessions_path = tmp / "sessions.json"
    facts_path = tmp / "facts.json"
    claims_path = tmp / "claims.json"
    room_path.write_text(json.dumps(room))
    sessions_path.write_text(json.dumps({"sessions": [{
        "attribution": {"chatIds": ["room-test"], "peerName": "stephensookra/gatekeeper"},
        "models": [{"model": "gpt-6-astra"}], "inputTokens": 10, "outputTokens": 5,
        "cacheCreationTokens": 0, "cacheReadTokens": 0, "totalCost": 0.25,
    }]}))
    facts_path.write_text(json.dumps({
        "track": "pocketful",
        "one_line": "Six seats built and checked the judged result from one dispatch.",
        "room_sha256": hashlib.sha256(room_path.read_bytes()).hexdigest(),
        "stage_claims": {str(stage): "PASS" for stage in range(1, 5)},
        "holdout_score": "73/73", "holdout_digest": "a" * 64,
        "holdout_headline": "The sealed holdout passed.",
        "genericity": "Second-track run measured separately.",
        "baseline": "Solo run measured separately.",
        "featherless_note": "The inference key cannot read the provider billing meter.",
        "check_commands": ["python3 tools/check_room.py room.json"],
        "limits": ["Provider billing telemetry is unavailable to the inference key."],
    }))
    claims_path.write_text(json.dumps({"claims": claims}))

    result = subprocess.run(
        ["bash", str(PACKAGER), str(repo), str(room_path), str(sessions_path), str(facts_path), str(claims_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(1)
    after = {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for stage in range(1, 5)
        for path in (repo / f"stage-{stage}").iterdir()
    }
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    readme = (repo / "README.md").read_text()
    good = (
        stage_hashes == after
        and not any(path.startswith("stage-") for path in staged)
        and "Stages reached: 4 of 4" in readme
        and "Human messages after dispatch: 0" in readme
        and (repo / "evidence" / "claim-evidence.json").is_file()
        and (repo / ".github" / "workflows" / "verify.yml").is_file()
        and "PASS  packaged measured result evidence" in result.stdout
    )
    if not good:
        print(result.stdout)
        print(result.stderr)
        print(staged)
        raise SystemExit(1)

print("ok   generic result packaging preserves every stage byte and stages only evidence paths")
