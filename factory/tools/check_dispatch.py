"""Prove every runnable dispatch is generated and names exactly the seats. Exit 1 on any problem.

  python factory/tools/check_dispatch.py            (from the repository root)

- factory/dispatch/runs.json lists every runnable dispatch with its generator arguments. Every
  dispatch/*.md except the templates must be listed, every listed file must exist, and each must equal
  what build_dispatch.py produces from those arguments.
- For band dispatches (template.md): the seats named by seats.json keys, tracked mandates (what
  the commit guard authorizes) and src role files must be the same set, the Band section (from its
  heading to "Paths:") must list exactly every seat but the coordinator, and the commit-author
  sentence must name exactly every seat.
- No dispatch may contain a brace.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
F = ROOT / "factory"
D = F / "dispatch"
TEMPLATES = {"template.md", "baseline-template.md"}
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

runs = json.loads((D / "runs.json").read_text())
if not runs:
    sys.exit("runs.json lists no dispatch")
same("dispatch files vs runs.json", {p.stem for p in D.glob("*.md") if p.name not in TEMPLATES}, set(runs))

checked = 0
for run, args in runs.items():
    path = D / f"{run}.md"
    if not path.exists():
        continue  # already reported by the file-set comparison
    text = path.read_text()
    gen = subprocess.run([sys.executable, str(F / "tools" / "build_dispatch.py"), *args],
                         capture_output=True, text=True)
    if gen.returncode != 0:
        problems.append(f"{run}: generator failed: {gen.stderr.strip()[:300]}")
    elif gen.stdout != text:
        problems.append(f"{run}: differs from the generator output for {args}")
    if re.search(r"[{}]", text):
        problems.append(f"{run}: unresolved brace")
    template = args[args.index("--template") + 1] if "--template" in args else "template.md"
    if template == "template.md":
        lines = text.splitlines()
        heads = [i for i, l in enumerate(lines) if l.startswith("Band (")]
        ends = [i for i, l in enumerate(lines) if l.startswith("Paths:")]
        if len(heads) != 1 or len(ends) != 1 or ends[0] < heads[0]:
            problems.append(f"{run}: Band section not found exactly once before Paths:")
            continue
        handles = set()
        for l in lines[heads[0] + 1:ends[0]]:
            if not l.strip():
                continue
            m = re.fullmatch(r"- @stephensookra/([a-z]+)", l)
            if m:
                handles.add(m.group(1))
            else:
                problems.append(f"{run}: unexpected line in the Band section {l!r}")
        same(f"{run} Band section", handles, want - {"coordinator"})
        authors = re.findall(r"where <seat> is (.+)\.", text)
        if len(authors) != 1:
            problems.append(f"{run}: expected one commit-author sentence, found {len(authors)}")
        else:
            same(f"{run} commit authors", set(re.split(r", | or ", authors[0])), want)
    checked += 1

if checked != len(runs):
    problems.append(f"checked {checked} of {len(runs)} listed dispatches")
for p in problems:
    print("FAIL", p)
print(f"checked {checked} dispatches against {len(seats)} seats: {'FAIL' if problems else 'ok'}")
sys.exit(1 if problems else 0)
