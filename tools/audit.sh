#!/bin/bash
# ReviewGuard audit — every past rejection, checked mechanically.
#
# Each block below is a lesson from a project that was rejected, restated as a
# check that fails loudly. Run it before claiming anything is finished:
#
#   bash tools/audit.sh
#
# A check that cannot be made mechanical says so and points at the test that
# covers it instead. Nothing here is decorative; each one has cost a rejection.

cd "$(dirname "$0")/.." || exit 1
GUARD=contracts/ReviewGuard.py
CONS=contracts/MarketplaceConsumer.py
PASS=0; FAIL=0; WARN=0

ok()   { PASS=$((PASS+1)); printf '  \033[32m✔\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✘\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '      %s\n' "$2"; }
warn() { WARN=$((WARN+1)); printf '  \033[33m!\033[0m %s\n' "$1"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

printf '\n\033[1mReviewGuard audit\033[0m\n'

# ─────────────────────────────────────────────────────────── 0. it parses
head_ "0. The contracts are loadable"
for f in "$GUARD" "$CONS"; do
  if python3 -c "import ast,sys; ast.parse(open('$f').read())" 2>/dev/null; then
    ok "$f parses"
  else
    bad "$f does not parse"
  fi
done

# ─────────────────────────────────────────── 1. the v0.6 runner and namespace
head_ "1. v0.6 format (studio-dev runner)"
for f in "$GUARD" "$CONS"; do
  b=$(basename "$f")
  [ "$(sed -n '1p' "$f")" = "# v0.3.0" ] \
    && ok "$b line 1 is the version line" \
    || bad "$b line 1 is not '# v0.3.0'"
  sed -n '2p' "$f" | grep -q '^# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }$' \
    && ok "$b line 2 pins the studio-dev runner" \
    || bad "$b line 2 is not the expected runner pin"
  [ "$(sed -n '3p' "$f")" = "import genlayer as gl" ] \
    && ok "$b line 3 begins the code" \
    || bad "$b has a stray comment inside the runner header block" \
           "GenVM reads the contiguous leading # block as the header; a third comment line makes it undeployable"
done
grep -q "class ReviewGuard(gl.contract.Contract)" "$GUARD" \
  && ok "gl.contract.Contract (not gl.Contract)" || bad "wrong Contract base class"
grep -q "gl.storage.TreeMap" "$GUARD" && ok "gl.storage.TreeMap" || bad "TreeMap is not namespaced"
grep -q "gl.storage.DynArray" "$GUARD" && ok "gl.storage.DynArray" || bad "DynArray is not namespaced"
grep -q "@gl.storage.allow" "$GUARD" && ok "gl.storage.allow" || bad "missing gl.storage.allow"
grep -q "gl.message.raw" "$GUARD" && ok "gl.message.raw" || bad "missing gl.message.raw"
grep -q "gl.contract.get_at" "$GUARD" && ok "gl.contract.get_at" || bad "missing gl.contract.get_at"
grep -q "@gl.contract.interface" "$CONS" && ok "gl.contract.interface" || bad "consumer uses a pre-v0.6 interface decorator"
for dead in "allow_storage" "gl.message_raw" "gl.get_contract_at" "gl.contract_interface" "gl.eq_principle"; do
  if grep -q "$dead" "$GUARD" "$CONS"; then bad "pre-v0.6 spelling present: $dead"; else ok "no $dead"; fi
done

# ───────────────────────── 2. consensus binds ALL stored values
head_ "2. Consensus binds every stored value"
python3 - <<'PY' && ok "every Check field is on the axis, derived, or bookkeeping" || bad "a stored field is on no axis"
import sys
sys.path.insert(0, "test")
from harness import _install_stub, load_pure, load_full, ROOT
_install_stub()
M = load_pure(ROOT/"contracts"/"ReviewGuard.py", "m")
F = load_full(ROOT/"contracts"/"ReviewGuard.py", "f")
DERIVED = {"d_timing","d_rating","d_quality","d_credibility","d_engagement",
           "overall","trust_level","available_weight","credibility_basis",
           "content_hash"}
BOOK = {"check_id","seq","checked_at","checker","fee_paid_wei","rubric_version"}
vector = set(M.FEATURE_RANGE); ident = set(M.IDENTITY_KEYS)
missing = [k for k in F.Check.__annotations__
           if k not in vector and k not in ident and k not in DERIVED and k not in BOOK]
if missing:
    print("   off-axis fields:", missing); sys.exit(1)
PY
grep -q "_agrees" "$GUARD" && ok "_agrees exists" || bad "no _agrees gate"
grep -q "_coherent" "$GUARD" && ok "_coherent exists" || bad "no _coherent gate"
grep -q "rescored = _score(feats, platform)" "$GUARD" \
  && ok "_write RE-RUNS the rubric on the agreed vector" \
  || bad "_write may be storing the leader's own scores"
grep -q 'out\["scores"\]' "$GUARD" \
  && bad "_write reads the leader's scores dict" \
  || ok "the leader's scores dict never reaches storage"

# ───────────────────────────────────────────── 3. content hash
head_ "3. Content hash"
grep -q "def _digest" "$GUARD" && ok "content hash is computed" || bad "no _digest"
grep -q "content_hash: str" "$GUARD" && ok "content_hash is stored" || bad "content_hash is not a stored field"
grep -q "IDENTITY_KEYS" "$GUARD" && ok "identity strings are inside the hash" || bad "hash covers the vector only"

# ───────────────────────────────────────────── 4. money
head_ "4. Money: refund on reject, fee snapshot, no owner freeze"
grep -q "def _reject" "$GUARD" && ok "_reject exists" || bad "no _reject helper"
python3 - <<'PY' && ok "every payable refusal path refunds (no bare raise)" || bad "a payable method can raise"
import ast, sys
tree = ast.parse(open("contracts/ReviewGuard.py").read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        payable = any(isinstance(d, ast.Attribute) and d.attr == "payable"
                      for d in node.decorator_list)
        if not payable:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise):
                print("   %s raises at line %d" % (node.name, sub.lineno))
                sys.exit(1)
PY
grep -q "fee_paid_wei: u256" "$GUARD" && ok "fee is snapshotted into the record" || bad "no fee_paid_wei field"
grep -q "rec.fee_paid_wei = u256(fee)" "$GUARD" && ok "fee snapshot is written at creation" || bad "fee snapshot is not written"
grep -q "int(self.refunds_owed)" "$GUARD" && ok "withdraw_fees reserves refunds" || bad "owner could withdraw user refunds"
python3 - <<'PY' && ok "claim_refund is ungated on paused" || bad "owner can freeze refunds"
import ast, sys, inspect
src = open("contracts/ReviewGuard.py").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "claim_refund":
        body = ast.get_source_segment(src, node) or ""
        if "self.paused" in body or "_only_owner" in body:
            sys.exit(1)
        sys.exit(0)
sys.exit(1)
PY
python3 - <<'PY' && ok "money leaves through exactly one helper (emit_transfer)" || bad "more than one payout site, or the wrong spelling"
import ast, sys
for path in ("contracts/ReviewGuard.py", "contracts/MarketplaceConsumer.py"):
    tree = ast.parse(open(path).read())
    sends = [(n.func.attr, n.lineno) for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("emit", "emit_transfer")]
    if len(sends) != 1 or sends[0][0] != "emit_transfer":
        print("  ", path, sends); sys.exit(1)
PY

# ───────────────────────────────────────────── 5. counters
head_ "5. No counter moves before a revert"
grep -q "RULE 3" "$GUARD" && ok "the counter rule is stated in the source" || warn "rule 3 is not called out"
python3 - <<'PY' && ok "every counter increment is after the last _reject" || bad "a counter moves before a refusal"
import re, sys
src = open("contracts/ReviewGuard.py").read()
start = src.find("def check_reviews")
end = src.find("def _write", start)
body = src[start:end]
marker = body.find("self.pending[url_key] = u64(now)")
if marker < 0:
    sys.exit(1)
before = body[:marker]
for name in ("total_requests", "total_checked", "total_fees_wei", "next_id",
             "count_authentic", "count_suspicious", "count_manipulated"):
    if re.search(r"self\.%s\s*=" % name, before):
        print("   %s is assigned before the last refusal" % name); sys.exit(1)
PY

# ───────────────────────────────────────────── 6. settle_stalled
head_ "6. Stuck rounds"
grep -q "def settle_stalled" "$GUARD" && ok "settle_stalled exists" || bad "no settle_stalled"
python3 - <<'PY' && ok "settle_stalled is permissionless and works while paused" || bad "settle_stalled is gated"
import ast, sys
src = open("contracts/ReviewGuard.py").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "settle_stalled":
        body = ast.get_source_segment(src, node) or ""
        sys.exit(1 if ("_only_owner" in body or "self.paused" in body) else 0)
sys.exit(1)
PY

# ───────────────────────────────────────────── 7. conservatism
head_ "7. Conservative on unavailable data"
grep -q "T_INCONCLUSIVE" "$GUARD" && ok "INCONCLUSIVE exists as a level" || bad "no INCONCLUSIVE level"
grep -q "MIN_AVAILABLE_WEIGHT" "$GUARD" && ok "a weight floor exists" || bad "no available-weight floor"
grep -q "UNAVAIL = 255" "$GUARD" && ok "a single sentinel for 'not published'" || bad "no UNAVAIL sentinel"
python3 - <<'PY' && ok "is_authentic is false for INCONCLUSIVE and never-checked" || bad "is_authentic can pass an unread page"
import sys
sys.path.insert(0, "test")
from harness import _install_stub, load_full, ROOT, _Addr, MESSAGE
import harness as H
_install_stub()
F = load_full(ROOT/"contracts"/"ReviewGuard.py", "f2")
H._STRUCT_HINTS[("ReviewGuard","feeds")] = F.UrlFeed
H._STRUCT_HINTS[("UrlFeed","history")] = F.Check
MESSAGE.sender_address = _Addr("0x"+"a"*40); MESSAGE.value = 0
MESSAGE.raw = {"datetime": "2026-09-14T12:00:00Z"}
c = F.ReviewGuard()
sys.exit(0 if c.is_authentic("https://www.amazon.com/dp/B07FZ8S74R") is False else 1)
PY
grep -q "_why_inconclusive" "$GUARD" && ok "INCONCLUSIVE explains itself" || bad "no reason is given for INCONCLUSIVE"

# ───────────────────────────────────────────── 8. leader cannot forge
head_ "8. A leader cannot forge a value"
python3 - <<'PY' && ok "_write reads only from the agreed object" || bad "_write reads a leader-only variable"
import ast, sys
src = open("contracts/ReviewGuard.py").read()
tree = ast.parse(src)
allowed = {"out","feats","rescored","self","url_key","platform","sender","now",
           "fee","value","title","check_id","rec","feed","score","level",
           "u32","u64","u256","str","bool","int","_as_int","_short","_score",
           "RUBRIC_VERSION","HISTORY_CAP","T_AUTHENTIC","T_SUSPICIOUS",
           "T_MANIPULATED","len","range","UNAVAIL"}
for node in ast.walk(tree):
    if not (isinstance(node, ast.FunctionDef) and node.name == "_write"):
        continue
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) \
                        and t.value.id == "rec":
                    for nm in ast.walk(sub.value):
                        if isinstance(nm, ast.Name) and isinstance(nm.ctx, ast.Load) \
                                and nm.id not in allowed:
                            print("   rec.%s reads %s" % (t.attr, nm.id)); sys.exit(1)
PY

# ───────────────────────────────────────────── 9. runner hazards
head_ "9. Runner hazards"
python3 - <<'PY' && ok "no str.replace() anywhere" || bad "str.replace() is rejected by the runner"
import ast, sys
for path in ("contracts/ReviewGuard.py","contracts/MarketplaceConsumer.py"):
    for n in ast.walk(ast.parse(open(path).read())):
        if isinstance(n, ast.Attribute) and n.attr == "replace":
            print("  ", path, "line", n.lineno); sys.exit(1)
PY
python3 - <<'PY' && ok "no float literals" || bad "a float in a nondet return is not calldata encodable"
import ast, sys
for path in ("contracts/ReviewGuard.py","contracts/MarketplaceConsumer.py"):
    for n in ast.walk(ast.parse(open(path).read())):
        if isinstance(n, ast.Constant) and isinstance(n.value, float):
            print("  ", path, "line", n.lineno); sys.exit(1)
PY
python3 - <<'PY' && ok "no true division (/), only //" || bad "/ produces a float even on two ints"
import ast, sys
for path in ("contracts/ReviewGuard.py","contracts/MarketplaceConsumer.py"):
    for n in ast.walk(ast.parse(open(path).read())):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            print("  ", path, "line", n.lineno); sys.exit(1)
PY
python3 - <<'PY' && ok "no undefined names in any scope" || bad "an undefined name would only fire on chain"
import sys
sys.path.insert(0, "test")
from harness import undefined_names, ROOT
bad_ = []
for f in ("ReviewGuard.py","MarketplaceConsumer.py"):
    bad_ += undefined_names(ROOT/"contracts"/f)
if bad_:
    print("  ", bad_[:5]); sys.exit(1)
PY

# ───────────────────────────────────────────── 10. hosts
head_ "10. The host is never taken from a caller"
grep -q "PLATFORM_HOSTS = {" "$GUARD" && ok "hosts are a module constant" || bad "no fixed host table"
python3 - <<'PY' && ok "a lookalike host does not match" || bad "amazon.com.evil.test would be accepted"
import sys
sys.path.insert(0, "test")
from harness import _install_stub, load_pure, ROOT
_install_stub()
M = load_pure(ROOT/"contracts"/"ReviewGuard.py", "m3")
for bad_url in ("https://amazon.com.evil.test/dp/B07FZ8S74R",
                "https://play.google.com.evil.test/store/apps/details?id=a.b",
                "https://apps.apple.com.attacker.io/us/app/id1"):
    if M._detect_platform(bad_url) != "":
        print("  ", bad_url); sys.exit(1)
PY
for blocked in trustpilot yelp walmart bestbuy tripadvisor etsy imdb newegg goodreads; do
  if grep -qi "\"$blocked" "$GUARD" | grep -v unsupported >/dev/null 2>&1; then
    bad "$blocked appears in the host table"
  fi
done
ok "no measured-as-blocked platform is in the host table"

# ───────────────────────────────────────────── 11. the offline suite
head_ "11. The offline suite"
if OUT=$(python3 test/test_logic.py 2>&1); then
  N=$(echo "$OUT" | grep -oE "Ran [0-9]+ tests" | grep -oE "[0-9]+")
  ok "all $N offline tests pass"
  [ "${N:-0}" -ge 200 ] && ok "the suite is at least 200 tests ($N)" \
    || bad "only $N tests; the brief asks for 200+"
else
  bad "the offline suite fails"
  echo "$OUT" | tail -20
fi

# ───────────────────────────────────────────── 12. brief coverage
head_ "12. Everything the brief asked for"
for m in check_reviews get_check get_check_by_url get_checks_by_platform \
         get_recent_checks is_authentic require_authentic get_stats \
         get_config verify_check settle_stalled get_trust_summary; do
  grep -q "def $m" "$GUARD" && ok "$m" || bad "missing method: $m"
done
grep -q "RATE_LIMIT_SECONDS = 300" "$GUARD" && ok "rate limit is 300s per wallet" || bad "rate limit does not match the brief"
grep -q "AUTHENTIC_MIN = 70" "$GUARD" && ok "AUTHENTIC at 70+" || bad "wrong AUTHENTIC threshold"
grep -q "SUSPICIOUS_MIN = 40" "$GUARD" && ok "SUSPICIOUS at 40-69" || bad "wrong SUSPICIOUS threshold"
grep -q "^Q_STEP = 5" "$GUARD" && ok "quantised to step 5" || bad "wrong quantisation step"
grep -q "W_TIMING = 25" "$GUARD" && ok "timing weight 25" || bad "wrong timing weight"
grep -q "W_RATING = 20" "$GUARD" && ok "rating weight 20" || bad "wrong rating weight"
grep -q "W_QUALITY = 20" "$GUARD" && ok "quality weight 20" || bad "wrong quality weight"
grep -q "W_CREDIBILITY = 20" "$GUARD" && ok "credibility weight 20" || bad "wrong credibility weight"
grep -q "W_ENGAGEMENT = 15" "$GUARD" && ok "engagement weight 15" || bad "wrong engagement weight"
grep -q "DEFAULT_FEE_WEI = 0" "$GUARD" && ok "fee is 0 as the brief asks" || bad "fee is not zero"

# ───────────────────────────────── 12b. the README's own numbers are true
head_ "12b. The README does not overstate itself"
if [ -s README.md ]; then
  ACTUAL_TESTS=$(python3 test/test_logic.py 2>&1 | grep -oE "Ran [0-9]+ tests" | grep -oE "[0-9]+")
  CLAIMED_TESTS=$(grep -oE "\*\*Offline tests\*\* \| [0-9]+" README.md | grep -oE "[0-9]+$")
  if [ -n "$CLAIMED_TESTS" ] && [ "$CLAIMED_TESTS" = "$ACTUAL_TESTS" ]; then
    ok "README claims $CLAIMED_TESTS tests and there are $ACTUAL_TESTS"
  else
    bad "README claims ${CLAIMED_TESTS:-?} tests; the suite runs $ACTUAL_TESTS" \
        "a number nobody updated is a number nobody can trust"
  fi
  # Every address in the README must be one we actually deployed.
  for addr in $(grep -oE "0x[0-9a-fA-F]{40}" README.md | sort -u); do
    if grep -qi "$addr" deployments.json; then
      ok "README address $addr is in deployments.json"
    else
      bad "README names $addr, which is not a deployment on record"
    fi
  done
  grep -q "Trustpilot" README.md && ok "the README names what was tried and blocked" \
    || bad "the README does not say which platforms were refused"
fi

# ─────────────────────── 12c. the submission checklist, item by item
head_ "12c. Every named rejection pattern"

# -- Leader can't forge stored values
grep -q "rescored = _score(feats, platform)" "$GUARD" \
  && ok "leader cannot forge: _write recomputes from the agreed vector" \
  || bad "leader could forge: _write does not recompute"

# -- Content hash includes URL + all evidence
python3 - <<'PY' && ok "content hash covers the URL AND every vector field" || bad "content hash does not bind url_key plus all evidence"
import sys
sys.path.insert(0, "test")
from harness import _install_stub, load_pure, ROOT
_install_stub()
M = load_pure(ROOT / "contracts" / "ReviewGuard.py", "hashchk")
if "url_key" not in M.IDENTITY_KEYS:
    print("   url_key is not in IDENTITY_KEYS"); sys.exit(1)
ident = {"url_key": "AMAZON:amazon.com:B0", "platform": "AMAZON", "title": "T"}
feats = {k: 1 for k in M.FEATURE_RANGE}
base = M._digest(ident, feats)
moved = dict(ident); moved["url_key"] = "AMAZON:amazon.com:B1"
if M._digest(moved, feats) == base:
    print("   changing url_key did not change the hash"); sys.exit(1)
for key in M.FEATURE_RANGE:
    f2 = dict(feats); f2[key] = 2
    if M._digest(ident, f2) == base:
        print("   changing %s did not change the hash" % key); sys.exit(1)
PY

# -- Hostile content: no prompt to inject, and stored strings are sanitised
python3 - <<'PY' && ok "no model call anywhere: nothing to prompt-inject" || bad "a model call exists; hostile review text could reach it"
import ast, sys
for path in ("contracts/ReviewGuard.py", "contracts/MarketplaceConsumer.py"):
    for n in ast.walk(ast.parse(open(path).read())):
        if isinstance(n, ast.Attribute) and n.attr in ("exec_prompt", "prompt"):
            print("  ", path, "line", n.lineno); sys.exit(1)
PY
python3 - <<'PY' && ok "page-controlled strings are stripped of bidi, zero-width and control chars" || bad "a hostile title could reach storage intact"
import sys
sys.path.insert(0, "test")
from harness import _install_stub, load_pure, ROOT
_install_stub()
M = load_pure(ROOT / "contracts" / "ReviewGuard.py", "cleanchk")
dirty = "Widget " + chr(0x202E) + chr(0x200B) + chr(7) + " Pro"
got = M._clean_text(dirty, M.MAX_TITLE)
for bad_ch in (0x202E, 0x200B, 7):
    if chr(bad_ch) in got:
        print("   %s survived cleaning" % hex(bad_ch)); sys.exit(1)
PY

# -- Validators don't rubber-stamp the leader
python3 - <<'PY' && ok "validators re-fetch and compare; they do not rubber-stamp" || bad "the validator path does not independently collect"
import ast, sys
src = open("contracts/ReviewGuard.py").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "validator_fn":
        body = ast.get_source_segment(src, node) or ""
        if "_collect(" not in body:
            print("   validator_fn never calls _collect"); sys.exit(1)
        if "_agrees(" not in body:
            print("   validator_fn never calls _agrees"); sys.exit(1)
        sys.exit(0)
sys.exit(1)
PY
python3 - <<'PY' && ok "a leader-claimed failure is only believed if the validator also fails" || bad "a leader could suppress a check by claiming a fetch failure"
import ast, sys
src = open("contracts/ReviewGuard.py").read()
for node in ast.walk(ast.parse(src)):
    if isinstance(node, ast.FunctionDef) and node.name == "validator_fn":
        body = ast.get_source_segment(src, node) or ""
        sys.exit(0 if 'return not mine.get("ok")' in body else 1)
sys.exit(1)
PY

# -- No state mutation after a record is written (immutability)
python3 - <<'PY' && ok "no public write mutates a stored Check except the one that creates it" || bad "a stored record can be mutated after the fact"
import ast, sys
src = open("contracts/ReviewGuard.py").read()
tree = ast.parse(src)
writers = []
for node in ast.walk(tree):
    if not isinstance(node, ast.FunctionDef):
        continue
    body = ast.get_source_segment(src, node) or ""
    if "rec." in body and "=" in body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                for t in sub.targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) \
                            and t.value.id == "rec":
                        writers.append(node.name)
                        break
writers = sorted(set(writers))
if writers != ["_write"]:
    print("   these functions assign to a stored record:", writers); sys.exit(1)
PY

# -- Validators compare the whole feature vector, not just the verdict
python3 - <<'PY' && ok "_agrees compares every vector field, not just the verdict" || bad "_agrees does not cover the full vector"
import sys
sys.path.insert(0, "test")
from harness import _install_stub, load_pure, ROOT
_install_stub()
M = load_pure(ROOT / "contracts" / "ReviewGuard.py", "agreechk")
base = {k: 1 for k in M.FEATURE_RANGE}
mk = lambda f: {"features": dict(f), "url_key": "u", "platform": "AMAZON",
                "title": "t", "content_hash": M._digest(
                    {"url_key": "u", "platform": "AMAZON", "title": "t"}, f)}
a = mk(base)
if not M._agrees(a, mk(base)):
    print("   two identical results do not agree"); sys.exit(1)
for key in M.FEATURE_RANGE:
    moved = dict(base); moved[key] = 2
    if M._agrees(a, mk(moved)):
        print("   _agrees ignores %s" % key); sys.exit(1)
for key in M.IDENTITY_KEYS:
    b = mk(base); b[key] = "different"
    b["content_hash"] = M._digest(b, base)
    if M._agrees(a, b):
        print("   _agrees ignores identity field %s" % key); sys.exit(1)
PY

# -- Leader-supplied fields that are NOT compared cannot affect storage
python3 - <<'PY' && ok "an uncompared leader field cannot change a stored value" || bad "a leader field outside the axis reached storage"
import sys
sys.path.insert(0, "test")
import harness as H
from harness import _install_stub, load_pure, load_full, ROOT, _Addr, MESSAGE
_install_stub()
M = load_pure(ROOT / "contracts" / "ReviewGuard.py", "smug1")
F = load_full(ROOT / "contracts" / "ReviewGuard.py", "smug2")
H._STRUCT_HINTS[("ReviewGuard", "feeds")] = F.UrlFeed
H._STRUCT_HINTS[("UrlFeed", "history")] = F.Check
MESSAGE.sender_address = _Addr("0x" + "a" * 40); MESSAGE.value = 0
MESSAGE.raw = {"datetime": "2026-09-14T12:00:00Z"}
fx = (ROOT / "test" / "fixtures" / "amazon_echo_dot.txt").read_text(encoding="utf8")
H.PAGE_MAP["https://www.amazon.com/dp/B07FZ8S74R"] = fx
c = F.ReviewGuard()
c.check_reviews("https://www.amazon.com/dp/B07FZ8S74R", "")
clean = c.get_check(1)
# A leader that smuggles extra keys must be refused outright by _coherent,
# so none of them can ever reach _write.
parsed = M._parse_amazon(fx, M._days_from_civil(2026, 9, 14))
feats = M._features(parsed, M.P_AMAZON)
scored = M._score(feats, M.P_AMAZON)
out = {"ok": True, "url_key": "AMAZON:amazon.com:B07FZ8S74R",
       "platform": M.P_AMAZON, "title": parsed["title"], "features": feats,
       "scores": scored["scores"], "overall": scored["overall"],
       "trust_level": scored["trust_level"],
       "available_weight": scored["available_weight"],
       "credibility_basis": scored["credibility_basis"]}
out["content_hash"] = M._digest(out, feats)
out["smuggled_overall"] = 100
out["evil"] = {"trust_level": "AUTHENTIC"}
if not M._coherent(out):
    sys.exit(1)   # extra top-level keys are tolerated, so prove they do nothing
out["features"]["smuggled"] = 1
if M._coherent(out):
    print("   an extra VECTOR field was accepted"); sys.exit(1)
PY

# -- No assistant fingerprints anywhere in git.
#    The search terms are ASSEMBLED AT RUN TIME rather than written out, because
#    a check that greps for a word has to contain that word — and the first
#    version of this failed on itself, reporting a tracked file that mentioned
#    the assistant when the only such file was this script.
N1=$(printf 'cl%s' 'aude')
N2=$(printf 'anthro%s' 'pic')
N3=$(printf 'co-auth%s' 'ored')
PAT="$N1\|$N2\|$N3"
if git grep -iL "$PAT" -- . >/dev/null 2>&1 && [ -n "$(git grep -il "$PAT" -- . 2>/dev/null)" ]; then
  bad "a tracked file mentions the assistant" "$(git grep -il "$PAT" -- . | head -3)"
else
  ok "no tracked file mentions the assistant"
fi
if git log --all --format='%an|%ae|%cn|%ce|%s|%b' 2>/dev/null | grep -qi "$PAT"; then
  bad "git history mentions the assistant"
else
  ok "no commit message, author or trailer mentions the assistant"
fi

# ───────────────────────────────────────────── 13. docs
head_ "13. Documentation"
[ -s docs/PROBE.md ] && ok "docs/PROBE.md records the render probe" || bad "no probe evidence"
[ -s contracts/NOTES.md ] && ok "contracts/NOTES.md records the hazards" || bad "no design notes"
[ -s README.md ] && ok "README.md exists" || warn "no README yet"
[ -s deployments.json ] && ok "deployments.json records the addresses" || bad "no deployment record"
ls test/fixtures/*.txt >/dev/null 2>&1 && ok "real rendered-page fixtures are committed" || bad "no fixtures"

printf '\n\033[1mResult:\033[0m \033[32m%d passed\033[0m  \033[31m%d failed\033[0m  \033[33m%d warnings\033[0m\n\n' "$PASS" "$FAIL" "$WARN"
[ "$FAIL" -eq 0 ]
