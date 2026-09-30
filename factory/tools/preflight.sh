#!/usr/bin/env bash
# Pre-dispatch preflight on the factory machine. Run right before the one dispatch of a judged run.
# Every line is PASS or FAIL; exit 1 on any FAIL. Nothing here changes state.
#
#   preflight.sh <result repo> <factory dir> <kickoff dir> <dispatch file> [seats...]
set -u
REPO=$1 FACTORY=$2 KICKOFF=$3 DISPATCH=$4; shift 4
SEATS=${*:-$(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))))' "$FACTORY/seats.json")}
[ -n "$SEATS" ] || { echo "FAIL  no seats (seats.json unreadable?)"; exit 1; }
fails=0
pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; fails=$((fails + 1)); }
chk() { local label=$1; shift; if "$@" >/dev/null 2>&1; then pass "$label"; else fail "$label"; fi; }

# Machine
free_gb=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
[ "$free_gb" -ge 20 ] && pass "disk free ${free_gb} GB (>= 20)" || fail "disk free ${free_gb} GB (< 20)"
chk "docker daemon answers" docker info
chk "docker can create an internal network" sh -c 'n=pf-$$; docker network create --internal $n && docker network rm $n'
chk "harness runs from the kickoff environment" sh -c "cd '$KICKOFF' && .venv/bin/python -m harness --help"
junk=$(find "$FACTORY" "$REPO" -name '._*' 2>/dev/null | wc -l | tr -d ' ')
[ "$junk" = 0 ] && pass "no macOS metadata files (._*) in factory or result repo" \
  || fail "$junk macOS metadata files (._*): copy with COPYFILE_DISABLE=1"

# Seats
listed=$(jam list 2>/dev/null)
for s in $SEATS; do
  echo "$listed" | grep -q "/$s \[$s\] Connected" && pass "seat $s connected" || fail "seat $s not connected"
done

# Mandates: the files the seats read are the committed ones, and generic.
for s in $SEATS; do
  a=$(sha256sum "$FACTORY/mandates/$s.md" 2>/dev/null | cut -c1-64)
  b=$(sha256sum "$REPO/mandates/$s.md" 2>/dev/null | cut -c1-64)
  [ -n "$a" ] && [ "$a" = "$b" ] && pass "mandate $s identical in factory and result repo" \
    || fail "mandate $s differs between factory and result repo"
  head -2 "$FACTORY/mandates/$s.md" | grep -q '^Harness:' && head -3 "$FACTORY/mandates/$s.md" | grep -q '^Model:' \
    && pass "mandate $s starts with Harness and Model lines" || fail "mandate $s header lines"
done
chk "mandate vocabulary lint" python3 "$FACTORY/tools/lint_mandates.py" "$KICKOFF" "$FACTORY/mandates"
# The commit guard authorizes every committed mandate, so that set must be exactly the seats.
want=$(printf '%s\n' $SEATS | sort | tr '\n' ' ')
have=$(git -C "$REPO" ls-tree --name-only HEAD mandates/ 2>/dev/null | sed -n 's#^mandates/\(.*\)\.md$#\1#p' | sort | tr '\n' ' ')
[ "$have" = "$want" ] && pass "committed mandates are exactly the seats ($have)" \
  || fail "committed mandates [$have] differ from seats [$want]"

# Result repository: fresh, one human root commit, guard installed, seats will work in it.
n=$(git -C "$REPO" rev-list --count HEAD 2>/dev/null || echo 0)
[ "$n" = 1 ] && pass "result repo has exactly the root commit" || fail "result repo has $n commits (want 1)"
stages=$(ls -d "$REPO"/stage-* 2>/dev/null | wc -l | tr -d ' ')
[ "$stages" = 0 ] && pass "no stage folders yet" || fail "$stages stage folders already exist"
[ -z "$(git -C "$REPO" status --porcelain)" ] && pass "result repo tree clean" || fail "result repo has uncommitted changes"
cmp -s "$FACTORY/tools/pre-commit" "$REPO/.git/hooks/pre-commit" && [ -x "$REPO/.git/hooks/pre-commit" ] \
  && pass "commit guard installed and current" || fail "commit guard missing or stale"
[ "$(readlink -f /home/ubuntu/work/band-work/current)" = "$(readlink -f "$REPO")" ] \
  && pass "seat working directory points at the result repo" || fail "current -> $(readlink -f /home/ubuntu/work/band-work/current)"

# Seat accounts and billing
python3 -c "import json,sys;d=json.load(open('$HOME/.claude/settings.json'));sys.exit(0 if d.get('includeCoAuthoredBy') is False and (d.get('attribution') or {}).get('commit')=='' else 1)" \
  && pass "Claude seats add no co-author trailers" || fail "Claude co-author trailers not disabled"
for v in ANTHROPIC_API_KEY OPENAI_API_KEY; do
  [ -z "${!v:-}" ] && pass "$v unset (seats stay on subscriptions)" || fail "$v is set"
done

# Inputs
[ -f "$DISPATCH" ] && pass "dispatch file present ($(sha256sum "$DISPATCH" | cut -c1-12))" || fail "dispatch file missing"
[ -f /home/ubuntu/work/design-kit/BRIEF.md ] && pass "design kit present" || fail "design kit missing"

# Headroom: a full run used about 35% of the Codex week.
cx=$(python3 - <<'EOF'
import json, glob, os
fs = sorted(glob.glob(os.path.expanduser('~/.codex/sessions/*/*/*/*.jsonl')), key=os.path.getmtime)
last = None
for f in fs[-3:]:
    for l in open(f):
        if '"used_percent"' in l:
            last = json.loads(l)['payload']['rate_limits']['primary']['used_percent']
print(last if last is not None else -1)
EOF
)
awk "BEGIN{exit !($cx >= 0 && $cx < 60)}" && pass "Codex weekly usage ${cx}% (< 60)" || fail "Codex weekly usage ${cx}% (want < 60)"
echo "NOTE  check Claude weekly usage by hand at claude.ai/settings/usage before dispatching"

[ "$fails" = 0 ] && { echo "RESULT PASS"; exit 0; } || { echo "RESULT FAIL ($fails)"; exit 1; }
