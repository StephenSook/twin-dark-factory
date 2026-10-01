#!/bin/sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$T"' EXIT
mkdir "$T/kit"
printf 'brief\n' > "$T/kit/BRIEF.md"
printf 'image\n' > "$T/kit/reference.jpg"
(cd "$T/kit" && find . -type f -print0 | sort -z | xargs -0 shasum -a 256) \
  | sed 's#  \./#  #' > "$T/manifest"
sh "$HERE/check_design_kit.sh" "$T/kit" "$T/manifest" >/dev/null
echo "ok   exact design kit passes"

printf 'changed\n' > "$T/kit/reference.jpg"
if sh "$HERE/check_design_kit.sh" "$T/kit" "$T/manifest" >/dev/null 2>&1; then
  echo "FAIL changed file passed"; exit 1
fi
echo "ok   changed design file fails"
printf 'image\n' > "$T/kit/reference.jpg"

printf 'extra\n' > "$T/kit/extra.jpg"
if sh "$HERE/check_design_kit.sh" "$T/kit" "$T/manifest" >/dev/null 2>&1; then
  echo "FAIL extra file passed"; exit 1
fi
echo "ok   extra design file fails"
python3 -c 'import pathlib; pathlib.Path("'$T'/kit/extra.jpg").unlink()'

printf '%064d  ../escape\n' 0 > "$T/bad-manifest"
if sh "$HERE/check_design_kit.sh" "$T/kit" "$T/bad-manifest" >/dev/null 2>&1; then
  echo "FAIL unsafe manifest passed"; exit 1
fi
echo "ok   unsafe manifest path fails"
