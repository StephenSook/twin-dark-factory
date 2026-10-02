#!/bin/sh
# Prove a complete-looking summary cannot hide a failed isolated harness process.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$T"' EXIT

SRC="$T/source"
mkdir -p "$SRC/stage-1" "$SRC/mandates" "$SRC/evidence" "$T/kickoff" "$T/bin"
printf 'FROM scratch\n' > "$SRC/stage-1/Dockerfile"
printf 'run\n' > "$SRC/stage-1/RUN.md"
printf 'Harness: test\n' > "$SRC/mandates/builder.md"
printf '# result\n' > "$SRC/README.md"
printf '# factory\n' > "$SRC/FACTORY.md"
printf '# judge\n' > "$SRC/JUDGE-GUIDE.md"
printf '{"events":[]}\n' > "$SRC/evidence/floor.json"
python3 - "$SRC/room.json" "$SRC/evidence/claim-evidence.json" <<'PY'
import json, pathlib, sys
specs = [
    ("executable_model", "modeler", "The executable model covered the accepted operations."),
    ("differential_comparison", "gatekeeper", "The differential comparison matched every sampled operation."),
    ("concurrency_probe", "gatekeeper", "The concurrency probe completed with fifty overlapping requests."),
    ("planted_fault", "gatekeeper", "The planted fault was detected before the clean rerun."),
    ("third_family_audit", "auditor", "The independent audit found no behaviour-changing misreading."),
]
messages, claims = [], []
for number, (claim_id, sender, quote) in enumerate(specs, start=1):
    message_id = f"{number:08x}-0000-4000-8000-{number:012x}"
    messages.append({"id": message_id, "messageType": "text", "senderType": "Agent",
                     "senderName": sender, "content": quote})
    claims.append({"id": claim_id, "room_message_id": message_id,
                   "sender": sender, "quote": quote})
pathlib.Path(sys.argv[1]).write_text(json.dumps({"messages": messages}))
pathlib.Path(sys.argv[2]).write_text(json.dumps({"claims": claims}))
PY
git -C "$SRC" init -q -b main
git -C "$SRC" add stage-1/Dockerfile stage-1/RUN.md mandates/builder.md room.json \
  README.md FACTORY.md JUDGE-GUIDE.md evidence/claim-evidence.json evidence/floor.json
git -C "$SRC" -c user.name=builder -c user.email=builder@band.local commit -q -m fixture

cat > "$T/bin/fake-python" <<'EOF'
#!/bin/sh
if [ "$1" = "-" ]; then
  exec python3 "$@"
fi
case " $* " in
  *" -m harness check "*) exit 0 ;;
  *" -m harness run "*)
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--out" ]; then out=$2; break; fi
      shift
    done
    mkdir -p "$out"
    printf '{"folders":{"1":{"claimed":true,"share":1}}}\n' > "$out/summary.json"
    exit "${FAKE_RUN_STATUS:-0}"
    ;;
  *"check_room.py"*) exit 0 ;;
  *"check_claim_evidence.py"*) exec python3 "$@" ;;
  *"check_public_copy.py"*) exit "${FAKE_PUBLIC_COPY_STATUS:-0}" ;;
esac
echo "unexpected fake-python arguments: $*" >&2
exit 97
EOF
chmod +x "$T/bin/fake-python"
cat > "$T/bin/gitleaks" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$T/bin/gitleaks"

if PATH="$T/bin:$PATH" PYTHON="$T/bin/fake-python" FAKE_RUN_STATUS=23 \
  bash "$HERE/verify_result.sh" "$SRC" "$T/kickoff" pocketful 1 > "$T/fail.log" 2>&1; then
  echo "FAIL nonzero harness process was accepted"
  exit 1
fi
grep -q 'FAIL  isolated harness process exited 23' "$T/fail.log" || {
  cat "$T/fail.log"
  exit 1
}
echo "ok   nonzero harness process is refused even with a valid summary"

PATH="$T/bin:$PATH" PYTHON="$T/bin/fake-python" FAKE_RUN_STATUS=0 \
  bash "$HERE/verify_result.sh" "$SRC" "$T/kickoff" pocketful 1 > "$T/pass.log" 2>&1
grep -q 'RESULT PASS' "$T/pass.log"
echo "ok   zero harness process with a valid summary is accepted"

if PATH="$T/bin:$PATH" PYTHON="$T/bin/fake-python" FAKE_RUN_STATUS=0 \
  FAKE_PUBLIC_COPY_STATUS=31 \
  bash "$HERE/verify_result.sh" "$SRC" "$T/kickoff" pocketful 1 > "$T/bad-public-copy.log" 2>&1; then
  echo "FAIL a failing public copy check was ignored"
  exit 1
fi
grep -q 'RESULT FAIL' "$T/bad-public-copy.log"
echo "ok   a failing public copy check fails result verification"

mv "$SRC/evidence/floor.json" "$T/floor.json"
git -C "$SRC" add -u evidence/floor.json
git -C "$SRC" -c user.name=builder -c user.email=builder@band.local commit -q -m remove-floor
if PATH="$T/bin:$PATH" PYTHON="$T/bin/fake-python" FAKE_RUN_STATUS=0 \
  bash "$HERE/verify_result.sh" "$SRC" "$T/kickoff" pocketful 1 > "$T/no-floor.log" 2>&1; then
  echo "FAIL a result without floor evidence passed the copy check"
  exit 1
fi
grep -q 'FAIL  tools/check_public_copy.py or evidence/floor.json missing' "$T/no-floor.log"
echo "ok   judged result without the copy check inputs is refused"
mv "$T/floor.json" "$SRC/evidence/floor.json"
git -C "$SRC" add evidence/floor.json
git -C "$SRC" -c user.name=builder -c user.email=builder@band.local commit -q -m put-floor-back

mv "$SRC/evidence/claim-evidence.json" "$T/claim-evidence.json"
git -C "$SRC" add -u evidence/claim-evidence.json
git -C "$SRC" -c user.name=builder -c user.email=builder@band.local commit -q -m remove-claim-evidence
if PATH="$T/bin:$PATH" PYTHON="$T/bin/fake-python" FAKE_RUN_STATUS=0 \
  bash "$HERE/verify_result.sh" "$SRC" "$T/kickoff" pocketful 1 > "$T/no-claims.log" 2>&1; then
  echo "FAIL missing public-claim evidence was accepted"
  exit 1
fi
grep -q 'FAIL  evidence/claim-evidence.json or tools/check_claim_evidence.py missing' "$T/no-claims.log"
echo "ok   judged result without public-claim evidence is refused"
