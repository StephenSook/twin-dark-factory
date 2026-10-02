"""Regression checks for the room-cap gate and FACTORY.md room provenance."""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECK_ROOM = ROOT / "factory" / "tools" / "check_room.py"
FLOOR_DATA = ROOT / "factory" / "tools" / "floor_data.py"
FACTORY_MD = ROOT / "factory" / "tools" / "factory_md.py"
JUDGE_GUIDE = ROOT / "factory" / "tools" / "judge_guide.py"
DECK = ROOT / "factory" / "deck" / "build_deck.py"
FACTORY_TEMPLATE = ROOT / "factory" / "docs" / "FACTORY.template.md"
FLOOR_INDEX = ROOT / "factory" / "floor" / "index.html"
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


def run_room(label, room, want, allow_development=False, expected=None,
             expected_accepts=1, add_final=True, expected_seats=None):
    if not allow_development and add_final:
        room["messages"].append(message(
            0x7FFFFFFF,
            "text",
            sender="coordinator",
            content="FINAL REPORT\nrun complete",
        ))
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "room.json"
        path.write_text(json.dumps(room))
        if expected_seats is not None:
            mandates = pathlib.Path(tmp) / "mandates"
            mandates.mkdir()
            for seat in expected_seats:
                (mandates / f"{seat}.md").write_text(f"# {seat}\n")
        command = [
            sys.executable,
            str(CHECK_ROOM),
            str(path),
            "--expected-accepts",
            str(expected_accepts),
        ]
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
        "rejections": [],
        "commits": [],
        "totals": {
            "human_messages_after_dispatch": 0,
            "rejects": 0,
            "accepts": 0,
            "handoffs": 0,
            "rejects_followed_by_seat_commit": 0,
            "rejects_resolved_by_accepted_revision": 0,
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

        facts_path.write_text(json.dumps({
            "track": "toy",
            "development_run": True,
            "room_sha256": room_hash,
            "holdout_note": "Pocketful-only private attacks do not apply to the Toy track.",
            "cost_note": "Development usage note.",
        }))
        result = subprocess.run(command, capture_output=True, text=True)
        good = (
            result.returncode == 0
            and "Private attack suite" in result.stdout
            and "Pocketful-only private attacks do not apply" in result.stdout
            and "Development usage note" in result.stdout
            and "Development autonomy" in result.stdout
            and "Hands off" not in result.stdout
            and "Evidence the band never saw" not in result.stdout
            and "Sealed holdout digest" not in result.stdout
        )
        if good:
            print("ok   FACTORY.md records a track-scoped holdout exemption")
        else:
            failures.append("FACTORY.md track-scoped holdout")
            print("BAD  FACTORY.md misstated an inapplicable holdout")
            print(result.stdout)
            print(result.stderr)

        strict_facts = {
            "track": "toy",
            "development_run": True,
            "stage_claims": {"1": "claims its stage"},
            "holdout_note": "Pocketful-only private attacks do not apply to the Toy track.",
            "genericity": "Not run in this development test.",
            "baseline": "Not run in this development test.",
            "check_commands": ["python -m harness run --track toy --repo . --all --mode isolated"],
            "limits": ["Development run."],
            "cost_note": "Development usage note.",
            "room_sha256": room_hash,
        }
        facts_path.write_text(json.dumps(strict_facts))
        strict_command = command[:-1]
        result = subprocess.run(strict_command, capture_output=True, text=True)
        if result.returncode != 0 and "no usage sessions are attributed" in result.stderr:
            print("ok   FACTORY.md refuses an empty usage export outside draft mode")
        else:
            failures.append("FACTORY.md empty usage export")
            print("BAD  FACTORY.md accepted an empty measured usage export")
            print(result.stdout)
            print(result.stderr)

        sessions_path.write_text(json.dumps({"sessions": [{
            "attribution": {"chatIds": ["room-test"], "peerName": "stephensookra/coordinator-cx"},
            "models": [{"model": "gpt-6-astra"}],
            "inputTokens": 10,
            "outputTokens": 5,
            "cacheCreationTokens": 0,
            "cacheReadTokens": 20,
            "totalCost": 0.25,
        }]}))
        result = subprocess.run(strict_command, capture_output=True, text=True)
        if result.returncode == 0 and "| **total** | | 35 | 0.25 |" in result.stdout:
            print("ok   FACTORY.md accepts attributed development usage")
        else:
            failures.append("FACTORY.md attributed usage")
            print("BAD  FACTORY.md refused attributed development usage")
            print(result.stdout)
            print(result.stderr)

        strict_facts["holdout_applicable"] = True
        strict_facts["holdout_score"] = "73/73"
        strict_facts["holdout_digest"] = "a" * 64
        facts_path.write_text(json.dumps(strict_facts))
        result = subprocess.run(strict_command, capture_output=True, text=True)
        if result.returncode != 0 and "holdout_applicable must agree with the run track" in result.stderr:
            print("ok   FACTORY.md refuses a cross-track holdout claim")
        else:
            failures.append("FACTORY.md cross-track holdout")
            print("BAD  FACTORY.md accepted a cross-track holdout claim")

        pocketful_facts = dict(strict_facts)
        pocketful_facts["track"] = "pocketful"
        pocketful_facts.pop("holdout_applicable")
        facts_path.write_text(json.dumps(pocketful_facts))
        result = subprocess.run(strict_command, capture_output=True, text=True)
        if result.returncode == 0 and "Sealed holdout digest `aaaaaaaaaaaaaaaa`" in result.stdout:
            print("ok   FACTORY.md accepts complete Pocketful holdout evidence")
        else:
            failures.append("FACTORY.md complete holdout")
            print("BAD  FACTORY.md refused complete Pocketful holdout evidence")
            print(result.stdout)
            print(result.stderr)

        for label, update, expected_error in (
            ("short digest", {"holdout_digest": "abc"}, "holdout_digest must be 64"),
            ("boolean digest", {"holdout_digest": True}, "holdout_digest must be 64"),
            ("boolean score", {"holdout_score": True}, "holdout_score must use"),
            ("score above total", {"holdout_score": "74/73"}, "passed <= total"),
            ("zero score total", {"holdout_score": "0/0"}, "total > 0"),
            ("false applicability", {"holdout_applicable": False}, "must agree with the run track"),
            ("null applicability", {"holdout_applicable": None}, "must be boolean"),
        ):
            bad = dict(pocketful_facts)
            bad.update(update)
            facts_path.write_text(json.dumps(bad))
            result = subprocess.run(strict_command, capture_output=True, text=True)
            if result.returncode != 0 and expected_error in result.stderr:
                print(f"ok   FACTORY.md refuses {label}")
            else:
                failures.append(f"FACTORY.md {label}")
                print(f"BAD  FACTORY.md accepted {label}")


def run_judge_guide_checks():
    floor = {
        "events": [
            {"from": "gatekeeper", "human": False, "t": 1, "id": "reject-id",
             "preview": "REJECT ccccccc failing burst", "verdicts": [{"verdict": "REJECT", "rev": "ccccccc"}]},
            {"from": "gatekeeper", "human": False, "t": 2, "id": "accept-id",
             "preview": "ACCEPT ddddddd", "verdicts": [{"verdict": "ACCEPT", "rev": "ddddddd"}]},
            {"from": "coordinator-cx", "human": False, "t": 3, "id": "final-id",
             "preview": "FINAL REPORT", "verdicts": []},
            {"from": "auditor", "human": False, "t": 4, "id": "audit-id",
             "preview": "Quoted FINAL REPORT concern", "verdicts": []},
        ],
        "commits": [
            {"by_seat": True, "t": 1.5, "author": "gatekeeper", "sha": "c" * 40,
             "subject": "candidate with failing burst", "stages": [1]},
            {"by_seat": True, "t": 2.0, "author": "builder", "sha": "b" * 40,
             "subject": "unrelated stage work", "stages": [2]},
            {"by_seat": True, "t": 0.5, "author": "builder", "sha": "f" * 40,
             "subject": "fix burst", "stages": [1]},
        ],
        "rejections": [{
            "rev": "ccccccc", "t": 1, "message_id": "reject-id", "stages": [1],
            "followup": {"sha": "f" * 40, "t": 1.5, "author": "builder", "subject": "fix burst"},
            "resolved_by": {"rev": "ddddddd", "t": 2, "message_id": "accept-id"},
        }],
        "totals": {"rejects": 1, "rejects_followed_by_seat_commit": 1,
                   "rejects_resolved_by_accepted_revision": 1,
                   "human_messages_after_dispatch": 3},
    }
    facts = {
        "track": "toy",
        "holdout_note": "Pocketful-only private attacks do not apply to the Toy track.",
        "coordinator_handle": "coordinator-cx",
        "one_line": "Twin development run: six agents, two model families.",
        "room_sha256": "abc123",
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        floor_path = tmp / "floor.json"
        facts_path = tmp / "facts.json"
        floor_path.write_text(json.dumps(floor))
        facts_path.write_text(json.dumps(facts))
        result = subprocess.run(
            [sys.executable, str(JUDGE_GUIDE), str(floor_path), str(facts_path)],
            capture_output=True,
            text=True,
        )
    good = (
        result.returncode == 0
        and "--track toy" in result.stdout
        and "--track pocketful" not in result.stdout
        and "Development autonomy" in result.stdout
        and "human recovery messages" in result.stdout
        and "Pocketful-only private attacks do not apply" in result.stdout
        and "Evidence the band never saw" not in result.stdout
        and "final-id" in result.stdout
        and "audit-id" not in result.stdout
        and "fix burst" in result.stdout
        and "unrelated stage work" not in result.stdout
    )
    if good:
        print("ok   judge guide reports the run's track and development limits")
    else:
        failures.append("judge guide track scope")
        print("BAD  judge guide misstated the run scope")
        print(result.stdout)
        print(result.stderr)

    no_fix_floor = json.loads(json.dumps(floor))
    no_fix_floor["commits"] = no_fix_floor["commits"][:2]
    no_fix_floor["totals"]["rejects_followed_by_seat_commit"] = 0
    no_fix_floor["totals"]["rejects_resolved_by_accepted_revision"] = 0
    no_fix_floor["rejections"][0].update(followup=None, resolved_by=None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        floor_path = tmp / "floor.json"
        facts_path = tmp / "facts.json"
        floor_path.write_text(json.dumps(no_fix_floor))
        facts_path.write_text(json.dumps(facts))
        no_fix_result = subprocess.run(
            [sys.executable, str(JUDGE_GUIDE), str(floor_path), str(facts_path)],
            capture_output=True,
            text=True,
        )
    if (
        no_fix_result.returncode == 0
        and "0 had a same-stage writer commit after the REJECT itself" in no_fix_result.stdout
        and "every one ended" not in no_fix_result.stdout
        and "unrelated stage work" not in no_fix_result.stdout
    ):
        print("ok   judge guide refuses to label unrelated stage work as a fix")
    else:
        failures.append("judge guide unrelated follow-up")
        print("BAD  judge guide mislabeled unrelated stage work as a fix")
        print(no_fix_result.stdout)
        print(no_fix_result.stderr)

    spec = importlib.util.spec_from_file_location("factory_build_deck_test", DECK)
    deck = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deck)
    report_spec = importlib.util.spec_from_file_location("factory_md_test", FACTORY_MD)
    report = importlib.util.module_from_spec(report_spec)
    report_spec.loader.exec_module(report)
    with tempfile.TemporaryDirectory() as cost_tmp:
        cost_sessions = pathlib.Path(cost_tmp) / "sessions.json"
        cost_sessions.write_text(json.dumps({"sessions": [{
            "attribution": {"chatIds": ["room-test"], "peerName": "stephensookra/gatekeeper"},
            "models": [{"model": "gpt-6-astra"}],
            "inputTokens": 10,
            "outputTokens": 5,
            "totalCost": 0.25,
        }]}))
        honest_cost = report.costs(
            cost_sessions,
            "room-test",
            {"featherless_note": "The inference key cannot read the provider billing meter."},
            False,
            False,
        )
    fixed_slide = deck.caught_slide(floor)
    no_fix_slide = deck.caught_slide(no_fix_floor)
    surface_floor = json.loads(json.dumps(floor))
    surface_floor["commits"][-1]["author"] = "surface"
    surface_floor["rejections"][0]["followup"]["author"] = "surface"
    surface_slide = deck.caught_slide(surface_floor)
    fixed_claims = deck.rejection_claims(floor["totals"])
    no_fix_claims = deck.rejection_claims(no_fix_floor["totals"])
    usage_claim = deck.usage_claim(1_500_000, 12.25)
    development_title = deck.title_claim(facts, floor["totals"])
    judged_totals = dict(floor["totals"])
    judged_totals["human_messages_after_dispatch"] = 0
    zero_message_development = deck.title_claim({**facts, "development_run": True}, judged_totals)
    judged_title = deck.title_claim({**facts, "development_run": False}, judged_totals)
    temporary_grid = deck.seat_grid([
        ("builder-cx", 1.0, 10, {"gpt-6-astra"}),
        ("gatekeeper", 1.0, 10, {"gpt-6-astra"}),
    ])
    original_art_dir = deck.ART["dir"]
    with tempfile.TemporaryDirectory() as app_tmp:
        app_dir = pathlib.Path(app_tmp)
        (app_dir / "app-live.png").write_bytes(b"screenshot")
        deck.ART["dir"] = app_dir
        app_slide = deck.optional_app_slide({
            "app_headline": "The accepted final stage runs in a browser.",
            "app_caption": "Captured from the deployed judged service.",
        })
    deck.ART["dir"] = original_art_dir
    fixed_report = report.first_catch(floor)
    no_fix_report = report.first_catch(no_fix_floor)
    if (
        "fix burst" in fixed_slide
        and "unrelated stage work" not in fixed_slide
        and "builder changed the same stage" in fixed_slide
        and "fixed it" not in fixed_slide
        and "changed the same stage" not in no_fix_slide
        and "unrelated stage work" not in no_fix_slide
        and "surface changed the same stage" in surface_slide
        and "builder changed the same stage" not in surface_slide
        and fixed_claims[0] == 1
        and fixed_claims[2] == ("Every rejection ended in a newer revision the gatekeeper accepted; "
                                "1 of 1 had a writer commit after the REJECT.")
        and no_fix_claims[0] == 0
        and no_fix_claims[2] == ("0 of 1 rejections ended in a newer revision the gatekeeper accepted; "
                                 "0 had a writer commit after the REJECT.")
        and "under a minute later" in fixed_slide
        and "0m later" not in fixed_slide
        and "<b>auditor</b><span>DeepSeek</span>" in deck.seat_grid([], {"auditor": "DeepSeek"})

        and usage_claim == "BAND attributes 2M tokens and about $12 of list-price equivalent to the Claude and Codex seats."
        and "whole run" not in usage_claim.lower()
        and "outside Band's export" in honest_cost
        and "cannot read the provider billing meter" in honest_cost
        and "metered:" not in honest_cost
        and "3 human recovery messages" in development_title
        and "no later human input" not in development_title
        and "This development run" in zero_message_development
        and "The judged run" not in zero_message_development
        and "no later human input" in judged_title
        and "The judged run" in judged_title
        and "<b>builder-cx</b><span>Codex</span>" in temporary_grid
        and "<b>builder</b>" not in temporary_grid
        and "<b>auditor</b><span>not in BAND usage</span>" in temporary_grid
        and "The accepted final stage runs in a browser." in app_slide
        and "Captured from the deployed judged service." in app_slide
        and 'src="art/app-live.png"' in app_slide
        and "fix burst" in fixed_report
        and "unrelated stage work" not in fixed_report
        and "fixed it" not in no_fix_report
        and "fixed it" not in fixed_report
    ):
        print("ok   reports bind a fix to the rejected stage and ancestry")
    else:
        failures.append("report rejection follow-up")
        print("BAD  a report mislabeled a rejection follow-up")

    facts["holdout_applicable"] = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        floor_path = tmp / "floor.json"
        facts_path = tmp / "facts.json"
        floor_path.write_text(json.dumps(floor))
        facts_path.write_text(json.dumps(facts))
        result = subprocess.run(
            [sys.executable, str(JUDGE_GUIDE), str(floor_path), str(facts_path)],
            capture_output=True,
            text=True,
        )
    if result.returncode != 0 and "holdout_applicable must agree with the run track" in result.stderr:
        print("ok   judge guide refuses a cross-track holdout claim")
    else:
        failures.append("judge guide cross-track holdout")
        print("BAD  judge guide accepted a cross-track holdout claim")

    pocketful_facts = dict(facts)
    pocketful_facts["track"] = "pocketful"
    pocketful_facts.pop("holdout_applicable")
    pocketful_facts["holdout_digest"] = "a" * 64
    pocketful_facts["holdout_score"] = "73/73"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        floor_path = tmp / "floor.json"
        facts_path = tmp / "facts.json"
        floor_path.write_text(json.dumps(floor))
        facts_path.write_text(json.dumps(pocketful_facts))
        result = subprocess.run(
            [sys.executable, str(JUDGE_GUIDE), str(floor_path), str(facts_path)],
            capture_output=True,
            text=True,
        )
    if result.returncode == 0 and "`aaaaaaaaaaaaaaaa`" in result.stdout:
        print("ok   judge guide accepts complete Pocketful holdout evidence")
    else:
        failures.append("judge guide complete holdout")
        print("BAD  judge guide refused complete Pocketful holdout evidence")

    for label, update, expected_error in (
        ("missing digest", {"holdout_digest": None}, "holdout_digest must be 64"),
        ("boolean digest", {"holdout_digest": True}, "holdout_digest must be 64"),
        ("score above total", {"holdout_score": "74/73"}, "passed <= total"),
        ("zero score total", {"holdout_score": "0/0"}, "total > 0"),
        ("false applicability", {"holdout_applicable": False}, "must agree with the run track"),
        ("null applicability", {"holdout_applicable": None}, "must be boolean"),
    ):
        bad = dict(pocketful_facts)
        bad.update(update)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            floor_path = tmp / "floor.json"
            facts_path = tmp / "facts.json"
            floor_path.write_text(json.dumps(floor))
            facts_path.write_text(json.dumps(bad))
            result = subprocess.run(
                [sys.executable, str(JUDGE_GUIDE), str(floor_path), str(facts_path)],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0 and expected_error in result.stderr:
            print(f"ok   judge guide refuses {label}")
        else:
            failures.append(f"judge guide {label}")
            print(f"BAD  judge guide accepted {label}")


def room_gate_accepts(content):
    """The ACCEPT revisions check_room.py reads from one gatekeeper message."""
    spec = importlib.util.spec_from_file_location("check_room_rule", FLOOR_DATA.with_name("check_room.py"))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    head = gate.ACCEPT.match(gate.LEAD.sub("", content, count=1))
    return [head["r1"] or head["r2"]] if head else []


def run_rejection_timing_checks():
    """A writer commit made before a REJECT is not its follow-up; the later accepted revision still resolves it."""
    spec = importlib.util.spec_from_file_location("floor_data_timing", FLOOR_DATA)
    tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools)
    commits = [
        {"sha": "c" * 40, "t": 100.0, "author": "builder", "subject": "candidate", "stages": [1], "by_seat": True},
        {"sha": "a" * 40, "t": 200.0, "author": "builder", "subject": "pushed before the verdict", "stages": [1], "by_seat": True},
    ]
    early = tools.rejection_record(commits, [(400.0, "aaaaaaa", "accept-id")], 300.0, "ccccccc", "reject-id")
    late_commits = commits + [{"sha": "b" * 40, "t": 330.0, "author": "surface", "subject": "after the verdict",
                               "stages": [1], "by_seat": True}]
    late = tools.rejection_record(late_commits, [(400.0, "bbbbbbb", "accept-id")], 300.0, "ccccccc", "reject-id")
    log_order = tools.rejection_record(
        [commits[0], dict(commits[1], sha="c2" * 20, t=330.0), dict(commits[1], sha="b2" * 20, t=310.0)],
        [], 300.0, "ccccccc", "reject-id")
    partial = tools.rejection_record(
        [dict(commits[0], stages=[1, 2]), dict(commits[1], t=320.0)],
        [(400.0, "aaaaaaa", "accept-id")], 300.0, "ccccccc", "reject-id")
    cumulative = tools.rejection_record(
        [dict(commits[0], stages=[1, 2]), dict(commits[1], sha="1" * 40, t=310.0, stages=[1]),
         dict(commits[1], sha="2" * 40, t=320.0, stages=[2])],
        [(400.0, "2222222", "accept-id")], 300.0, "ccccccc", "reject-id")
    unclamped = tools.rejection_record(
        [commits[0], dict(commits[1], t=600.0, t_exact=3600.0)], [], 300.0, "ccccccc", "reject-id")
    gatekeeper_accept = tools.rejection_record(
        [commits[0], dict(commits[1], t=310.0),
         dict(commits[1], sha="3" * 40, t=320.0, author="gatekeeper")],
        [(400.0, "3333333", "accept-id")], 300.0, "ccccccc", "reject-id")
    one_second_before = tools.rejection_record(
        [commits[0], dict(commits[1], t=299.0)], [], 300.0, "ccccccc", "reject-id")
    off_stage_accept = tools.rejection_record(
        [commits[0], dict(commits[1], sha="1" * 40, t=310.0, stages=[1]),
         dict(commits[1], sha="2" * 40, t=320.0, stages=[2])],
        [(400.0, "2222222", "accept-id")], 300.0, "ccccccc", "reject-id")
    missing_followed = {"rejections": [], "totals": {"rejects": 0, "rejects_resolved_by_accepted_revision": 0}}
    readme_spec = importlib.util.spec_from_file_location("result_readme_guard", FLOOR_DATA.with_name("result_readme.py"))
    readme = importlib.util.module_from_spec(readme_spec)
    readme_spec.loader.exec_module(readme)
    try:
        readme.build(missing_followed, {"stage_claims": {}})
        readme_refused = False
    except SystemExit as error:
        readme_refused = "predates rejection records" in str(error)
    try:
        tools.featured_rejection(missing_followed, {})
        partial_floor_refused = False
    except SystemExit as error:
        partial_floor_refused = "predates rejection records" in str(error)
    try:
        tools.featured_rejection({"totals": {"rejects": 0}}, {})
        old_floor_refused = False
    except SystemExit as error:
        old_floor_refused = "predates rejection records" in str(error)
    branchy = [dict(commits[0], stages=[1, 2]), dict(commits[1], sha="5" * 40, t=310.0, stages=[2]),
               dict(commits[1], sha="6" * 40, t=320.0, stages=[1])]
    sibling_ignored = tools.rejection_record(
        branchy, [(400.0, "6666666", "accept-id")], 300.0, "ccccccc", "reject-id",
        between=lambda rejected, accepted: [branchy[2]])
    linear_counted = tools.rejection_record(
        branchy, [(400.0, "6666666", "accept-id")], 300.0, "ccccccc", "reject-id")
    same_second_start = tools.rejection_record(
        [commits[0], dict(commits[1], t=300.0)], [], 300.0, "ccccccc", "reject-id")
    inside_reject_second = tools.rejection_record(
        [commits[0], dict(commits[1], t=300.0)], [], 300.7, "ccccccc", "reject-id")
    same_second = tools.rejection_record(
        [commits[0], dict(commits[1], t=299.5)], [], 300.0, "ccccccc", "reject-id")
    good = (
        early["followup"] is None
        and early["resolved_by"] == {"rev": "aaaaaaa", "t": 400.0, "message_id": "accept-id"}
        and late["followup"]["sha"] == "b" * 40
        and late["resolved_by"]["rev"] == "bbbbbbb"
        and same_second["followup"] is None
        and (same_second_start["followup"] or {}).get("sha") == "a" * 40
        and inside_reject_second["followup"] is None
        and sibling_ignored["resolved_by"] is None
        and early["fixed_before_reject"] is True
        and late["fixed_before_reject"] is False
        and tools.message_verdicts("gatekeeper", "text", "ACCEPT aaaaaaa\n\n> REJECT ccccccc old") == [
            {"verdict": "ACCEPT", "rev": "aaaaaaa"}]
        and tools.message_verdicts("gatekeeper", "text", "Prior verdict follows:\nREJECT ccccccc stale") == []
        and tools.message_verdicts("gatekeeper", "text", "```\nREJECT ccccccc\n```") == []
        and tools.message_verdicts("gatekeeper", "text", "> REJECT ccccccc quoted") == []
        and tools.message_verdicts("gatekeeper", "error", "REJECT deadbee transport failed") == []
        and tools.message_verdicts("builder", "text", "REJECT ccccccc relayed") == []
        and tools.message_verdicts("gatekeeper", "text", "---\nREJECT ccccccc stale") == []
        and tools.message_verdicts("gatekeeper", "text", "@[[" + "a" * 8 + "-0000-4000-8000-" + "a" * 12 + "]] **REJECT ccccccc** fresh") == [
            {"verdict": "REJECT", "rev": "ccccccc"}]
        and room_gate_accepts("Prior verdict follows:\nACCEPT abcdef1") == []
        and room_gate_accepts("ACCEPT\nabcdef1 is a second-line hash") == []
        and room_gate_accepts("ACCEPTabcdef1 glued") == []
        and room_gate_accepts("ACCEPT abcdef1garbage") == []
        and room_gate_accepts("ACCEPT `abcdef1`garbage") == []
        and room_gate_accepts("ACCEPT `abcdef1` stage 2") == ["abcdef1"]
        and tools.message_verdicts("gatekeeper", "text", "REJECT `ccccccc`garbage") == []
        and tools.message_verdicts("gatekeeper", "text", "REJECT `ccccccc reason") == []
        and room_gate_accepts("ACCEPT `abcdef1 stage 2") == []
        and tools.message_verdicts("gatekeeper", "text", "REJECT `ccccccc`\u00e9chec") == []
        and tools.message_verdicts("gatekeeper", "text", "`REJECT` `ccccccc`: reason") == [
            {"verdict": "REJECT", "rev": "ccccccc"}]
        and tools.message_verdicts("gatekeeper", "text", "REJECTccccccc glued") == []
        and tools.message_verdicts("gatekeeper", "text", "REJECT ccccccczz trailing") == []
        and tools.message_verdicts("gatekeeper", "text", "REJECT `ccccccc`: reason") == [
            {"verdict": "REJECT", "rev": "ccccccc"}]
        and tools.message_verdicts("gatekeeper", "text", "REJECT\nccccccc second line") == []
        and room_gate_accepts("@[[" + "a" * 8 + "-0000-4000-8000-" + "a" * 12 + "]] ACCEPT abcdef1 stage 1") == ["abcdef1"]
        and (linear_counted["resolved_by"] or {}).get("rev") == "6666666"
        and log_order["followup"]["sha"] == "b2" * 20
        and partial["resolved_by"] is None
        and old_floor_refused
        and partial_floor_refused
        and off_stage_accept["resolved_by"] is None
        and gatekeeper_accept["resolved_by"] is None
        and one_second_before["followup"] is None
        and readme_refused
        and (cumulative["resolved_by"] or {}).get("rev") == "2222222"
        and unclamped["followup"]["t"] == 3600.0
        and tools.gap_phrase(0) == "under a minute"
        and tools.gap_phrase(61) == "1 minute"
        and tools.rejection_quote("@a @b REJECT abc1234: expected x. Then more.") == "expected x."
    )
    if good:
        print("ok   rejection follow-ups are ordered by time, and resolution by a later accept")
    else:
        failures.append("rejection timing")
        print("BAD  rejection follow-up timing", early, late, same_second)


def run_saved_log_ancestry_check():
    """A saved log has no ancestry, so a sibling commit before the accepted one cannot cover a stage."""
    room = export([
        message(1, "text", "Human", "human", "dispatch"),
        message(2, "text", sender="stephensookra/gatekeeper", content="REJECT " + "1" * 7 + " two stages"),
        message(3, "text", sender="stephensookra/gatekeeper", content="ACCEPT " + "3" * 7 + " stage one"),
    ])
    for index, item in enumerate(room["messages"]):
        item["insertedAt"] = f"2026-01-01T00:00:0{index * 2}.000Z"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        room_path, log_path, out = tmp / "room.json", tmp / "commits.log", tmp / "floor.json"
        room_path.write_text(json.dumps(room))
        log_path.write_text(
            f"{'e' * 40}\x1fStephen Sookra\x1f2026-01-01T00:00:00+00:00\x1fsetup\nmandates/builder.md\n"
            f"{'1' * 40}\x1fbuilder\x1f2026-01-01T00:00:00+00:00\x1frejected\nstage-1/a.py\nstage-2/a.py\n"
            f"{'2' * 40}\x1fbuilder\x1f2026-01-01T00:00:03+00:00\x1fsibling stage 2\nstage-2/a.py\n"
            f"{'3' * 40}\x1fbuilder\x1f2026-01-01T00:00:03+00:00\x1faccepted stage 1\nstage-1/a.py\n")
        result = subprocess.run([sys.executable, str(FLOOR_DATA), str(room_path), str(log_path), str(out)],
                                capture_output=True, text=True)
        floor = json.loads(out.read_text()) if out.exists() else {}
    record = (floor.get("rejections") or [{}])[0]
    if result.returncode == 0 and record.get("rev") == "1" * 7 and record.get("resolved_by") is None:
        print("ok   a saved log cannot credit a sibling commit to the accepted revision")
    else:
        failures.append("saved log ancestry")
        print("BAD  saved log credited an unproven commit", result.stderr[-300:], record)


def run_floor_verdict_checks():
    room = export([
        message(1, "text", "Human", "human", "dispatch"),
        message(2, "text", sender="modeler", content="ACCEPT aaaaaaa model coverage"),
        message(3, "text", sender="coordinator", content="REJECT bbbbbbb relayed decision"),
        message(4, "text", sender="stephensookra/gatekeeper", content="REJECT ccccccc failing burst"),
        message(5, "text", sender="stephensookra/gatekeeper", content="ACCEPT ddddddd stage accepted"),
        message(6, "text", sender="auditor", content="ACCEPT eeeeeee audit closed"),
        message(7, "text", sender="stephensookra/builder-cx", content="fixed the rejected revision"),
        message(8, "text", sender="intruder", content="undeclared agent message"),
    ])
    for index, item in enumerate(room["messages"]):
        second, millis = divmod(500 + index * 200, 1000)
        item["insertedAt"] = f"2026-01-01T00:00:0{second}.{millis:03d}Z"
    room["messages"][-1]["insertedAt"] = "2026-01-01T00:00:02.100Z"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        room_path = tmp / "room.json"
        log_path = tmp / "commits.log"
        floor_path = tmp / "floor.json"
        room_path.write_text(json.dumps(room))
        log_path.write_text(
            f"{'e' * 40}\x1fStephen Sookra\x1f2026-01-01T00:00:00+00:00\x1fsetup\n"
            "mandates/builder.md\n"
            f"{'c' * 40}\x1fbuilder\x1f2026-01-01T00:00:01+00:00\x1fcandidate with failing burst\n"
            "stage-1/app.py\n"
            f"{'b' * 40}\x1fbuilder\x1f2026-01-01T00:00:01+00:00\x1funrelated stage work\n"
            "stage-2/app.py\n"
            f"{'f' * 40}\x1fbuilder\x1f2026-01-01T00:00:02+00:00\x1ffix burst handling\n"
            "stage-1/app.py\n"
            f"{'9' * 40}\x1fintruder\x1f2026-01-01T00:00:02+00:00\x1fundeclared stage work\n"
            "stage-3/app.py\n"
            f"{'d' * 40}\x1fStephen Sookra\x1f2026-01-01T00:00:03+00:00\x1fpackage evidence\n"
            "README.md\n"
        )
        result = subprocess.run(
            [sys.executable, str(FLOOR_DATA), str(room_path), str(log_path), str(floor_path)],
            capture_output=True,
            text=True,
        )
        floor = json.loads(floor_path.read_text()) if floor_path.exists() else {}
        log_path.write_text(
            log_path.read_text()
            + f"{'a' * 40}\x1fStephen Sookra\x1f2026-01-01T00:00:04+00:00\x1fpackage again\n"
              "FACTORY.md\n"
        )
        second_path = tmp / "floor-second.json"
        second = subprocess.run(
            [sys.executable, str(FLOOR_DATA), str(room_path), str(log_path), str(second_path)],
            capture_output=True,
            text=True,
        )
        floor_second = json.loads(second_path.read_text()) if second_path.exists() else {}
        unrelated_log = tmp / "unrelated.log"
        unrelated_log.write_text(
            f"{'e' * 40}\x1fStephen Sookra\x1f2026-01-01T00:00:00+00:00\x1fsetup\n"
            "mandates/builder.md\n"
            f"{'c' * 40}\x1fbuilder\x1f2026-01-01T00:00:01+00:00\x1fcandidate with failing burst\n"
            "stage-1/app.py\n"
            f"{'b' * 40}\x1fbuilder\x1f2026-01-01T00:00:01+00:00\x1funrelated stage work\n"
            "stage-2/app.py\n"
        )
        unrelated_path = tmp / "unrelated.json"
        unrelated = subprocess.run(
            [sys.executable, str(FLOOR_DATA), str(room_path), str(unrelated_log), str(unrelated_path)],
            capture_output=True,
            text=True,
        )
        unrelated_floor = json.loads(unrelated_path.read_text()) if unrelated_path.exists() else {}
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
        and second.returncode == 0
        and totals.get("commits") == 4
        and totals.get("seat_commits") == 3
        and totals.get("rejects_followed_by_seat_commit") == 1
        and floor.get("stage_first_commit_s") == {"1": 0.5, "2": 0.5}
        and [commit["sha"] for commit in floor.get("commits", [])] == [
            "c" * 40, "b" * 40, "f" * 40, "9" * 40,
        ]
        and floor.get("commits", [])[-1].get("by_seat") is False
        and floor_second == floor
        and unrelated.returncode == 0
        and unrelated_floor.get("totals", {}).get("rejects_followed_by_seat_commit") == 0
        and [r["rev"] for r in floor.get("rejections", [])] == ["ccccccc"]
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


def run_floor_dispatch_time_check():
    room = export([
        message(1, "task", sender="coordinator"),
        message(2, "text", "Human", "human", "dispatch"),
        message(3, "text", sender="builder", content="work complete"),
    ])
    room["messages"][0]["insertedAt"] = "2026-01-01T00:00:00.000Z"
    room["messages"][1]["insertedAt"] = "2026-01-01T00:00:10.000Z"
    room["messages"][2]["insertedAt"] = "2026-01-01T00:00:15.000Z"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        room_path = tmp / "room.json"
        log_path = tmp / "commits.log"
        floor_path = tmp / "floor.json"
        room_path.write_text(json.dumps(room))
        log_path.write_text(
            f"{'e' * 40}\x1fStephen Sookra\x1f2026-01-01T00:00:00+00:00\x1fsetup\n"
            "mandates/builder.md\n"
            f"{'b' * 40}\x1fbuilder\x1f2026-01-01T00:00:12+00:00\x1fbuild\n"
            "stage-1/app.py\n"
        )
        result = subprocess.run(
            [sys.executable, str(FLOOR_DATA), str(room_path), str(log_path), str(floor_path)],
            capture_output=True,
            text=True,
        )
        floor = json.loads(floor_path.read_text()) if floor_path.exists() else {}
    event_times = [event["t"] for event in floor.get("events", [])]
    good = (
        result.returncode == 0
        and floor.get("duration_s") == 5.0
        and event_times == [0.0, 5.0]
        and floor.get("stage_first_commit_s") == {"1": 2.0}
    )
    if good:
        print("ok   floor duration starts at the human dispatch")
    else:
        failures.append("floor duration dispatch boundary")
        print("BAD  floor duration includes pre-dispatch room events")
        print(result.stdout)
        print(result.stderr)
        print(floor)


def run_declared_seat_check():
    room = export([
        message(1, "text", "Human", "human", "dispatch"),
        message(2, "text", sender="stephensookra/builder-cx", content="stage work complete"),
    ])
    room["messages"][-1]["insertedAt"] = "2026-01-01T00:00:01.000Z"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        repo = tmp / "result"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        mandates = repo / "mandates"
        mandates.mkdir()
        (mandates / "builder.md").write_text("# Builder\n")
        subprocess.run(["git", "-C", str(repo), "add", "mandates/builder.md"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Stephen Sookra",
             "-c", "user.email=stephen@example.invalid", "commit", "-qm", "setup"],
            check=True,
        )
        stage = repo / "stage-1"
        stage.mkdir()
        (stage / "app.py").write_text("pass\n")
        subprocess.run(["git", "-C", str(repo), "add", "stage-1/app.py"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=builder",
             "-c", "user.email=builder@example.invalid", "commit", "-qm", "build stage"],
            check=True,
        )
        intruder_stage = repo / "stage-2"
        intruder_stage.mkdir()
        (intruder_stage / "app.py").write_text("pass\n")
        subprocess.run(["git", "-C", str(repo), "add", "stage-2/app.py"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=intruder",
             "-c", "user.email=intruder@example.invalid", "commit", "-qm", "intruder stage"],
            check=True,
        )
        room_path = tmp / "room.json"
        floor_path = tmp / "floor.json"
        room_path.write_text(json.dumps(room))
        result = subprocess.run(
            [sys.executable, str(FLOOR_DATA), str(room_path), str(repo), str(floor_path)],
            capture_output=True,
            text=True,
        )
        floor = json.loads(floor_path.read_text()) if floor_path.exists() else {}
    commits = floor.get("commits", [])
    good = (
        result.returncode == 0
        and floor.get("seats") == ["builder-cx"]
        and floor.get("totals", {}).get("commits") == 2
        and floor.get("totals", {}).get("seat_commits") == 1
        and len(commits) == 2
        and commits[0].get("author") == "builder"
        and commits[0].get("by_seat") is True
        and commits[1].get("author") == "intruder"
        and commits[1].get("by_seat") is False
    )
    if good:
        print("ok   committed mandates map temporary handles to canonical seat authors")
    else:
        failures.append("floor data canonical seat authors")
        print("BAD  floor data did not recognize a canonical author behind a temporary handle")
        print(result.stdout)
        print(result.stderr)
        print(floor)


def run_static_public_claim_checks():
    factory_template = FACTORY_TEMPLATE.read_text()
    floor_index = FLOOR_INDEX.read_text()
    good = (
        "all four stage folders" not in factory_template
        and "built and checked one stage folder at a time" in factory_template
        and "Six agents. One verifiable run." in floor_index
        and "Five agents" not in floor_index
        and "python tools/floor_data.py room.json . floor.json" in floor_index
        and "python factory/tools/floor_data.py room.json . floor.json" not in floor_index
    )
    if good:
        print("ok   public fallback copy avoids unmeasured run claims")
    else:
        failures.append("public fallback copy")
        print("BAD  public fallback copy contains an unmeasured or stale claim")


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
         expected="each ROOM COUNT report uses a distinct boundary anchor", expected_accepts=2)

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

all_seats = ["coordinator", "modeler", "builder", "surface", "gatekeeper", "auditor"]
full_roster = boundary_room()
for number, seat in enumerate(("modeler", "builder", "surface", "auditor"), start=20_000):
    full_roster["messages"].append(message(number, "thought", sender=seat))
run_room("all committed seats produced room activity", full_roster, True,
         expected_seats=all_seats)

missing_auditor = json.loads(json.dumps(full_roster))
missing_auditor["messages"] = [
    item for item in missing_auditor["messages"]
    if (item.get("senderName") or "").split("/")[-1] != "auditor"
]
run_room("a committed seat without activity fails", missing_auditor, False,
         expected="room activity matches all committed seats", expected_seats=all_seats)

run_room("a judged export with zero acceptances fails closed", export([
    message(1, "text", "Human", "human", "dispatch"),
]), False, expected="unique ACCEPT revisions", expected_accepts=4)

run_room("a judged export without a final report fails closed", boundary_room(), False,
         expected="exactly one FINAL REPORT", add_final=False)

text_after_final = boundary_room()
text_after_final["messages"].extend([
    message(100_001, "text", sender="coordinator", content="FINAL REPORT\nrun complete"),
    message(100_002, "text", sender="builder", content="late reply"),
])
run_room("text after the final report fails closed", text_after_final, False,
         expected="FINAL REPORT is the last text message", add_final=False)

run_factory_md_checks()
run_floor_verdict_checks()
run_rejection_timing_checks()
run_saved_log_ancestry_check()
run_floor_dispatch_time_check()
run_declared_seat_check()
run_judge_guide_checks()
run_static_public_claim_checks()
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
