#!/bin/bash
# Every deploy and every write goes through here, so that fee estimation is not
# something to remember. studio-dev rejects a transaction whose fee distribution
# is absent with `FeeValueMustBeNonZero(1)` — the CLI's --fee-value alone is not
# enough, the distribution object must travel with it. Measured, not assumed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="$ROOT/.feecache.json"

fees_json() {
  if [ ! -s "$CACHE" ]; then
    genlayer estimate-fees --json 2>/dev/null | tail -1 > "$CACHE"
  fi
  python3 -c "
import json,io,sys
d=json.load(io.open('$CACHE'))
print(json.dumps({'distribution':d['distribution']}))
"
}

fee_value() {
  python3 -c "
import json,io
d=json.load(io.open('$CACHE'))
print(d['feeValue'])
"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  deploy)
    D=$(fees_json); V=$(fee_value)
    exec genlayer deploy --contract "$1" --fees "$D" --fee-value "$V" "${@:2}"
    ;;
  write)
    D=$(fees_json); V=$(fee_value)
    ADDR="$1"; METHOD="$2"; shift 2
    exec genlayer write "$ADDR" "$METHOD" --fees "$D" --fee-value "$V" "$@"
    ;;
  fees)
    fees_json
    ;;
  *)
    echo "usage: gl.sh {deploy <file>|write <addr> <method> [--args ...]|fees}" >&2
    exit 2
    ;;
esac
