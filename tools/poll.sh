#!/bin/bash
# Poll a view until it answers something other than the "not yet" shape.
# studio-dev settles a render-heavy round in minutes, not seconds, and a CLI
# that returns before the round decides reports a stale read as a result.
cd "$(dirname "$0")/.."
ADDR="$1"; METHOD="$2"; ARG="$3"; NEEDLE="${4:-found: true}"; TRIES="${5:-60}"
for i in $(seq 1 "$TRIES"); do
  OUT=$(genlayer call "$ADDR" "$METHOD" ${ARG:+--args "$ARG"} 2>/dev/null)
  if echo "$OUT" | grep -q "$NEEDLE"; then
    echo "$OUT"
    exit 0
  fi
  sleep 10
done
echo "TIMED OUT after $((TRIES*10))s"
genlayer call "$ADDR" "$METHOD" ${ARG:+--args "$ARG"} 2>/dev/null
exit 1
