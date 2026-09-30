#!/bin/sh
# Mutation test for check_dispatch.py and build_dispatch.py: a clean copy passes, every planted
# disagreement fails. Run from the repository root.
set -u
SRC=$(pwd)
PY=${PYTHON:-python3}
fails=0

fresh() {
  D=$(mktemp -d)
  (cd "$SRC" && git ls-files -z | xargs -0 tar -cf - ) | (cd "$D" && tar -xf -)
  (cd "$D" && git init -q && git config user.name t && git config user.email t@t && git add -A && git commit -q -m base)
  echo "$D"
}

expect() {  # expect <pass|fail> <label> <dir>
  if (cd "$3" && $PY factory/tools/check_dispatch.py > "$3/.out" 2>&1); then got=pass; else got=fail; fi
  if [ "$got" = "$1" ]; then echo "ok   $2 ($got)"; else echo "BAD  $2 (want $1, got $got)"; cat "$3/.out"; fails=$((fails+1)); fi
}

D=$(fresh); expect pass "clean copy" "$D"
D=$(fresh); (cd "$D" && git rm -q factory/mandates/auditor.md && git commit -q -m x); expect fail "committed mandate deleted" "$D"
D=$(fresh); (cd "$D" && cp factory/mandates/builder.md factory/mandates/extra.md && git add factory/mandates/extra.md && git commit -q -m x); expect fail "extra committed mandate" "$D"
D=$(fresh); sed -i.b '/^- @stephensookra\/gatekeeper$/d' "$D/factory/dispatch/pocketful-judged.md"; expect fail "gatekeeper missing from Band block" "$D"
D=$(fresh); sed -i.b 's/, gatekeeper or auditor\./ or gatekeeper./' "$D/factory/dispatch/tablekeeper-gen1.md"; expect fail "auditor missing from authors" "$D"
D=$(fresh); sed -i.b 's#/pocketful/spec#/{Track}/spec#' "$D/factory/dispatch/pocketful-judged.md"; expect fail "stray placeholder" "$D"
D=$(fresh); printf '{"coordinator": {}' > "$D/factory/seats.json"; expect fail "unreadable seats.json" "$D"

D=$(fresh); sed -i.b 's/{TRACK}/{TRACK1}/' "$D/factory/dispatch/template.md"
if (cd "$D" && $PY factory/tools/build_dispatch.py pocketful x > /dev/null 2>&1); then echo "BAD  generator accepted {TRACK1}"; fails=$((fails+1)); else echo "ok   generator refuses {TRACK1}"; fi
D=$(fresh); sed -i.b 's/{TRACK}/{Track}/' "$D/factory/dispatch/template.md"
if (cd "$D" && $PY factory/tools/build_dispatch.py pocketful x > /dev/null 2>&1); then echo "BAD  generator accepted {Track}"; fails=$((fails+1)); else echo "ok   generator refuses {Track}"; fi

echo "failures: $fails"
[ "$fails" -eq 0 ]
