"""Fill the dispatch template for one run, so every dispatch is provably the same text.

  python build_dispatch.py <track> <run-name> [--design <dir>] > dispatch.md

Without --design the visual-direction block is left out (the brief is product-owner input for one
product; the mandates never depend on it).
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
KICKOFF = "/home/ubuntu/work/dark-factory-wearedevs"
RESULT = "/home/ubuntu/work/band-work/current"


def main():
    args = sys.argv[1:]
    track, run = args[0], args[1]
    design = args[args.index("--design") + 1] if "--design" in args else None
    template = args[args.index("--template") + 1] if "--template" in args else "template.md"
    text = (HERE.parent / "dispatch" / template).read_text()
    if design is None and "Visual direction" in text:
        start = text.index("Visual direction")
        end = text.index("Folder rules:")
        text = text[:start] + text[end:]
    import json
    seats = [s for s in json.loads((HERE.parent / "seats.json").read_text()) if s != "coordinator"]
    band = "\n".join(f"- @stephensookra/{s}" for s in seats)
    ver = [f"@{s}" for s in ("modeler", "gatekeeper", "auditor") if s in seats]
    verifiers = ver[0] if len(ver) == 1 else ", ".join(ver[:-1]) + " and " + ver[-1]
    everyone = ["coordinator"] + seats
    authors = ", ".join(everyone[:-1]) + " or " + everyone[-1]
    for key, value in {"{BAND}": band, "{VERIFIERS}": verifiers, "{SEATS}": authors,
                       "{KICKOFF}": KICKOFF, "{TRACK}": track, "{RESULT}": RESULT,
                       "{CHECKS}": f"/home/ubuntu/work/band-work/checks/{run}",
                       "{DESIGN}": design or ""}.items():
        text = text.replace(key, value)
    import re
    left = re.findall(r"\{[A-Z_]+\}", text)
    if left:
        sys.exit(f"unfilled placeholders: {left}")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
