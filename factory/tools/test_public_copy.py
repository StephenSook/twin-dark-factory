#!/usr/bin/env python3
"""Regression cases for the public copy check: each rule fails on a planted defect."""
import json
import pathlib
import subprocess
import sys
import tempfile

TOOL = pathlib.Path(__file__).resolve().parent / "check_public_copy.py"
failures = []


def run(files, quotes=None):
    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        paths = []
        for name, text in files.items():
            path = root / name
            path.write_text(text, encoding="utf-8")
            paths.append(str(path))
        args = [sys.executable, str(TOOL)]
        if quotes is not None:
            room, floor = root / "room.json", root / "floor.json"
            room.write_text(json.dumps({"messages": [{"content": quotes}]}), encoding="utf-8")
            floor.write_text(json.dumps({"events": []}), encoding="utf-8")
            args += ["--quotes", str(room), str(floor)]
        return subprocess.run(args + paths, capture_output=True, text=True)


def expect(label, ok, result, needle=""):
    good = (result.returncode == 0) == ok and needle in (result.stdout + result.stderr)
    print(("ok   " if good else "BAD  ") + label)
    if not good:
        failures.append(label)
        print(result.stdout + result.stderr)


clean = "# Run result\n\nThe gatekeeper posted 4 ACCEPT verdicts.\n"
expect("clean copy passes", True, run({"README.md": clean}), "PASS")
expect("em dash in our copy fails", False, run({"README.md": "Four stages — one room.\n"}), "em dash")
expect("curly quote fails", False, run({"README.md": "“quoted” words here.\n"}), "curly quote")
expect("schema marker fails", False, run({"README.md": "Result: REQUIRED_MEASURED_RESULT\n"}), "pending value")
expect("unfilled generator placeholder fails", False, run({"F.md": "Cost: {{COST_TABLE}}\n"}), "pending value")
expect("unfilled form placeholder fails", False, run({"F.md": "Stage {STAGES_REACHED} reached.\n"}), "pending value")
expect("pending measurement fails", False, run({"F.md": "Usage is NOT MEASURED YET.\n"}), "pending value")
expect("AI-tone word fails", False, run({"README.md": "A robust factory.\n"}), "AI-tone word 'robust'")
expect("html surface is read", False, run({"i.html": "<p>Six seats — one room.</p>"}), "em dash")
quote = "STAGE 1 HANDOFF — PART 1 OF 5 for every seat in the room"
expect("verbatim room quote keeps its own typography", True,
       run({"floor.html": f"<p>{quote}</p>"}, quotes=f"@coordinator {quote} and more"), "PASS")
expect("a paraphrase of a room message is still checked", False,
       run({"floor.html": "<p>STAGE ONE HANDOFF — PART ONE OF FIVE for all seats</p>"}, quotes=quote), "em dash")
expect("missing surface fails", False, run({}), "")
print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
