"""Commit-then-reveal for a holdout check suite the band never sees.

Before a run, `seal` prints a digest of the holdout files; the human commits only that digest.
After the run, the files are published and anyone can run `verify` to confirm they are the
same bytes that were sealed. The digest covers each file's path and exact bytes, in sorted
order, so it does not depend on timestamps, archive tools or the machine that computes it.

Usage:
  seal_holdout.py seal <dir>                 print the digest and the per-file table
  seal_holdout.py verify <dir> <digest>      exit 0 only if <dir> reproduces <digest>
"""
import hashlib
import pathlib
import sys


def files(root: pathlib.Path):
    found = sorted(p for p in root.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("."))
    if not found:
        sys.exit(f"no files under {root}: an empty holdout seals nothing")
    return found


def digest(root: pathlib.Path) -> tuple[str, list[tuple[str, str]]]:
    outer = hashlib.sha256()
    rows = []
    for p in files(root):
        rel = p.relative_to(root).as_posix()
        inner = hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append((rel, inner))
        # Length-prefix each field so no two different file sets can share one digest.
        for field in (rel.encode(), inner.encode()):
            outer.update(len(field).to_bytes(8, "big"))
            outer.update(field)
    return outer.hexdigest(), rows


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("seal", "verify"):
        sys.exit(__doc__)
    root = pathlib.Path(sys.argv[2])
    value, rows = digest(root)
    if sys.argv[1] == "seal":
        print(f"holdout digest: {value}")
        print(f"files: {len(rows)}")
        return
    want = sys.argv[3] if len(sys.argv) > 3 else ""
    if value != want:
        sys.exit(f"MISMATCH: {root} digests to {value}, expected {want}")
    print(f"verified: {len(rows)} files reproduce {value}")


if __name__ == "__main__":
    main()
