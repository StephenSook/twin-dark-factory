#!/usr/bin/env python3
"""Refuse public result copy that carries placeholders, banned typography or AI-tone words.

  python3 tools/check_public_copy.py [--quotes room.json evidence/floor.json] README.md FACTORY.md ...

Every number on these surfaces is generated from the evidence files by the generators, which refuse
missing facts; the five central claims are bound to verbatim room messages by check_claim_evidence.py.
This check covers what is left: no unfilled or pending value reaches a judge, and the copy follows the
house typography. It reads the same visible text units as check_public_claims.py. A unit that is a
verbatim excerpt of a room message or a replay preview (--quotes) is the band's own words, quoted, and is
not rewritten, so only those units skip the typography and tone checks.
"""

import importlib.util
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_public_claims", HERE / "check_public_claims.py")
_claims = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_claims)

TYPOGRAPHY = {
    "—": "em dash", "–": "en dash", "“": "curly quote", "”": "curly quote",
    "‘": "curly quote", "’": "curly quote",
}
PENDING = re.compile(
    r"REQUIRED_|NOT MEASURED YET|\{\{[A-Z_]+\}\}|\{[A-Z][A-Z0-9_]+\}|\bTODO\b|\bTBD\b|lorem ipsum|example\.(?:com|org)",
    re.IGNORECASE,
)
AI_TONE = re.compile(
    r"\b(?:delve|leverage[sd]?|robust|comprehensive|seamless(?:ly)?|powerful|transformative|elevate|empower|"
    r"intuitive|cutting-edge|revolutionary|amazing|effortless(?:ly)?|streamline[sd]?|unlocked|ecosystem)\b",
    re.IGNORECASE,
)


def quote_corpus(paths):
    corpus = []
    for path in paths:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        for message in data.get("messages") or []:
            if isinstance(message.get("content"), str):
                corpus.append(_claims.normalize(message["content"]))
        for event in data.get("events") or []:
            if isinstance(event.get("preview"), str):
                corpus.append(_claims.normalize(event["preview"]))
    return corpus


def is_quote(text, corpus):
    return len(text) >= 24 and any(text in item for item in corpus)


def problems_in(path, corpus=()):
    found = []
    for text, _kind in _claims.surface_units(path):
        if is_quote(text, corpus):
            continue
        for char, label in TYPOGRAPHY.items():
            if char in text:
                found.append(f"{path.name}: {label}: {text[:80]}")
        for match in PENDING.finditer(text):
            found.append(f"{path.name}: pending value {match.group(0)!r}: {text[:80]}")
        for match in AI_TONE.finditer(text):
            found.append(f"{path.name}: AI-tone word {match.group(0)!r}: {text[:80]}")
    return found


def main(argv):
    if len(argv) < 2:
        print("usage: check_public_copy.py <surface> [<surface> ...]", file=sys.stderr)
        return 2
    args = argv[1:]
    corpus = []
    if args[:1] == ["--quotes"]:
        if len(args) < 3:
            print("usage: --quotes needs room.json and floor.json", file=sys.stderr)
            return 2
        corpus = quote_corpus(args[1:3])
        args = args[3:]
    if not args:
        print("usage: check_public_copy.py [--quotes room.json floor.json] <surface> [...]", file=sys.stderr)
        return 2
    problems, units = [], 0
    for raw in args:
        path = pathlib.Path(raw)
        if not path.is_file():
            problems.append(f"missing public surface: {raw}")
            continue
        units += len(_claims.surface_units(path))
        problems += problems_in(path, corpus)
    if units == 0 and not problems:
        problems.append("no visible text units were read")
    if problems:
        for line in sorted(set(problems)):
            print("FAIL  " + line)
        return 1
    print(f"PASS  {units} visible text units on {len(args)} public surfaces carry no pending value, "
          "banned typography or AI-tone word")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
