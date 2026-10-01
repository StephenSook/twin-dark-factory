#!/bin/sh
# Require the complete private design kit to match the manifest produced by sync-design-kit.sh.
set -eu
[ "$#" = 2 ] || { echo "usage: check_design_kit.sh <kit-dir> <manifest>" >&2; exit 2; }
kit=$1 manifest=$2
[ -d "$kit" ] || { echo "design kit directory missing" >&2; exit 3; }
[ -s "$manifest" ] || { echo "design kit manifest missing or empty" >&2; exit 4; }
python3 - "$manifest" <<'PY'
import pathlib
import re
import sys

names = []
for number, line in enumerate(pathlib.Path(sys.argv[1]).read_text().splitlines(), 1):
    match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
    if match is None:
        raise SystemExit(f"invalid manifest row {number}")
    name = match.group(2)
    path = pathlib.PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or name.startswith("./"):
        raise SystemExit(f"unsafe manifest path on row {number}")
    names.append(name)
if len(names) != len(set(names)):
    raise SystemExit("manifest contains duplicate paths")
PY
want=$(wc -l < "$manifest" | tr -d ' ')
have=$(find "$kit" -type f | wc -l | tr -d ' ')
[ "$have" = "$want" ] || { echo "design kit file count differs: manifest=$want directory=$have" >&2; exit 5; }
(cd "$kit" && sha256sum -c "$manifest" >/dev/null)
echo "design kit matches $want-file sha256 manifest"
