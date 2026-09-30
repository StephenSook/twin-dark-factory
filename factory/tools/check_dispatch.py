"""Prove the seat list agrees everywhere a run depends on it. Exit 1 on any disagreement.

  python factory/tools/check_dispatch.py            (from the repository root)

Sources that must name exactly the same seats:
  factory/seats.json keys, tracked factory/mandates/*.md (what the commit guard authorizes),
  factory/src/<seat>.md role files, and in every run dispatch the Band block (every seat but the
  coordinator) and the commit-author sentence (every seat). A dispatch may not contain any brace.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
F = ROOT / "factory"
DISPATCHES = ["pocketful-judged.md", "tablekeeper-gen1.md"]
problems = []


def same(name, got, want):
    if got != want:
        problems.append(f"{name}: missing {sorted(want - got)}, extra {sorted(got - want)}")


seats = list(json.loads((F / "seats.json").read_text()))
if not seats:
    sys.exit("seats.json names no seat")
want = set(seats)

tracked = subprocess.run(["git", "ls-files", "--", "factory/mandates"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
same("tracked mandates", {pathlib.Path(p).stem for p in tracked if p.endswith(".md")}, want)
same("role sources", {p.stem for p in (F / "src").glob("*.md")} - {"agreement"}, want)

checked = 0
for name in DISPATCHES:
    text = (F / "dispatch" / name).read_text()
    if re.search(r"[{}]", text):
        problems.append(f"{name}: unresolved brace {re.findall(r'[{][^}]*[}]?', text)[:3]}")
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("Band ("))
    except StopIteration:
        problems.append(f"{name}: no Band block")
        continue
    block = []
    for l in lines[start + 1:]:
        if not l.strip():
            break
        block.append(l)
    handles = set()
    for l in block:
        m = re.fullmatch(r"- @stephensookra/([a-z]+)", l)
        if not m:
            problems.append(f"{name}: unexpected Band line {l!r}")
        else:
            handles.add(m.group(1))
    same(f"{name} Band block", handles, want - {"coordinator"})
    authors = re.findall(r"where <seat> is (.+)\.", text)
    if len(authors) != 1:
        problems.append(f"{name}: expected one commit-author sentence, found {len(authors)}")
    else:
        same(f"{name} commit authors", set(re.split(r", | or ", authors[0])), want)
    checked += 1

if checked != len(DISPATCHES):
    problems.append(f"checked {checked} of {len(DISPATCHES)} dispatches")
for p in problems:
    print("FAIL", p)
print(f"checked {checked} dispatches against {len(seats)} seats: {'FAIL' if problems else 'ok'}")
sys.exit(1 if problems else 0)
