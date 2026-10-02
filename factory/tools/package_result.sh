#!/usr/bin/env bash
# Package measured evidence outside stage folders. The band remains the only writer of stage code.
# package_result.sh <result-repo> <room.json> <usage-sessions.json> <facts.json> <claim-evidence.json> <public-claims.json>
set -euo pipefail

[ "$#" = 6 ] || { echo "usage: package_result.sh <result-repo> <room.json> <usage-sessions.json> <facts.json> <claim-evidence.json> <public-claims.json>" >&2; exit 2; }
RESULT=$(cd "$1" && pwd)
ROOM=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$2")
SESSIONS=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$3")
FACTS=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$4")
CLAIMS=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$5")
PUBLIC_CLAIMS=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$6")
HERE=$(cd "$(dirname "$0")" && pwd)
FACTORY=$(cd "$HERE/.." && pwd)

git -C "$RESULT" rev-parse --is-inside-work-tree >/dev/null
for path in "$ROOM" "$SESSIONS" "$FACTS" "$CLAIMS" "$PUBLIC_CLAIMS"; do
  [ -f "$path" ] || { echo "missing input: $path" >&2; exit 1; }
done
[ -z "$(git -C "$RESULT" status --porcelain -- 'stage-*')" ] || {
  echo "refusing: stage folders have uncommitted changes" >&2
  exit 1
}

mkdir -p "$RESULT/tools" "$RESULT/docs" "$RESULT/evidence" "$RESULT/floor" \
  "$RESULT/deploy" "$RESULT/.github/workflows"

copy_file() {
  src=$1 dst=$2 mode=${3:-0644}
  [ "$src" = "$dst" ] || install -m "$mode" "$src" "$dst"
}

copy_file "$ROOM" "$RESULT/room.json"
copy_file "$SESSIONS" "$RESULT/evidence/usage-sessions.json"
copy_file "$FACTS" "$RESULT/evidence/facts.json"
copy_file "$CLAIMS" "$RESULT/evidence/claim-evidence.json"
copy_file "$PUBLIC_CLAIMS" "$RESULT/evidence/public-claims.json"

for name in check_room.py check_claim_evidence.py check_public_claims.py floor_data.py factory_md.py judge_guide.py result_readme.py; do
  copy_file "$FACTORY/tools/$name" "$RESULT/tools/$name"
done
copy_file "$FACTORY/tools/verify_result.sh" "$RESULT/tools/verify_result.sh" 0755
copy_file "$FACTORY/docs/FACTORY.template.md" "$RESULT/docs/FACTORY.template.md"
for name in index.html style.css app.js; do
  copy_file "$FACTORY/floor/$name" "$RESULT/floor/$name"
done
for name in Dockerfile render.Dockerfile README.md proxy.py seed.json; do
  copy_file "$FACTORY/deploy/$name" "$RESULT/deploy/$name"
done
copy_file "$FACTORY/result-ci/verify.yml" "$RESULT/.github/workflows/verify.yml"
copy_file "$FACTORY/result-ci/demo-image.yml" "$RESULT/.github/workflows/demo-image.yml"
copy_file "$FACTORY/result-ci/pages.yml" "$RESULT/.github/workflows/pages.yml"

stage_count=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["stage_claims"]))' "$RESULT/evidence/facts.json")
python3 "$RESULT/tools/check_room.py" "$RESULT/room.json" --expected-accepts "$stage_count"
python3 "$RESULT/tools/check_claim_evidence.py" \
  "$RESULT/room.json" "$RESULT/evidence/claim-evidence.json"
python3 "$RESULT/tools/floor_data.py" \
  "$RESULT/room.json" "$RESULT" "$RESULT/evidence/floor.json"
python3 "$RESULT/tools/result_readme.py" \
  "$RESULT/evidence/floor.json" "$RESULT/evidence/facts.json" > "$RESULT/README.md"
python3 "$RESULT/tools/factory_md.py" \
  --repo "$RESULT" --room "$RESULT/room.json" \
  --floor "$RESULT/evidence/floor.json" \
  --sessions "$RESULT/evidence/usage-sessions.json" \
  --facts "$RESULT/evidence/facts.json" \
  --template "$RESULT/docs/FACTORY.template.md" > "$RESULT/FACTORY.md"
python3 "$RESULT/tools/judge_guide.py" \
  "$RESULT/evidence/floor.json" "$RESULT/evidence/facts.json" > "$RESULT/JUDGE-GUIDE.md"
python3 "$RESULT/tools/check_public_claims.py" \
  --evidence-root "$RESULT" --allow-absent "$RESULT/evidence/public-claims.json" \
  "$RESULT/README.md" "$RESULT/FACTORY.md" "$RESULT/JUDGE-GUIDE.md" \
  "$RESULT/floor/index.html" "$RESULT/deploy/README.md"

recomputed=$(mktemp)
trap 'python3 -c "import os,sys; os.unlink(sys.argv[1]) if os.path.exists(sys.argv[1]) else None" "$recomputed"' EXIT
python3 "$RESULT/tools/floor_data.py" "$RESULT/room.json" "$RESULT" "$recomputed"
cmp "$recomputed" "$RESULT/evidence/floor.json"

git -C "$RESULT" add README.md FACTORY.md JUDGE-GUIDE.md room.json \
  docs/FACTORY.template.md evidence/floor.json evidence/usage-sessions.json \
  evidence/facts.json evidence/claim-evidence.json evidence/public-claims.json floor deploy tools \
  .github/workflows/verify.yml .github/workflows/demo-image.yml \
  .github/workflows/pages.yml
git -C "$RESULT" diff --cached --check
if git -C "$RESULT" diff --cached --name-only | while IFS= read -r path; do
  case "$path" in stage-[0-9]*) exit 1;; esac
done; then
  :
else
  echo "refusing: packaging staged a stage folder" >&2
  exit 1
fi

echo "PASS  packaged measured result evidence without touching stage folders"
echo "INFO  inspect the staged files, then commit them as the human owner"
