#!/usr/bin/env python3
"""Mutation tests for the public-claims matrix gate."""

import copy
import json
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECKER = ROOT / "factory" / "tools" / "check_public_claims.py"


def run(matrix_path, matrix, surfaces, want_ok, allow_absent=False):
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    command = ["python3", str(CHECKER), "--evidence-root", str(matrix_path.parent.parent)]
    if allow_absent:
        command.append("--allow-absent")
    command.extend([str(matrix_path), *(str(path) for path in surfaces)])
    result = subprocess.run(command, capture_output=True, text=True)
    if (result.returncode == 0) != want_ok:
        raise AssertionError(result.stdout + result.stderr)


def replace_claim(matrix, old_text, new_claim):
    changed = copy.deepcopy(matrix)
    changed["claims"] = [
        new_claim if claim["text"] == old_text else claim for claim in changed["claims"]
    ]
    return changed


def claim(matrix, text):
    return next(item for item in matrix["claims"] if item["text"] == text)


def without(matrix, text):
    changed = copy.deepcopy(matrix)
    changed["claims"] = [item for item in changed["claims"] if item["text"] != text]
    return changed


with tempfile.TemporaryDirectory() as tmp_value:
    tmp = pathlib.Path(tmp_value)
    evidence_dir = tmp / "evidence"
    evidence_dir.mkdir()
    matrix_path = evidence_dir / "public-claims.json"
    source = tmp / "room.json"
    facts = evidence_dir / "facts.json"
    codex_source = evidence_dir / "codex.json"
    readme = tmp / "README.md"
    deck = tmp / "deck.html"
    rendered = tmp / "rendered.html"
    source.write_text(json.dumps({
        "six_band_seats_completed": 4,
        "opencode_powers_auditor": "OpenCode",
        "stage4_passed": "Stage4",
        "codex_tests_ran": 57,
        "attacks_passed": 73,
        "codex_tests_passed": 73,
        "passed_attacks": 73,
        "rendered_count": 77,
        "markdown_codex_tests_passed": 73,
        "inline_codex_tests_passed": 74,
        "hidden_claim": 888,
        "visible_result": 61,
        "visible_placeholder": 62,
        "weather": "sunny",
        "weather_temperature": 73,
        "modeler_seat": "Codex",
        "requests_handled": 73,
        "codex_requests_handled_duration": 73,
        "codex_requests_handled_mean": 73,
        "codex_tests_passed_duration": 73,
        "codex_tests_passed_sessions": 73,
        "deployment_security_status": "The deployment is not secure.",
        "circular_claim": "Kubernetes secures production.",
        "codex": {"tests": {"passed": {"id": 73, "sessions": {"value": 73}}}},
    }), encoding="utf-8")
    facts.write_text(json.dumps({
        "measurements": [
            {
                "entity": "Codex", "predicate": "ran", "measure": "tests", "value": 57,
                "source": {"path": "room.json", "pointer": "/codex_tests_ran"},
            },
            {
                "entity": "Codex", "predicate": "passed", "measure": "tests", "value": 73,
                "source": {"path": "room.json", "pointer": "/weather_temperature"},
            },
            {
                "entity": "Codex", "predicate": "passed", "measure": "tests", "value": 73,
                "source": {"path": "room.json", "pointer": "/codex_tests_passed_duration"},
            },
            {
                "entity": "Codex", "predicate": "passed", "measure": "tests", "value": 73,
                "source": {"path": "room.json", "pointer": "/codex_tests_passed_sessions"},
            },
            {
                "entity": "Codex", "predicate": "passed", "measure": "tests", "value": 73,
                "source": {"path": "room.json", "pointer": "/codex/tests/passed/id"},
            },
            {
                "entity": "Codex", "predicate": "passed", "measure": "tests", "value": 73,
                "source": {"path": "room.json", "pointer": "/codex/tests/passed/sessions/value"},
            },
        ],
        "circular_claim": "Kubernetes secures production.",
        "kubernetes_status": "secures production",
    }), encoding="utf-8")
    codex_source.write_text(json.dumps({"weather_temperature": 73, "test_duration": 73}), encoding="utf-8")
    readme.write_text(
        "# Result\n\n- Six BAND seats completed 4 of 4 stages.\n\n"
        "OpenCode powers the auditor.\n\nStage4 passed.\n\n"
        "```sh\npython3 tool.py\n```\n\n"
        '<img alt="Markdown Codex passed 73 tests.">\n\n'
        '<img alt="Inline Codex passed 74 tests.">\n',
        encoding="utf-8",
    )
    deck.write_text(
        '<title>Evidence deck</title><style>.n{width:100px}</style>'
        '<p>Codex ran <b>57</b> tests.</p>'
        '<script>const fake = "99";</script><p>Featherless cost is unknown.</p>'
        '<svg aria-label="Evidence drawing"><text>73 attacks passed.</text></svg>'
        '<img alt="Codex passed 73 tests">'
        '<img alt="small icon">'
        '<div class="stat"><b>73</b><span>attacks passed</span></div>'
        '<table><tr><td>modeler</td><td>Codex</td></tr></table>'
        '<span hidden>Hidden 999 claim</span><span aria-hidden="true">Hidden 888 claim</span>'
        '<input value="Visible 61 result"><input placeholder="Visible 62 placeholder">',
        encoding="utf-8",
    )
    base = {
        "technology_terms": ["BAND", "Codex", "OpenCode", "Featherless"],
        "claims": [
            {"text": "Result", "status": "NONCLAIM", "reason": "heading", "evidence": []},
            {"text": "python3 tool.py", "status": "NONCLAIM", "reason": "command", "evidence": []},
            {
                "text": "Markdown Codex passed 73 tests.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/markdown_codex_tests_passed",
                    "equals": 73, "display": "73",
                    "clause": "Markdown Codex passed 73 tests",
                }],
            },
            {
                "text": "Inline Codex passed 74 tests.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/inline_codex_tests_passed",
                    "equals": 74, "display": "74",
                    "clause": "Inline Codex passed 74 tests",
                }],
            },
            {
                "text": "Six BAND seats completed 4 of 4 stages.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/six_band_seats_completed",
                    "equals": 4, "display": "4",
                    "clause": "Six BAND seats completed 4 of 4 stages",
                }],
            },
            {
                "text": "OpenCode powers the auditor.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/opencode_powers_auditor",
                    "equals": "OpenCode", "display": "OpenCode",
                    "clause": "OpenCode powers the auditor",
                }],
            },
            {
                "text": "Stage4 passed.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/stage4_passed",
                    "equals": "Stage4", "display": "Stage4", "clause": "Stage4 passed",
                }],
            },
            {"text": "Evidence deck", "status": "NONCLAIM", "reason": "document title", "evidence": []},
            {"text": "Evidence drawing", "status": "NONCLAIM", "reason": "accessible label", "evidence": []},
            {
                "text": "Codex ran 57 tests.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "evidence/facts.json", "pointer": "/measurements/0/value",
                    "equals": 57, "display": "57", "clause": "Codex ran 57 tests",
                }],
            },
            {
                "text": "Featherless cost is unknown.", "status": "UNKNOWN DISCLOSED",
                "entity": "Featherless", "metric": "cost", "state": "is unknown", "evidence": [],
            },
            {
                "text": "73 attacks passed.",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/attacks_passed",
                    "equals": 73, "display": "73",
                    "clause": "73 attacks passed",
                }],
            },
            {
                "text": "Codex passed 73 tests",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/codex_tests_passed",
                    "equals": 73, "display": "73",
                    "clause": "Codex passed 73 tests",
                }],
            },
            {
                "text": "73 attacks passed",
                "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/passed_attacks",
                    "equals": 73, "display": "73", "clause": "73 attacks passed",
                }],
            },
            {"text": "small icon", "status": "NONCLAIM", "reason": "accessible label", "evidence": []},
            {
                "text": "modeler Codex", "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/modeler_seat",
                    "equals": "Codex", "display": "Codex", "clause": "modeler Codex",
                }],
            },
            {
                "text": "Hidden 888 claim", "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/hidden_claim",
                    "equals": 888, "display": "888", "clause": "Hidden 888 claim",
                }],
            },
            {
                "text": "Visible 61 result", "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/visible_result",
                    "equals": 61, "display": "61", "clause": "Visible 61 result",
                }],
            },
            {
                "text": "Visible 62 placeholder", "status": "VERIFIED",
                "evidence": [{
                    "path": "room.json", "pointer": "/visible_placeholder",
                    "equals": 62, "display": "62", "clause": "Visible 62 placeholder",
                }],
            },
            {"text": "A removed claim used 12 tools.", "status": "CUT", "evidence": []},
        ],
    }
    run(matrix_path, base, [readme, deck], True)

    for unmapped in ["An ordinary unmapped sentence.", "supabase powers runtime.", "thirteen tests passed."]:
        readme.write_text(readme.read_text(encoding="utf-8") + f"\n{unmapped}\n", encoding="utf-8")
        run(matrix_path, base, [readme, deck], False)
        readme.write_text(readme.read_text(encoding="utf-8").replace(f"\n{unmapped}\n", "\n"), encoding="utf-8")

    broken = copy.deepcopy(base)
    claim(broken, "Six BAND seats completed 4 of 4 stages.")["evidence"] = []
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    claim(broken, "Six BAND seats completed 4 of 4 stages.")["evidence"][0]["pointer"] = "/absent"
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    claim(broken, "Codex ran 57 tests.")["evidence"][0]["equals"] = "57"
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    claim(broken, "Codex ran 57 tests.")["evidence"][0]["display"] = "fifty-seven"
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    room_claim = claim(broken, "Six BAND seats completed 4 of 4 stages.")
    room_claim["evidence"][0]["path"] = "evidence/public-claims.json"
    room_claim["evidence"][0]["pointer"] = "/claims/1/text"
    room_claim["evidence"][0]["equals"] = room_claim["text"]
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    claim(broken, "OpenCode powers the auditor.")["evidence"][0]["pointer"] = "/room"
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "OpenCode powers the auditor.")["evidence"][0]
    unrelated.update({"pointer": "/weather", "equals": "sunny", "display": "powers"})
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({"pointer": "/weather_temperature", "equals": 73, "display": "73"})
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/codex.json", "pointer": "/weather_temperature",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/codex.json", "pointer": "/test_duration",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/facts.json", "pointer": "/measurements/1/value",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/facts.json", "pointer": "/measurements/2/value",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/facts.json", "pointer": "/measurements/3/value",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/facts.json", "pointer": "/measurements/4/value",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    broken = copy.deepcopy(base)
    unrelated = claim(broken, "Codex passed 73 tests")["evidence"][0]
    unrelated.update({
        "path": "evidence/facts.json", "pointer": "/measurements/5/value",
        "equals": 73, "display": "73",
    })
    run(matrix_path, broken, [readme, deck], False)

    for mixed_text in [
        "OpenCode powers the auditor. Featherless cost is unknown.",
        "OpenCode powers the auditor while Featherless cost is unknown.",
    ]:
        changed = replace_claim(base, "Featherless cost is unknown.", {
            "text": mixed_text, "status": "UNKNOWN DISCLOSED",
            "entity": "Featherless", "metric": "cost", "state": "is unknown", "evidence": [],
        })
        deck.write_text(deck.read_text(encoding="utf-8").replace("Featherless cost is unknown.", mixed_text), encoding="utf-8")
        run(matrix_path, changed, [readme, deck], False)
        deck.write_text(deck.read_text(encoding="utf-8").replace(mixed_text, "Featherless cost is unknown."), encoding="utf-8")

    injected = copy.deepcopy(base)
    injected["technology_terms"].append("OpenCode powers the auditor because Featherless")
    claim(injected, "Featherless cost is unknown.").update({
        "text": "OpenCode powers the auditor because Featherless cost is unknown.",
        "entity": "OpenCode powers the auditor because Featherless",
    })
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Featherless cost is unknown.",
        "OpenCode powers the auditor because Featherless cost is unknown.",
    ), encoding="utf-8")
    run(matrix_path, injected, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "OpenCode powers the auditor because Featherless cost is unknown.",
        "Featherless cost is unknown.",
    ), encoding="utf-8")

    for compound_text in [
        "Codex ran 57 tests and Kubernetes handled 9000 requests.",
        "Codex ran 57 tests plus Kubernetes handled 9000 requests.",
        "Codex ran 57 tests, Kubernetes secures production traffic.",
    ]:
        compound = replace_claim(base, "Codex ran 57 tests.", {
            **copy.deepcopy(claim(base, "Codex ran 57 tests.")),
            "text": compound_text,
        })
        deck.write_text(deck.read_text(encoding="utf-8").replace("Codex ran <b>57</b> tests.", compound_text), encoding="utf-8")
        run(matrix_path, compound, [readme, deck], False)
        deck.write_text(deck.read_text(encoding="utf-8").replace(compound_text, "Codex ran <b>57</b> tests."), encoding="utf-8")

    false_nonclaim = replace_claim(base, "Codex ran 57 tests.", {
        "text": "Codex ran 57 tests.", "status": "NONCLAIM", "reason": "heading", "evidence": [],
    })
    run(matrix_path, false_nonclaim, [readme, deck], False)

    suffix_matrix = replace_claim(base, "Codex ran 57 tests.", {
        "text": "Codex handled 73k requests.", "status": "VERIFIED",
        "evidence": [{
            "path": "room.json", "pointer": "/requests_handled",
            "equals": 73, "display": "73", "clause": "Codex handled 73k requests",
        }],
    })
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Codex ran <b>57</b> tests.", "Codex handled 73k requests.",
    ), encoding="utf-8")
    run(matrix_path, suffix_matrix, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Codex handled 73k requests.", "Codex ran <b>57</b> tests.",
    ), encoding="utf-8")

    wrong_dimension = replace_claim(base, "Codex ran 57 tests.", {
        "text": "Codex handled 73 requests.", "status": "VERIFIED",
        "evidence": [{
            "path": "room.json", "pointer": "/codex_requests_handled_duration",
            "equals": 73, "display": "73", "clause": "Codex handled 73 requests",
        }],
    })
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Codex ran <b>57</b> tests.", "Codex handled 73 requests.",
    ), encoding="utf-8")
    run(matrix_path, wrong_dimension, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Codex handled 73 requests.", "Codex ran <b>57</b> tests.",
    ), encoding="utf-8")

    wrong_aggregate = replace_claim(base, "Codex ran 57 tests.", {
        "text": "Codex handled 73 requests.", "status": "VERIFIED",
        "evidence": [{
            "path": "room.json", "pointer": "/codex_requests_handled_mean",
            "equals": 73, "display": "73", "clause": "Codex handled 73 requests",
        }],
    })
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Codex ran <b>57</b> tests.", "Codex handled 73 requests.",
    ), encoding="utf-8")
    run(matrix_path, wrong_aggregate, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        "Codex handled 73 requests.", "Codex ran <b>57</b> tests.",
    ), encoding="utf-8")

    unsupported_technology = replace_claim(base, "Codex passed 73 tests", {
        **copy.deepcopy(claim(base, "Codex passed 73 tests")),
        "text": "Codex passed 73 tests with Kubernetes.",
    })
    unsupported_technology["technology_terms"].append("Kubernetes")
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        '<img alt="Codex passed 73 tests">',
        '<img alt="Codex passed 73 tests with Kubernetes.">',
    ), encoding="utf-8")
    run(matrix_path, unsupported_technology, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace(
        '<img alt="Codex passed 73 tests with Kubernetes.">',
        '<img alt="Codex passed 73 tests">',
    ), encoding="utf-8")

    opposite_polarity = replace_claim(base, "Stage4 passed.", {
        "text": "The deployment is secure.", "status": "VERIFIED",
        "evidence": [{
            "path": "room.json", "pointer": "/deployment_security_status",
            "equals": "The deployment is not secure.", "display": "secure",
            "clause": "The deployment is secure",
        }],
    })
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Stage4 passed.", "The deployment is secure.",
    ), encoding="utf-8")
    run(matrix_path, opposite_polarity, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "The deployment is secure.", "Stage4 passed.",
    ), encoding="utf-8")

    omitted_technology = replace_claim(base, "Stage4 passed.", {
        "text": "Kubernetes secures production.", "status": "VERIFIED",
        "evidence": [{
            "path": "room.json", "pointer": "/deployment_security_status",
            "equals": "The deployment is not secure.", "display": "The deployment is not secure.",
            "clause": "Kubernetes secures production",
        }],
    })
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    source_payload["production_security_status"] = "secure"
    source.write_text(json.dumps(source_payload), encoding="utf-8")
    claim(omitted_technology, "Kubernetes secures production.")["evidence"][0].update({
        "equals": "secure", "display": "secure",
    })
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Stage4 passed.", "Kubernetes secures production.",
    ), encoding="utf-8")
    run(matrix_path, omitted_technology, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Kubernetes secures production.", "Stage4 passed.",
    ), encoding="utf-8")
    source_payload["production_security_status"] = "The deployment is not secure."
    source.write_text(json.dumps(source_payload), encoding="utf-8")

    circular_evidence = replace_claim(base, "Stage4 passed.", {
        "text": "Kubernetes secures production.", "status": "VERIFIED",
        "evidence": [{
            "path": "evidence/facts.json", "pointer": "/circular_claim",
            "equals": "Kubernetes secures production.", "display": "Kubernetes secures production.",
            "clause": "Kubernetes secures production",
        }],
    })
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Stage4 passed.", "Kubernetes secures production.",
    ), encoding="utf-8")
    run(matrix_path, circular_evidence, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Kubernetes secures production.", "Stage4 passed.",
    ), encoding="utf-8")

    split_circular_evidence = replace_claim(base, "Stage4 passed.", {
        "text": "Kubernetes secures production.", "status": "VERIFIED",
        "evidence": [{
            "path": "evidence/facts.json", "pointer": "/kubernetes_status",
            "equals": "secures production", "display": "secures production",
            "clause": "Kubernetes secures production",
        }],
    })
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Stage4 passed.", "Kubernetes secures production.",
    ), encoding="utf-8")
    run(matrix_path, split_circular_evidence, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace(
        "Kubernetes secures production.", "Stage4 passed.",
    ), encoding="utf-8")

    deck.write_text(deck.read_text(encoding="utf-8") + "<p>Production-ready deployment</p>", encoding="utf-8")
    wrong_structure = copy.deepcopy(base)
    wrong_structure["claims"].append({
        "text": "Production-ready deployment", "status": "NONCLAIM", "reason": "heading", "evidence": [],
    })
    run(matrix_path, wrong_structure, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace("<p>Production-ready deployment</p>", ""), encoding="utf-8")

    deck.write_text(deck.read_text(encoding="utf-8") + "<h1>Production-ready deployment</h1>", encoding="utf-8")
    false_heading = copy.deepcopy(base)
    false_heading["claims"].append({
        "text": "Production-ready deployment", "status": "NONCLAIM", "reason": "heading", "evidence": [],
    })
    run(matrix_path, false_heading, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace("<h1>Production-ready deployment</h1>", ""), encoding="utf-8")

    deck.write_text(deck.read_text(encoding="utf-8") + "<h1>Deployed application</h1>", encoding="utf-8")
    deployed_heading = copy.deepcopy(base)
    deployed_heading["claims"].append({
        "text": "Deployed application", "status": "NONCLAIM", "reason": "heading", "evidence": [],
    })
    run(matrix_path, deployed_heading, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace("<h1>Deployed application</h1>", ""), encoding="utf-8")

    deck.write_text(deck.read_text(encoding="utf-8") + "<button>Service online</button>", encoding="utf-8")
    online_control = copy.deepcopy(base)
    online_control["claims"].append({
        "text": "Service online", "status": "NONCLAIM", "reason": "control", "evidence": [],
    })
    run(matrix_path, online_control, [readme, deck], False)
    deck.write_text(deck.read_text(encoding="utf-8").replace("<button>Service online</button>", ""), encoding="utf-8")

    readme.write_text(readme.read_text(encoding="utf-8") + "\n```sh\nDocker powers production.\n```\n", encoding="utf-8")
    false_command = copy.deepcopy(base)
    false_command["claims"].append({
        "text": "Docker powers production.", "status": "NONCLAIM", "reason": "command", "evidence": [],
    })
    run(matrix_path, false_command, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace("\n```sh\nDocker powers production.\n```\n", "\n"), encoding="utf-8")

    readme.write_text(readme.read_text(encoding="utf-8") + "\n```sh\npython3 powers production.\n```\n", encoding="utf-8")
    false_python_command = copy.deepcopy(base)
    false_python_command["claims"].append({
        "text": "python3 powers production.", "status": "NONCLAIM", "reason": "command", "evidence": [],
    })
    run(matrix_path, false_python_command, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace("\n```sh\npython3 powers production.\n```\n", "\n"), encoding="utf-8")

    for required in [
        "python3 tool.py", "Markdown Codex passed 73 tests.", "Inline Codex passed 74 tests.",
        "Hidden 888 claim",
        "Visible 61 result", "Visible 62 placeholder",
    ]:
        run(matrix_path, without(base, required), [readme, deck], False)

    readme.write_text(readme.read_text(encoding="utf-8") + "\nA removed claim used 12 tools.\n", encoding="utf-8")
    run(matrix_path, base, [readme, deck], False)
    readme.write_text(readme.read_text(encoding="utf-8").replace("\nA removed claim used 12 tools.\n", "\n"), encoding="utf-8")

    rendered_claim = {
        "text": "Rendered room count is 77.",
        "status": "VERIFIED",
        "evidence": [{
            "path": "room.json", "pointer": "/rendered_count",
            "equals": 77, "display": "77", "clause": "Rendered room count is 77",
        }],
    }
    with_rendered = copy.deepcopy(base)
    with_rendered["claims"].append(rendered_claim)
    run(matrix_path, with_rendered, [readme, deck], True, allow_absent=True)
    run(matrix_path, with_rendered, [readme, deck], False)
    rendered.write_text("<p>Rendered room count is 77.</p>", encoding="utf-8")
    run(matrix_path, with_rendered, [readme, deck, rendered], True)

print("ok   every public unit needs a typed evidence disposition and rendered claims need strict coverage")
