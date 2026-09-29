"""Fail if any mandate names track detail.

Two layers: the organizers' own vocabulary list for every track (harness/vocabulary.py), and a
stricter rule of ours: no identifier-shaped token at all (paths, snake_case, kebab-case).
Usage: lint_mandates.py <kickoff-repo> <mandates-dir>
"""
import importlib.util
import pathlib
import re
import sys

kickoff, mdir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("vocab", kickoff / "harness" / "vocabulary.py")
vocab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vocab)
banned = {t for terms in vocab.TRACK_VOCABULARY.values() for t in terms}
files = sorted(mdir.glob("*.md"))
assert files, "no mandate files found: an empty scan is not a pass"
problems = []
for f in files:
    for n, line in enumerate(f.read_text().splitlines(), 1):
        for kind, term in vocab.terms_in(line):
            if term in banned:
                problems.append(f"{f.name}:{n}: BANNED {kind} {term!r}")
            elif n > 2:
                # Lines 1-2 are the required Harness/Model header; a model id is kebab-shaped
                # by nature, so the strict shape rule applies to the body only.
                problems.append(f"{f.name}:{n}: SHAPE {kind} {term!r}")
        m = re.match(r"^(Harness|Model): (.*)$", line)
        if n <= 2 and not m:
            problems.append(f"{f.name}:{n}: header line missing (Harness/Model)")
print(f"scanned {len(files)} mandates against {len(banned)} banned terms")
for p in problems:
    print(p)
sys.exit(1 if problems else 0)
