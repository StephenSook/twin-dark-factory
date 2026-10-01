#!/bin/sh
# Prove a complete-looking summary cannot hide a failed isolated harness process.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$T"' EXIT

SRC="$T/source"
mkdir -p "$SRC/stage-1" "$SRC/mandates" "$T/kickoff" "$T/bin"
printf 'FROM scratch\n' > "$SRC/stage-1/Dockerfile"
printf 'run\n' > "$SRC/stage-1/RUN.md"
printf 'Harness: test\n' > "$SRC/mandates/builder.md"
printf '{}\n' > "$SRC/room.json"
git -C "$SRC" init -q -b main
git -C "$SRC" add stage-1/Dockerfile stage-1/RUN.md mandates/builder.md room.json
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
