#!/usr/bin/env bash
# Create a fresh result repository for one run and point the seats at it.
#   new_run.sh <run-name> [--no-link]
# The only commit is the human's root commit holding mandates/. The commit guard is installed
# before anything else can commit. Refuses to reuse an existing name.
set -euo pipefail
NAME=$1
W=/home/ubuntu/work
R=$W/band-work/$NAME
[ -e "$R" ] && { echo "refusing: $R already exists"; exit 1; }
mkdir -p "$R/mandates" "$W/band-work/checks/$NAME"
cp "$W"/factory/mandates/*.md "$R/mandates/"
cd "$R"
git init -q -b main
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
