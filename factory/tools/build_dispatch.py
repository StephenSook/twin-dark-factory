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
    text = (HERE.parent / "dispatch" / "template.md").read_text()
    if design is None:
        start = text.index("Visual direction")
        end = text.index("Folder rules:")
        text = text[:start] + text[end:]
    for key, value in {"{KICKOFF}": KICKOFF, "{TRACK}": track, "{RESULT}": RESULT,
                       "{CHECKS}": f"/home/ubuntu/work/band-work/checks/{run}",
                       "{DESIGN}": design or ""}.items():
        text = text.replace(key, value)
    left = [w for w in text.split() if w.startswith("{") and w.endswith("}")]
    if left:
        sys.exit(f"unfilled placeholders: {left}")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
