#!/bin/sh
# seal_holdout.py must verify an untouched folder, reject a one-byte change and refuse an empty folder.
set -u
TOOL="$(cd "$(dirname "$0")" && pwd)/seal_holdout.py"
T=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$T"' EXIT
mkdir -p "$T/h/sub" "$T/empty"
printf 'check one\n' > "$T/h/a.py"; printf 'check two\n' > "$T/h/sub/b.py"
D=$(python3 "$TOOL" seal "$T/h" | awk '/digest/{print $3}')
fail=0
python3 "$TOOL" verify "$T/h" "$D" >/dev/null 2>&1 && echo "ok   untouched folder verifies" || { echo "FAIL untouched folder"; fail=1; }
printf ' ' >> "$T/h/a.py"
python3 "$TOOL" verify "$T/h" "$D" >/dev/null 2>&1 && { echo "FAIL tamper not caught"; fail=1; } || echo "ok   one-byte change is rejected"
python3 "$TOOL" seal "$T/empty" >/dev/null 2>&1 && { echo "FAIL empty folder sealed"; fail=1; } || echo "ok   empty folder is refused"
exit $fail
