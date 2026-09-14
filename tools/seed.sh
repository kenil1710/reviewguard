#!/bin/bash
# Seed studio-dev with real checks.
#
# Two things make this slower than it looks and both are the contract working:
#   * RATE_LIMIT_SECONDS is 300 PER WALLET, so the accounts alternate and the
#     script waits out the remainder rather than collecting refunds;
#   * a render-heavy round takes minutes to settle, so each submission is
#     followed by a poll rather than a fixed sleep.
set -uo pipefail
cd "$(dirname "$0")/.."
GUARD="${GUARD:-0xc5fdA37427Ba24E0A35B446cBEf7a2C5E7EE61b3}"
# Only `mywallet` is funded on studio-dev, so every check comes from it and the
# script waits out RATE_LIMIT_SECONDS between submissions. That wait is the
# contract's anti-abuse rule doing its job, not a delay to engineer around.
GAP="${GAP:-320}"

URLS=(
  "https://play.google.com/store/apps/details?id=com.whatsapp"
  "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"
  "https://play.google.com/store/apps/details?id=com.spotify.music"
  "https://apps.apple.com/us/app/instagram/id389801252"
  "https://www.amazon.com/dp/B07FZ8S74R"
  "https://play.google.com/store/apps/details?id=com.instagram.android"
  "https://apps.apple.com/us/app/tiktok/id835599320"
  "https://play.google.com/store/apps/details?id=com.zhiliaoapp.musically"
  "https://www.amazon.com/dp/B0BDHWDR12"
  "https://apps.apple.com/us/app/spotify-music-and-podcasts/id324684580"
)

i=0
for url in "${URLS[@]}"; do
  echo ""
  echo "=============================================================="
  echo "[$((i+1))/${#URLS[@]}]  $url"
  ./tools/gl.sh write "$GUARD" check_reviews --args "$url" '' 2>&1 \
    | grep -E "Transaction Hash|Error|REJECTED" | tail -2
  echo "  …polling for the record"
  ./tools/poll.sh "$GUARD" get_check_by_url "$url" 'found: true' 36 2>/dev/null \
    | grep -E "found:|trust_level|overall:|reviews_parsed|title:|TIMED" | head -6
  i=$((i+1))
  if [ "$i" -lt "${#URLS[@]}" ]; then
    echo "  …waiting ${GAP}s for the per-wallet rate limit"
    sleep "$GAP"
  fi
done
echo ""
echo "=== final stats ==="
genlayer call "$GUARD" get_stats 2>/dev/null | grep -E "total_checked|authentic|suspicious|manipulated|inconclusive|pages_tracked"
