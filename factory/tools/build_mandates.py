"""Assemble mandates/<seat>.md = Harness/Model header + role + shared agreement."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
seats = json.loads((ROOT / "seats.json").read_text())
agreement = (ROOT / "src" / "agreement.md").read_text().strip()
out = ROOT / "mandates"
out.mkdir(exist_ok=True)
for seat, cfg in seats.items():
    role = (ROOT / "src" / f"{seat}.md").read_text().strip()
    body = f"Harness: {cfg['harness']}\nModel: {cfg['model']}\n\n{role}\n\n{agreement}\n"
    (out / f"{seat}.md").write_text(body)
    print(f"built mandates/{seat}.md ({len(body.split())} words)")
if any(c["model"] == "TBD" for c in seats.values()):
    print("WARNING: a model id is still TBD", file=sys.stderr)
