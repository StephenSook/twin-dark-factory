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
  [ -f "$D/factory/tools/check_dispatch.py" ] || { echo "BAD  copy is missing files"; exit 1; }
  echo "$D"
}

regen() {  # regenerate every listed dispatch in copy $1 from its template (as a careless edit would)
  (cd "$1" && $PY - <<'EOF'
import json, subprocess, sys
runs = json.load(open("factory/dispatch/runs.json"))
for run, args in runs.items():
    out = subprocess.run([sys.executable, "factory/tools/build_dispatch.py", *args], capture_output=True, text=True)
    if out.returncode == 0:
        open(f"factory/dispatch/{run}.md", "w").write(out.stdout)
EOF
  )
}

expect() {  # expect <pass|fail> <label> <dir>
  if (cd "$3" && $PY factory/tools/check_dispatch.py > "$3/.out" 2>&1); then got=pass; else got=fail; fi
  if [ "$got" = "$1" ]; then echo "ok   $2 ($got)"; else echo "BAD  $2 (want $1, got $got)"; cat "$3/.out"; fails=$((fails+1)); fi
}

D=$(fresh); expect pass "clean copy" "$D"
D=$(fresh); (cd "$D" && git rm -q factory/mandates/auditor.md && git commit -q -m x); expect fail "committed mandate deleted" "$D"
D=$(fresh); (cd "$D" && cp factory/mandates/builder.md factory/mandates/extra.md && git add factory/mandates/extra.md && git commit -q -m x); expect fail "extra committed mandate" "$D"
D=$(fresh); sed -i.b '/^- @stephensookra\/gatekeeper$/d' "$D/factory/dispatch/pocketful-judged.md"; rm "$D"/factory/dispatch/*.b; expect fail "gatekeeper removed from a dispatch" "$D"
D=$(fresh); sed -i.b 's/, gatekeeper or auditor\./ or gatekeeper./' "$D/factory/dispatch/tablekeeper-gen1.md"; rm "$D"/factory/dispatch/*.b; expect fail "auditor removed from authors" "$D"
D=$(fresh); sed -i.b 's#/pocketful/spec#/{Track}/spec#' "$D/factory/dispatch/pocketful-judged.md"; rm "$D"/factory/dispatch/*.b; expect fail "stray placeholder in a dispatch" "$D"
D=$(fresh); printf '{"coordinator": {}' > "$D/factory/seats.json"; expect fail "unreadable seats.json" "$D"
D=$(fresh); cp "$D/factory/dispatch/tablekeeper-gen1.md" "$D/factory/dispatch/unlisted-run.md"; expect fail "unlisted dispatch file" "$D"
D=$(fresh); rm "$D/factory/dispatch/tablekeeper-gen1.md"; expect fail "listed dispatch missing" "$D"
D=$(fresh); $PY - "$D/factory/dispatch/template.md" <<'EOF'
import sys; p = sys.argv[1]; s = open(p).read()
open(p, "w").write(s.replace("{BAND}\n\n", "{BAND}\n\n- @stephensookra/solo\n\n", 1))
EOF
regen "$D"; expect fail "extra handle after a blank line, regenerated" "$D"
D=$(fresh); sed -i.b 's/{TRACK}/TRACK/' "$D/factory/dispatch/template.md"; rm "$D"/factory/dispatch/*.b; regen "$D"; expect fail "braces stripped from one {TRACK}, regenerated" "$D"
D=$(fresh); sed -i.b 's/run every suite through N/skip every suite through N/' "$D/factory/dispatch/template.md"; rm "$D"/factory/dispatch/*.b; regen "$D"; expect fail "current-stage applicability rule inverted, regenerated" "$D"
D=$(fresh); sed -i.b 's/Run the next suite/Skip the next suite/' "$D/factory/dispatch/template.md"; rm "$D"/factory/dispatch/*.b; regen "$D"; expect fail "next-stage applicability rule inverted, regenerated" "$D"
D=$(fresh); sed -i.b 's/Record an explicit exemption/Never record an explicit exemption/' "$D/factory/dispatch/template.md"; rm "$D"/factory/dispatch/*.b; regen "$D"; expect fail "explicit exemption rule inverted, regenerated" "$D"
D=$(fresh); sed -i.b 's/Never add a defect just to make a later suite fail\./Add a defect to make a later suite fail./' "$D/factory/dispatch/template.md"; rm "$D"/factory/dispatch/*.b; regen "$D"; expect fail "no-defect rule inverted, regenerated" "$D"

for bad in '{TRACK1}' '{Track}' 'TRACK'; do
  D=$(fresh); sed -i.b "s/{TRACK}/$bad/" "$D/factory/dispatch/template.md"
  if (cd "$D" && $PY factory/tools/build_dispatch.py pocketful x > /dev/null 2>&1); then echo "BAD  generator accepted $bad"; fails=$((fails+1)); else echo "ok   generator refuses $bad"; fi
done

echo "failures: $fails"
[ "$fails" -eq 0 ]
