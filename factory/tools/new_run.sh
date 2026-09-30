#!/usr/bin/env bash
# Create a fresh result repository for one run and point the seats at it.
#   new_run.sh <run-name> [--no-link]
# The only commit is the human's root commit holding mandates/. The commit guard is installed
# before anything else can commit. Refuses to reuse an existing name.
set -euo pipefail
NAME=$1
W=${WORK:-/home/ubuntu/work}
R=$W/band-work/$NAME
[ -e "$R" ] && { echo "refusing: $R already exists"; exit 1; }
MANDATES=${MANDATES:-$W/factory/mandates}   # the baseline run uses factory/baseline
# Every committed mandate becomes an authorized commit author, so copy exactly the declared seats.
if [ "$MANDATES" = "$W/factory/mandates" ]; then
  SEATS=$(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))))' "$W/factory/seats.json")
else
  SEATS=$(cd "$MANDATES" && ls *.md | sed 's/\.md$//' | tr '\n' ' ')
fi
[ -n "$SEATS" ] || { echo "refusing: no seats declared"; exit 1; }
present=$(cd "$MANDATES" && ls *.md | sed 's/\.md$//' | sort | tr '\n' ' ')
declared=$(printf '%s\n' $SEATS | sort | tr '\n' ' ')
[ "$present" = "$declared" ] || { echo "refusing: $MANDATES has [$present], seats are [$declared]"; exit 1; }
mkdir -p "$R/mandates" "$W/band-work/checks/$NAME"
for s in $SEATS; do cp "$MANDATES/$s.md" "$R/mandates/"; done
cd "$R"
git init -q -b main
mkdir -p .git/factory
chmod 700 .git/factory
git config user.name "Stephen Sookra"
git config user.email "stephensookra@gmail.com"
cp "$W/factory/tools/pre-commit" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
git add mandates
git commit -q -m "Set up result repository: seat mandates"
if [ "${2:-}" != "--no-link" ]; then
  ln -sfn "$NAME" "$W/band-work/current"
fi
echo "repo:    $R ($(git rev-parse --short HEAD))"
echo "current: $(readlink "$W/band-work/current")"
sha256sum mandates/*.md | cut -c1-12 | tr '\n' ' '; echo
