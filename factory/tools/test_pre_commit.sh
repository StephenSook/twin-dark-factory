#!/bin/sh
# Proves the result-repository guard both ways: bad commits are refused, a seat commit inside a
# stage folder is accepted. Exits non-zero on the first unexpected outcome.
set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/pre-commit"
T=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$T"' EXIT
cd "$T" && git init -q -b main && cp "$HOOK" .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
fail=0
expect() { # expect <refuse|accept> <label> <git args...>
  want=$1; label=$2; shift 2
  if git "$@" commit -q -m probe >/dev/null 2>&1; then got=accept; git reset -q --soft HEAD~1 2>/dev/null || git update-ref -d HEAD; else got=refuse; fi
  if [ "$got" = "$want" ]; then echo "ok   $label ($got)"; else echo "FAIL $label (wanted $want, got $got)"; fail=1; fi
}
seat="-c user.name=builder -c user.email=builder@band.local"

echo x > root.txt && git add root.txt
expect refuse "non-seat author" -c user.name=mallory -c user.email=m@x
# shellcheck disable=SC2086
expect refuse "seat outside stage folders" $seat
git reset -q root.txt

mkdir -p stage-1/inner && (cd stage-1/inner && git init -q && git -c user.name=a -c user.email=a@a commit -q --allow-empty -m x)
git add stage-1/inner 2>/dev/null
# shellcheck disable=SC2086
expect refuse "nested repository" $seat
git rm -q -f --cached stage-1/inner

mkdir -p stage-1/__pycache__ && echo b > stage-1/__pycache__/a.pyc && git add -f stage-1/__pycache__/a.pyc
# shellcheck disable=SC2086
expect refuse "bytecode cache" $seat
git rm -q --cached stage-1/__pycache__/a.pyc

echo ok > stage-1/app.py && git add stage-1/app.py
# shellcheck disable=SC2086
expect accept "seat inside a stage folder" $seat
expect accept "human owner" -c user.name="Stephen Sookra" -c user.email=owner@example.com
exit $fail
