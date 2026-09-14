#!/bin/bash
# Pull a whole rendered page out of the probe, one 9000-char window at a time,
# and save it as an offline fixture. The scoring tests then run against text a
# validator ACTUALLY saw, not against text this project invented — which is the
# only way an offline test can say anything about on-chain behaviour.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROBE="${PROBE:-0x183a0f7B71f83045aD25Bdb520FD10646c474b79}"
URL="$1"; NAME="$2"; TOTAL="$3"
OUT="$ROOT/test/fixtures/$NAME.txt"
: > "$OUT.parts"
POS=0
while [ "$POS" -lt "$TOTAL" ]; do
  "$ROOT/tools/gl.sh" write "$PROBE" probe_window --args "$URL" "$POS" 9000 '6s' true >/dev/null 2>&1
  "$ROOT/tools/read.sh" "$PROBE" read_window | python3 -c "
import json,sys
d=json.loads(sys.stdin.read().strip())
w=d['window']
i=w.rfind(' || {\"mode\"')
sys.stdout.write(w[:i] if i>=0 else w)
" >> "$OUT.parts"
  echo "  window $POS/$TOTAL" >&2
  POS=$((POS+9000))
done
mv "$OUT.parts" "$OUT"
wc -c "$OUT"
