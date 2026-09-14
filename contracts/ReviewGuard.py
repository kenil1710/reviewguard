# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
from dataclasses import dataclass
import json
import typing

# ReviewGuard — a fake-review detector any contract can read.
#
# Submit the URL of a product's review page. Validators independently RENDER the
# same page, reduce it to a twenty-number feature vector, and agree on THE
# VECTOR. Everything stored — five dimension ordinals, the overall score, the
# trust level, every evidence figure a reader sees — is recomputed from that
# agreed vector after consensus. The leader's own numbers never reach storage.
#
# Which platforms are supported was MEASURED, not assumed: docs/PROBE.md records
# a throwaway probe deployed to studio-dev that tried fourteen review sites.
# Eleven of them block a validator outright or render nothing but chrome, and
# they are not here. Three of them work, and only those three are offered.
#
# Design notes and hazards: contracts/NOTES.md.
#
# The two header lines above are the whole of what GenVM reads before the code:
# the version line and the runner pin, in that order. Nothing else may sit
# between line 1 and the imports — GenVM parses the contiguous leading `#` block
# as the runner header, and a stray comment there makes the contract
# undeployable with no error reported but `invalid_contract`.
#
# EIGHT RULES govern everything below. Each one is a past rejection written down
# so that it cannot happen again.
#
#   1. CONSENSUS BINDS EVERY STORED VALUE. Not the trust level, not "the
#      important fields" — every single one. A field the validators did not
#      compare is a field the leader can forge, and a forged review count on a
#      review oracle is the whole attack. The compared axis carries the twenty
#      vector integers AND the identity strings AND the content hash, and
#      `_write` may only ever read from `out`, the agreed object. See `_agrees`.
#
#   2. A PAYABLE METHOD MAY NEVER RAISE. A revert rolls back storage but NOT the
#      incoming value, which then sits in the contract unaccounted for. Every
#      refusal in `check_reviews` goes through `_reject`, which credits the full
#      deposit to a pull-based ledger and returns {"status": "REJECTED", …}.
#
#   3. NO COUNTER MOVES BEFORE A PATH THAT CAN STILL REFUSE. Every increment
#      happens after the last possible rejection, never before.
#
#   4. THE FEE IS SNAPSHOTTED INTO THE RECORD AT CREATION. `fee_paid_wei` is
#      what THIS check cost, frozen. An owner who raises the price tomorrow
#      cannot restate the price of work already done.
#
#   5. A WRITTEN CHECK IS IMMUTABLE. Nothing mutates a record after it is
#      written — not the owner, not a pause, not a re-check. A re-check appends.
#
#   6. THE OWNER CANNOT FREEZE USER MONEY. `claim_refund` and every read are
#      ungated on `paused`. `withdraw_fees` subtracts `refunds_owed` before
#      offering a balance. Pause stops new risk arriving and nothing else.
#
#   7. EVIDENCE THAT IS NOT THERE IS `UNAVAILABLE`, NEVER ZERO. Google Play does
#      not publish a rating histogram; the App Store publishes neither a
#      per-review rating nor a helpful vote. Scoring an absent feature as zero
#      would defame a product for a gap in somebody else's page. An unavailable
#      dimension carries NO WEIGHT, and below MIN_AVAILABLE_WEIGHT the whole
#      check is INCONCLUSIVE — which is not a low score and is not a pass.
#
#   8. A LEADER CANNOT FORGE A VALUE. `_coherent` proves the leader's own
#      arithmetic before any validator votes, `_agrees` compares every field,
#      and `_write` runs `_score()` AGAIN on the agreed vector rather than
#      storing the leader's scores.
#
# str.replace() is rejected by the runner; slice around find() instead.

RUBRIC_VERSION = "1.0.0"

# --- economics. The fee defaults to ZERO: this is a public good on a testnet
# and nobody should pay to ask whether a product's reviews are real. The
# machinery is here anyway, fully exercised, because a fee that cannot be
# charged is a fee whose refund path was never tested.
DEFAULT_FEE_WEI = 0
MAX_FEE_WEI = 10**17               # owner ceiling: 0.1 GEN

# --- anti-abuse. Constants rather than governance knobs: an owner who can
# retune the rate limit can price a competitor out of the oracle.
RATE_LIMIT_SECONDS = 300           # per wallet, as the brief specifies
URL_COOLDOWN = 900                 # per URL
PENDING_TTL = 600                  # then settle_stalled clears a stuck round
MAX_URLS = 2000
MAX_PLATFORM_INDEX = 64
HISTORY_CAP = 6                    # checks kept per URL
SCAN_CAP = 400                     # URLs a listing view will walk

# --- weights, straight from the brief. 25 + 20 + 20 + 20 + 15 = 100.
W_TIMING = 25
W_RATING = 20
W_QUALITY = 20
W_CREDIBILITY = 20
W_ENGAGEMENT = 15
WEIGHT_TOTAL = W_TIMING + W_RATING + W_QUALITY + W_CREDIBILITY + W_ENGAGEMENT
Q_STEP = 5
ORDINAL_MAX = 7

# Below this much available weight the evidence is too thin to call, whatever
# the surviving dimensions say. 60 is one dimension short of the App Store's
# 65 — so the App Store scores, and an App Store page that also fails to yield
# dates does not.
MIN_AVAILABLE_WEIGHT = 60
MIN_REVIEWS = 3                    # fewer parsed reviews than this: INCONCLUSIVE

# --- trust levels on the 0-100 overall.
AUTHENTIC_MIN = 70
SUSPICIOUS_MIN = 40

T_AUTHENTIC = "AUTHENTIC"
T_SUSPICIOUS = "SUSPICIOUS"
T_MANIPULATED = "MANIPULATED"
T_INCONCLUSIVE = "INCONCLUSIVE"
TRUST_LEVELS = (T_AUTHENTIC, T_SUSPICIOUS, T_MANIPULATED, T_INCONCLUSIVE)

ERR_EXPECTED = "[EXPECTED]"
ERR_EXTERNAL = "[EXTERNAL]"
ERR_TRANSIENT = "[TRANSIENT]"

# Storage has no signed integer type and no null. UNAVAIL is the one sentinel
# used for "this page does not publish that", applied in exactly one place
# (`_pack`) and removed in exactly one place (`_avail`). A sign convention
# spread across forty fields is how the -1 becomes a 255 in the UI.
UNAVAIL = 255

# --- the platforms. Fixed here and NEVER taken from a caller: a submitter who
# could name the host could point five validators at a server they control and
# manufacture any verdict they liked. Each entry says which dimensions that
# platform's page actually carries evidence for — see docs/PROBE.md §3.4, where
# every one of these flags was measured against a live render.
P_AMAZON = "AMAZON"
P_GPLAY = "GOOGLE_PLAY"
P_APPSTORE = "APP_STORE"
PLATFORMS = (P_AMAZON, P_GPLAY, P_APPSTORE)

PLATFORM_HOSTS = {
	P_AMAZON: ("amazon.com", "amazon.co.uk", "amazon.de", "amazon.ca",
		"amazon.in", "amazon.co.jp", "amazon.fr", "amazon.es", "amazon.it",
		"amazon.com.au", "amazon.com.mx", "amazon.com.br", "amazon.nl",
		"amazon.se", "amazon.pl", "amazon.sg", "amazon.ae"),
	P_GPLAY: ("play.google.com",),
	P_APPSTORE: ("apps.apple.com",),
}

# Which dimensions each platform can support, and on what basis. A False here
# is not a low score — it is "this page does not say", and rule 7 governs it.
PLATFORM_DIMS = {
	P_AMAZON: {"timing": True, "rating": True, "quality": True,
		"credibility": True, "engagement": True,
		"credibility_basis": "verified-purchase",
		"engagement_max": 8},
	P_GPLAY: {"timing": True, "rating": False, "quality": True,
		"credibility": True, "engagement": True,
		"credibility_basis": "identity-shape",
		"engagement_max": 5},
	P_APPSTORE: {"timing": True, "rating": False, "quality": True,
		"credibility": True, "engagement": False,
		"credibility_basis": "identity-shape",
		"engagement_max": 0},
}

RENDER_WAIT = "6s"
PAGE_CAP = 120000                  # characters of rendered text kept
MAX_REVIEWS = 40                   # reviews parsed from one page
MAX_URL = 300
MAX_TITLE = 120
SHORT_REVIEW_CHARS = 120           # below this a review body is "generic/short"
PREFIX_WORDS = 6                   # words compared when detecting duplicate openings

# --- the dimension vocabulary. Index 0 is always the WORST outcome and 7 the
# best, for every dimension, so `_score` can be one loop rather than five
# special cases and a reader never has to remember which way a bar points.
DIM_KEYS = ("timing_pattern", "rating_distribution", "review_quality",
	"reviewer_credibility", "engagement_signals")

DIM_WEIGHTS = {
	"timing_pattern": W_TIMING,
	"rating_distribution": W_RATING,
	"review_quality": W_QUALITY,
	"reviewer_credibility": W_CREDIBILITY,
	"engagement_signals": W_ENGAGEMENT,
}

BUCKETS = {
	"timing_pattern": (
		"one massive burst", "near-total clustering", "heavy clustering",
		"noticeable clustering", "mildly clustered", "mostly spread",
		"well spread", "naturally distributed"),
	"rating_distribution": (
		"effectively all five-star", "almost all five-star",
		"very top-heavy", "top-heavy", "slightly top-heavy",
		"plausible spread", "healthy spread", "natural spread"),
	"review_quality": (
		"all generic and short", "mostly generic", "thin and repetitive",
		"short but varied", "mixed depth", "reasonably detailed",
		"detailed", "detailed and varied"),
	"reviewer_credibility": (
		"no credible reviewers", "almost none credible", "largely doubtful",
		"doubtful", "unremarkable", "mostly credible", "credible",
		"established reviewers"),
	"engagement_signals": (
		"no engagement at all", "almost none", "very little", "little",
		"some", "moderate", "good", "high natural engagement"),
}

# Every vector field with the (lo, hi) it must lie inside. Enforced identically
# by `_coherent` before a vote, by `_agrees` during one, and by `verify_check`
# years later. A field not in this table cannot be on the axis, and a field not
# on the axis cannot be stored.
FEATURE_RANGE = {
	"reviews_parsed": (0, MAX_REVIEWS),
	"avg_rating_x10": (0, 50),
	"total_ratings": (0, 10**12),
	"pct_5": (0, 100), "pct_4": (0, 100), "pct_3": (0, 100),
	"pct_2": (0, 100), "pct_1": (0, 100),
	"dated_reviews": (0, MAX_REVIEWS),
	"distinct_days": (0, MAX_REVIEWS),
	"max_same_day": (0, MAX_REVIEWS),
	"span_days": (0, 20000),
	"median_chars": (0, 20000),
	"short_pct": (0, 100),
	"dup_open_pct": (0, 100),
	"lexical_pct": (0, 100),
	"verified_pct": (0, 100),
	"distinct_names_pct": (0, 100),
	"weak_handle_pct": (0, 100),
	"helpful_pct": (0, 100),
	"helpful_total": (0, 10**10),
	"has_photos": (0, 1),
	"has_response": (0, 1),
	# How much of the page rendered, and whether the review LIST was on it at
	# all. Neither feeds a dimension: they are here so that an INCONCLUSIVE
	# check can say WHY. Measured 2026-09-14: amazon.com/dp pages that had
	# rendered 37,914 characters with eight reviews an hour earlier began
	# rendering 14,163 characters and stopping before the review section, and a
	# wait raised from 6s to 12s changed that by 47 characters. Without this
	# field a reader sees "0 reviews parsed" and cannot tell a page with no
	# reviews from a page that was cut short.
	"page_chars": (0, PAGE_CAP),
	"reviews_section": (0, 1),
}
# Fields that may legitimately arrive as UNAVAIL because some platform does not
# publish them. Anything not listed here must be a real number every time.
NULLABLE = ("avg_rating_x10", "total_ratings", "pct_5", "pct_4", "pct_3",
	"pct_2", "pct_1", "verified_pct", "helpful_pct", "helpful_total")

# The identity axis. Strings the validators compare verbatim, because a leader
# who could vary any of them could show the scorer one page and the validators
# another.
IDENTITY_KEYS = ("url_key", "platform", "title")


# ─────────────────────────────────────────────────────────── small utilities

def _as_int(v: typing.Any, default: int = 0) -> int:
	"""An int from anything, with `bool` EXCLUDED explicitly.

	`bool` is an `int` in Python, so without this a `True` arriving in a vector
	field would silently score as 1 rather than being caught as the wrong type.
	"""
	if isinstance(v, bool):
		return default
	if isinstance(v, int):
		return v
	if isinstance(v, float):
		return int(v)
	if isinstance(v, str):
		t = v.strip()
		neg = t.startswith("-")
		if neg:
			t = t[1:]
		if t == "" or not t.isdigit():
			return default
		return -int(t) if neg else int(t)
	return default


def _clamp(v: int, lo: int, hi: int) -> int:
	return lo if v < lo else (hi if v > hi else v)


def _short(s: str, n: int) -> str:
	t = str(s)
	return t if len(t) <= n else t[:n]


def _swap(text: str, old: str, new: str) -> str:
	"""What `str.replace()` would do, written out because THE RUNNER REJECTS
	`str.replace`. Slicing around `find()` is the supported spelling."""
	if old == "":
		return text
	out = ""
	rest = text
	while True:
		i = rest.find(old)
		if i < 0:
			return out + rest
		out += rest[:i] + new
		rest = rest[i + len(old):]


def _strip_ws(s: str) -> str:
	return s.strip()


def _lower(s: str) -> str:
	return s.lower()


def _q(v: int, step: int) -> int:
	"""Round to the nearest `step`, half up. THE tolerance in this contract.

	Two validators render the same page seconds apart. `_agrees` demands exact
	equality, so the noise has to be absorbed somewhere, and it is absorbed HERE
	— in the quantisation — never in the comparison. A comparison with a
	tolerance in it would mean two different accepted outputs for one request,
	and then which one is the check?"""
	if step <= 1:
		return v
	return ((v + step // 2) // step) * step


def _sig3(v: int) -> int:
	"""Three significant figures. A review count that ticks from 1,037,930 to
	1,037,931 between two validators must not be a disagreement."""
	n = int(v)
	if n <= 0:
		return 0
	scale = 1
	probe = n
	while probe >= 1000:
		probe //= 10
		scale *= 10
	return ((n + scale // 2) // scale) * scale


def _pct(part: int, whole: int) -> int:
	if whole <= 0:
		return 0
	return _clamp((int(part) * 100) // int(whole), 0, 100)


def _avail(v: typing.Any) -> bool:
	"""Is this field a real measurement? THE ONLY place UNAVAIL is interpreted."""
	return _as_int(v, UNAVAIL) != UNAVAIL


def _digits_only(s: str) -> str:
	out = ""
	for ch in s:
		if ch.isdigit():
			out += ch
	return out


def _int_from_commas(s: str) -> int:
	"""`1,037,930` → 1037930. Also handles `239M`, `19M`, `3.5K` — the compact
	forms Google Play and the App Store use for large counts, which a plain
	digit strip would read as 239 and 35."""
	t = s.strip()
	mult = 1
	low = t.lower()
	if low.endswith("m"):
		mult = 1000000
		t = t[:-1]
	elif low.endswith("k"):
		mult = 1000
		t = t[:-1]
	elif low.endswith("b"):
		mult = 1000000000
		t = t[:-1]
	whole = ""
	frac = ""
	seen_dot = False
	for ch in t:
		if ch.isdigit():
			if seen_dot:
				frac += ch
			else:
				whole += ch
		elif ch == "." and mult > 1 and not seen_dot:
			seen_dot = True
		elif ch == ",":
			continue
		else:
			continue
	if whole == "":
		return 0
	base = int(whole) * mult
	if frac != "" and mult > 1:
		# 3.5K → 3500, one fractional digit at a time so no float is created.
		scale = mult
		for ch in frac:
			scale //= 10
			if scale <= 0:
				break
			base += int(ch) * scale
	return base


def _words(text: str) -> list:
	"""Lowercase alphabetic word list. Punctuation is a separator, so the same
	sentence typed with and without a comma yields the same words."""
	out = []
	cur = ""
	for ch in text.lower():
		if ch.isalpha() or ch.isdigit():
			cur += ch
		else:
			if cur != "":
				out.append(cur)
			cur = ""
	if cur != "":
		out.append(cur)
	return out


def _median(values: list) -> int:
	if len(values) == 0:
		return 0
	s = sorted(values)
	n = len(s)
	if n % 2 == 1:
		return int(s[n // 2])
	return (int(s[n // 2 - 1]) + int(s[n // 2])) // 2


# ─────────────────────────────────────────────── dates, in pure integer maths

MONTHS = ("january", "february", "march", "april", "may", "june", "july",
	"august", "september", "october", "november", "december")
MONTHS_ABBR = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
	"oct", "nov", "dec")


def _days_from_civil(y: int, m: int, d: int) -> int:
	"""Days since the Unix epoch for a civil date. Howard Hinnant's algorithm,
	integer-only — no datetime module and no float anywhere near consensus."""
	y -= 1 if m <= 2 else 0
	era = (y if y >= 0 else y - 399) // 400
	yoe = y - era * 400
	doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
	doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
	return era * 146097 + doe - 719468


def _month_index(token: str) -> int:
	t = token.strip().lower()
	if len(t) < 3:
		return 0
	for i in range(12):
		if t == MONTHS[i]:
			return i + 1
	head = t[:3]
	for i in range(12):
		if head == MONTHS_ABBR[i]:
			return i + 1
	return 0


def _epoch_from_iso(value: typing.Any) -> int:
	if not isinstance(value, str) or len(value) < 19:
		return 0
	try:
		y = int(value[0:4]); mo = int(value[5:7]); d = int(value[8:10])
		h = int(value[11:13]); mi = int(value[14:16]); s = int(value[17:19])
	except ValueError:
		return 0
	if mo < 1 or mo > 12 or d < 1 or d > 31:
		return 0
	return _days_from_civil(y, mo, d) * 86400 + h * 3600 + mi * 60 + s


def _parse_date(text: str, today_day: int) -> int:
	"""A review date as a day number, or 0 if the text carries none.

	Three formats, because the three shipped platforms use three:

	  Amazon      `December 14, 2019`
	  App Store   `06/14/2023`  and, for recent reviews, `Jan 21`
	  Google Play `August 28, 2026`

	`Jan 21` has no year. It is resolved against the BLOCK TIME — which is part
	of the transaction and therefore identical for every validator — and never
	against a wall clock, which would differ per node and put the date on the
	disagreement side of consensus. It resolves to the most recent such date not
	in the future, which is what "Jan 21" on a review page means.
	"""
	t = text.strip()
	if t == "":
		return 0

	# `06/14/2023` or `6/14/23`
	if "/" in t:
		parts = t.split("/")
		if len(parts) == 3:
			a = _digits_only(parts[0]); b = _digits_only(parts[1])
			c = _digits_only(parts[2])
			if a != "" and b != "" and c != "":
				mo = int(a); d = int(b); y = int(c)
				if y < 100:
					y += 2000
				if 1 <= mo <= 12 and 1 <= d <= 31 and 1900 < y < 2200:
					return _days_from_civil(y, mo, d)
		return 0

	tokens = []
	cur = ""
	for ch in t:
		if ch.isalpha() or ch.isdigit():
			cur += ch
		else:
			if cur != "":
				tokens.append(cur)
			cur = ""
	if cur != "":
		tokens.append(cur)
	if len(tokens) < 2:
		return 0

	mo = _month_index(tokens[0])
	if mo == 0:
		return 0
	dd = _digits_only(tokens[1])
	if dd == "" or len(dd) > 2:
		return 0
	d = int(dd)
	if d < 1 or d > 31:
		return 0

	if len(tokens) >= 3:
		yy = _digits_only(tokens[2])
		if len(yy) == 4:
			y = int(yy)
			if 1900 < y < 2200:
				return _days_from_civil(y, mo, d)
		return 0

	# No year: `Jan 21`. Resolve against block time, most recent not-future.
	if today_day <= 0:
		return 0
	y = 1970 + (today_day * 4) // 1461     # approximate year, then correct
	for cand in (y + 1, y, y - 1, y - 2):
		if cand < 1970:
			continue
		day = _days_from_civil(cand, mo, d)
		if day <= today_day:
			return day
	return 0


# ───────────────────────────────────────────── URLs: detection and canonical form
#
# THE HOST IS NEVER TAKEN FROM THE CALLER. A submitter hands in a URL; this code
# extracts an IDENTIFIER from it and then rebuilds the fetch URL out of the
# fixed host table above. A submitter who could name the host could point five
# validators at a server they control and manufacture any verdict they liked.

ASIN_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
PKG_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._"
CC_CHARS = "abcdefghijklmnopqrstuvwxyz"


def _strip_scheme(url: str) -> str:
	t = url.strip()
	low = t.lower()
	for pre in ("https://", "http://", "//"):
		if low.startswith(pre):
			t = t[len(pre):]
			low = t.lower()
	if low.startswith("www."):
		t = t[4:]
	return t


def _host_of(url: str) -> str:
	t = _strip_scheme(url)
	cut = len(t)
	for sep in ("/", "?", "#"):
		i = t.find(sep)
		if 0 <= i < cut:
			cut = i
	return t[:cut].lower()


def _path_of(url: str) -> str:
	t = _strip_scheme(url)
	i = t.find("/")
	if i < 0:
		return ""
	rest = t[i:]
	j = rest.find("#")
	if j >= 0:
		rest = rest[:j]
	return rest


def _query_value(url: str, key: str) -> str:
	t = _path_of(url)
	i = t.find("?")
	if i < 0:
		return ""
	q = t[i + 1:]
	for part in q.split("&"):
		eq = part.find("=")
		if eq < 0:
			continue
		if part[:eq] == key:
			return part[eq + 1:]
	return ""


def _segments(url: str) -> list:
	t = _path_of(url)
	i = t.find("?")
	if i >= 0:
		t = t[:i]
	out = []
	for seg in t.split("/"):
		s = seg.strip()
		if s != "":
			out.append(s)
	return out


def _allowed(text: str, alphabet: str) -> bool:
	if text == "":
		return False
	for ch in text:
		if ch not in alphabet:
			return False
	return True


def _detect_platform(url: str) -> str:
	"""Which platform a URL belongs to, or "" for one nothing here supports.

	Suffix-matched against the fixed table, and anchored: `amazon.com.evil.test`
	must NOT match `amazon.com`. The check is that the host either equals the
	known host or ends with `.` + the known host."""
	host = _host_of(url)
	if host == "":
		return ""
	for plat in PLATFORMS:
		for known in PLATFORM_HOSTS[plat]:
			if host == known or host.endswith("." + known):
				return plat
	return ""


def _amazon_asin(url: str) -> str:
	"""The ASIN out of any Amazon product URL shape.

	`/dp/B07FZ8S74R`, `/gp/product/B07FZ8S74R`, and the SEO form
	`/Echo-Dot-3rd-Gen/dp/B07FZ8S74R/ref=sr_1_3` all carry it. An ASIN is ten
	characters of uppercase alphanumerics."""
	segs = _segments(url)
	for i in range(len(segs)):
		s = segs[i]
		if s.lower() in ("dp", "product", "gp") and i + 1 < len(segs):
			cand = segs[i + 1].upper()
			if s.lower() == "gp" and cand == "PRODUCT" and i + 2 < len(segs):
				cand = segs[i + 2].upper()
			if len(cand) == 10 and _allowed(cand, ASIN_CHARS):
				return cand
	for s in segs:
		cand = s.upper()
		if len(cand) == 10 and _allowed(cand, ASIN_CHARS) and cand[0] == "B":
			return cand
	return ""


def _appstore_id(url: str) -> str:
	for s in _segments(url):
		low = s.lower()
		if low.startswith("id"):
			digits = _digits_only(low[2:])
			if len(digits) >= 6 and digits == low[2:]:
				return digits
	return ""


def _appstore_cc(url: str) -> str:
	segs = _segments(url)
	if len(segs) > 0 and len(segs[0]) == 2 and _allowed(segs[0].lower(), CC_CHARS):
		return segs[0].lower()
	return "us"


def _amazon_host(url: str) -> str:
	"""The Amazon locale, normalised. `amazon.co.uk` and `amazon.com` are
	DIFFERENT catalogues with different reviews, so the locale is part of the
	identity and must not be collapsed."""
	host = _host_of(url)
	for known in PLATFORM_HOSTS[P_AMAZON]:
		if host == known or host.endswith("." + known):
			return known
	return ""


def _canonical(url: str, platform: str) -> tuple:
	"""(url_key, fetch_url, why). The url_key is the identity this contract
	stores and indexes on; the fetch_url is rebuilt from the fixed host table.

	`why` is non-empty exactly when the URL cannot be used, and it says what was
	wrong in words a submitter can act on."""
	if platform == P_AMAZON:
		host = _amazon_host(url)
		if host == "":
			return ("", "", "not an Amazon host this contract knows")
		asin = _amazon_asin(url)
		if asin == "":
			return ("", "", "no ASIN in that Amazon URL — it should look like "
				"amazon.com/dp/B07FZ8S74R")
		# /dp/ and NOT /product-reviews/: docs/PROBE.md §2.4 measured the
		# dedicated reviews page returning a 607-character SIGN-IN WALL. The
		# product page carries the reviews; the reviews page carries a login.
		return (P_AMAZON + ":" + host + ":" + asin,
			"https://www." + host + "/dp/" + asin, "")

	if platform == P_GPLAY:
		pkg = _query_value(url, "id")
		if pkg == "" or not _allowed(pkg, PKG_CHARS) or "." not in pkg:
			return ("", "", "no app id in that Google Play URL — it should look "
				"like play.google.com/store/apps/details?id=com.whatsapp")
		if len(pkg) > 120:
			return ("", "", "that Google Play app id is implausibly long")
		return (P_GPLAY + ":" + pkg,
			"https://play.google.com/store/apps/details?id=" + pkg
			+ "&hl=en&gl=US", "")

	if platform == P_APPSTORE:
		app_id = _appstore_id(url)
		if app_id == "":
			return ("", "", "no app id in that App Store URL — it should look "
				"like apps.apple.com/us/app/whatsapp-messenger/id310633997")
		cc = _appstore_cc(url)
		return (P_APPSTORE + ":" + cc + ":" + app_id,
			"https://apps.apple.com/" + cc + "/app/id" + app_id, "")

	return ("", "", "unsupported platform")


# ───────────────────────────────────────────────────────────────── the fetch

def _source_url(url_key: str) -> str:
	"""The url_key turned back into a link a human can open.

	Stored as a KEY rather than as a URL because the key is what identity and
	the content hash are built on, and a stored URL would drift the moment a
	platform changed its path shape. One function rebuilds the link, so the
	front end never has to know how a key is spelled."""
	parts = str(url_key).split(":")
	if len(parts) < 2:
		return ""
	plat = parts[0]
	if plat == P_AMAZON and len(parts) >= 3:
		return "https://www." + parts[1] + "/dp/" + parts[2]
	if plat == P_GPLAY:
		return "https://play.google.com/store/apps/details?id=" + parts[1]
	if plat == P_APPSTORE and len(parts) >= 3:
		return "https://apps.apple.com/" + parts[1] + "/app/id" + parts[2]
	return ""


def _render_page(url: str) -> str:
	"""The rendered text of a review page, or "" if it could not be fetched.

	`render()` has NO status code: it returns the body on success and RAISES on
	everything else, with the reason in the exception text. A fetch that failed
	and a page that is empty are therefore the same value here, and both are
	treated as NO EVIDENCE rather than as bad evidence — which is the direction
	rule 7 demands."""
	txt = gl.nondet.web.render(url, mode="text", wait_after_loaded=RENDER_WAIT)
	if not isinstance(txt, str):
		txt = str(txt)
	return txt[:PAGE_CAP]


def _lines(text: str) -> list:
	out = []
	for raw in text.split("\n"):
		out.append(raw.strip())
	return out


def _find_line(rows: list, needle: str, start: int) -> int:
	for i in range(start, len(rows)):
		if rows[i] == needle:
			return i
	return -1


def _find_prefix(rows: list, prefix: str, start: int) -> int:
	for i in range(start, len(rows)):
		if rows[i].startswith(prefix):
			return i
	return -1


def _find_contains(rows: list, needle: str, start: int) -> int:
	for i in range(start, len(rows)):
		if needle in rows[i]:
			return i
	return -1


def _prev_nonempty(rows: list, i: int) -> int:
	j = i - 1
	while j >= 0:
		if rows[j] != "":
			return j
		j -= 1
	return -1


def _helpful_count(line: str) -> int:
	"""`119 people found this helpful` → 119. `One person found this helpful`
	→ 1. Amazon spells the singular as a WORD, and a digit-only parse reads it
	as zero — which would report a review that HAD engagement as having none."""
	low = line.lower()
	if "found this" not in low or "helpful" not in low:
		return -1
	if low.startswith("one person"):
		return 1
	head = ""
	for ch in line:
		if ch.isdigit() or ch == ",":
			head += ch
		elif head != "":
			break
		elif ch == " ":
			continue
		else:
			return -1
	if head == "":
		return -1
	return _int_from_commas(head)


AMZ_STOP = ("Read more", "Helpful", "Report", "Translate review to English",
	"See more reviews", "Top reviews from other countries")


def _parse_amazon(text: str, today_day: int) -> dict:
	"""Amazon `/dp/{ASIN}`. The richest of the three — see docs/PROBE.md §3.1.

	THE REVIEW SCAN STARTS AT THE `Top reviews from` ANCHOR AND NOT BEFORE. The
	page carries a carousel of RELATED products further up whose lines read
	`4.2 out of 5 stars`, and a whole-page scan picks those up as reviews of
	this product. Measured on the fixture: six such lines sit above the
	customer-review section."""
	rows = _lines(text)
	out = {"reviews": [], "avg_rating_x10": UNAVAIL, "total_ratings": UNAVAIL,
		"pct": [UNAVAIL] * 5, "has_photos": False, "has_response": False,
		"title": "", "page_chars": len(text), "has_review_section": False}

	# The product title sits immediately above the buy-box rating, past a store
	# link and a bare repeat of the average. Anchoring on the FIRST
	# `N.N out of 5 stars` line and walking BACK is what finds it: a
	# first-substantial-line scan instead picks up the keyboard-shortcut help
	# text, which is what the first version of this did.
	anchor = -1
	for i in range(len(rows)):
		r = rows[i]
		cut = r.find(" out of 5 stars")
		if cut > 0 and "." in r[:cut]:
			anchor = i
			break
	if anchor > 0:
		j = anchor - 1
		while j >= 0 and anchor - j < 8:
			cand = rows[j]
			low = cand.lower()
			bare = True
			for ch in cand:
				if not (ch.isdigit() or ch == "." or ch == "," or ch == "("
						or ch == ")" or ch == " "):
					bare = False
					break
			if (cand == "" or bare or low.startswith("visit the")
					or low.startswith("brand:") or low.startswith("click to")):
				j -= 1
				continue
			if len(cand) >= 8:
				out["title"] = _short(cand, MAX_TITLE)
			break

	head = _find_line(rows, "Customer reviews", 0)
	if head >= 0:
		i = _find_contains(rows, " out of 5 stars", head)
		if 0 <= i < head + 8:
			num = rows[i][:rows[i].find(" out of 5 stars")].strip()
			whole = _digits_only(num[:num.find(".")] if "." in num else num)
			frac = ""
			if "." in num:
				frac = _digits_only(num[num.find(".") + 1:])[:1]
			if whole != "":
				val = int(whole) * 10 + (int(frac) if frac != "" else 0)
				if 0 <= val <= 50:
					out["avg_rating_x10"] = val
		g = _find_contains(rows, "global ratings", head)
		if g < 0:
			g = _find_contains(rows, "global rating", head)
		if 0 <= g < head + 10:
			out["total_ratings"] = _int_from_commas(
				rows[g][:rows[g].lower().find("global")])
		# The histogram: `5 star` on one line, `83%` on the next.
		pcts = []
		for star in (5, 4, 3, 2, 1):
			k = _find_line(rows, str(star) + " star", head)
			if k < 0 or k + 1 >= len(rows) or not rows[k + 1].endswith("%"):
				pcts = []
				break
			d = _digits_only(rows[k + 1])
			if d == "":
				pcts = []
				break
			pcts.append(_clamp(int(d), 0, 100))
		if len(pcts) == 5:
			out["pct"] = pcts

	for marker in ("Reviews with images", "See all photos", "Customer images"):
		if _find_line(rows, marker, 0) >= 0:
			out["has_photos"] = True
	for marker in ("Manufacturer's response", "Response from",
			"Seller's response"):
		if _find_prefix(rows, marker, 0) >= 0:
			out["has_response"] = True

	start = _find_prefix(rows, "Top reviews from", head if head >= 0 else 0)
	if start < 0:
		start = _find_prefix(rows, "Top review", head if head >= 0 else 0)
	if start < 0:
		return out
	out["has_review_section"] = True

	reviews = []
	i = start + 1
	while i < len(rows) and len(reviews) < MAX_REVIEWS:
		row = rows[i]
		cut = row.find(" out of 5 stars")
		if cut <= 0 or cut > 2:
			i += 1
			continue
		rating_txt = row[:cut]
		if not rating_txt.isdigit():
			i += 1
			continue
		rating = int(rating_txt)
		if rating < 1 or rating > 5:
			i += 1
			continue

		name_i = _prev_nonempty(rows, i)
		name = rows[name_i] if name_i >= 0 else ""
		if name.endswith(" out of 5 stars") or name == "":
			name = ""

		title = ""
		j = i + 1
		if j < len(rows) and rows[j] != "" and not rows[j].startswith("Reviewed in"):
			title = _short(rows[j], MAX_TITLE)
			j += 1

		day = 0
		verified = False
		scan = j
		limit = min(len(rows), i + 8)
		while scan < limit:
			r = rows[scan]
			if r.startswith("Reviewed in"):
				on = r.rfind(" on ")
				if on > 0:
					day = _parse_date(r[on + 4:], today_day)
				scan += 1
				continue
			if r == "Verified Purchase":
				verified = True
				scan += 1
				continue
			if r == "":
				scan += 1
				continue
			break

		body = ""
		helpful = -1
		k = scan
		while k < len(rows):
			r = rows[k]
			if r in AMZ_STOP:
				break
			hc = _helpful_count(r)
			if hc >= 0:
				helpful = hc
				break
			if r.find(" out of 5 stars") > 0 and r.find(" out of 5 stars") <= 2:
				break
			if r != "":
				body += (" " if body != "" else "") + r
			k += 1
		while k < len(rows) and k < scan + 60:
			hc = _helpful_count(rows[k])
			if hc >= 0:
				helpful = hc
				break
			if rows[k] == "Report":
				break
			k += 1

		reviews.append({"name": name, "rating": rating, "title": title,
			"day": day, "verified": verified, "body": body,
			"helpful": helpful})
		i = max(k, i + 1)

	out["reviews"] = reviews
	return out


def _parse_gplay(text: str, today_day: int) -> dict:
	"""Google Play. Review blocks are anchored on the literal `more_vert` line
	the overflow menu renders as — see docs/PROBE.md §3.2.

	The rating HISTOGRAM is deliberately not read. The labels `5 4 3 2 1` do
	render, but the bar values are DRAWN and not written, so there is nothing
	there to read. Rule 7: that dimension is UNAVAILABLE, not zero."""
	rows = _lines(text)
	out = {"reviews": [], "avg_rating_x10": UNAVAIL, "total_ratings": UNAVAIL,
		"pct": [UNAVAIL] * 5, "has_photos": False, "has_response": False,
		"title": "", "page_chars": len(text),
		"has_review_section": _find_line(rows, "more_vert", 0) >= 0}

	for i in range(len(rows)):
		r = rows[i]
		if r.startswith("google_logo"):
			k = _prev_nonempty(rows, len(rows))
			for j in range(i + 1, min(len(rows), i + 14)):
				cand = rows[j]
				if cand in ("Games", "Apps", "Movies & TV", "Books", "Kids",
						"Gift Cards", "search", "help_outline", ""):
					continue
				out["title"] = _short(cand, MAX_TITLE)
				break
			break

	head = _find_line(rows, "Ratings and reviews", 0)
	if head >= 0:
		for j in range(head, min(len(rows), head + 20)):
			r = rows[j]
			if r.endswith(" reviews") or r.endswith(" review"):
				count_txt = r[:r.rfind(" review")]
				# The SECTION HEADING is `Ratings and reviews`, which also ends
				# with " reviews". Without a digit test the count parses out of
				# the word "and" as zero — and a zero review count is a real
				# measurement, so nothing downstream would have caught it.
				if _digits_only(count_txt) == "":
					continue
				out["total_ratings"] = _int_from_commas(count_txt)
				prev = _prev_nonempty(rows, j)
				if prev >= 0 and "." in rows[prev]:
					d = rows[prev]
					w = _digits_only(d[:d.find(".")])
					f = _digits_only(d[d.find(".") + 1:])[:1]
					if w != "":
						val = int(w) * 10 + (int(f) if f != "" else 0)
						if 0 <= val <= 50:
							out["avg_rating_x10"] = val
				break

	i = max(head, 0)
	reviews = []
	while i < len(rows) and len(reviews) < MAX_REVIEWS:
		k = _find_line(rows, "more_vert", i)
		if k < 0:
			break
		name_i = _prev_nonempty(rows, k)
		name = rows[name_i] if name_i >= 0 else ""
		day = 0
		body = ""
		helpful = -1
		j = k + 1
		if j < len(rows):
			day = _parse_date(rows[j], today_day)
			j += 1
		while j < len(rows):
			r = rows[j]
			if r == "Did you find this helpful?" or r == "more_vert":
				break
			hc = _helpful_count(r)
			if hc >= 0:
				helpful = hc
				break
			if r in ("Yes", "No", "See all reviews", "flag"):
				break
			if r != "":
				body += (" " if body != "" else "") + r
			j += 1
		if name != "" and body != "":
			reviews.append({"name": name, "rating": 0, "title": "",
				"day": day, "verified": False, "body": body,
				"helpful": helpful})
		i = k + 1

	out["reviews"] = reviews
	return out


def _parse_appstore(text: str, today_day: int) -> dict:
	"""Apple App Store. Blocks are `title / date / nickname / body / more`, and
	the section runs from `Ratings & Reviews` to `What's New` — see
	docs/PROBE.md §3.3.

	Neither a per-review star rating nor a helpful vote appears anywhere in the
	rendered text, so `rating_distribution` and `engagement_signals` are both
	UNAVAILABLE on this platform, by rule 7."""
	rows = _lines(text)
	out = {"reviews": [], "avg_rating_x10": UNAVAIL, "total_ratings": UNAVAIL,
		"pct": [UNAVAIL] * 5, "has_photos": False, "has_response": False,
		"title": "", "page_chars": len(text), "has_review_section": False}

	head = _find_line(rows, "Ratings & Reviews", 0)
	if head < 0:
		head = _find_line(rows, "Ratings and Reviews", 0)

	# The app name follows the device-platform list. The bare line `TV` is not
	# specific enough on its own — it is a store category too — so the anchor is
	# a `TV` with `iPhone` a few lines above it.
	for i in range(len(rows)):
		if rows[i] != "TV" or i + 1 >= len(rows) or rows[i + 1] == "":
			continue
		seen_iphone = False
		for k in range(max(0, i - 8), i):
			if rows[k] == "iPhone":
				seen_iphone = True
		if seen_iphone:
			out["title"] = _short(rows[i + 1], MAX_TITLE)
			break

	if head < 0:
		return out
	out["has_review_section"] = True

	i = head + 1
	if i < len(rows) and "." in rows[i]:
		d = rows[i]
		w = _digits_only(d[:d.find(".")])
		f = _digits_only(d[d.find(".") + 1:])[:1]
		if w != "":
			val = int(w) * 10 + (int(f) if f != "" else 0)
			if 0 <= val <= 50:
				out["avg_rating_x10"] = val
	r = _find_contains(rows, "Ratings", head + 1)
	if 0 <= r < head + 8:
		out["total_ratings"] = _int_from_commas(rows[r][:rows[r].find("Ratings")])

	stop = _find_line(rows, "What's New", head)
	if stop < 0:
		stop = _find_line(rows, "What’s New", head)
	if stop < 0:
		stop = _find_line(rows, "App Privacy", head)
	if stop < 0:
		stop = len(rows)

	reviews = []
	i = head + 1
	while i < stop and len(reviews) < MAX_REVIEWS:
		if rows[i] == "" or rows[i] == "out of 5" or rows[i].endswith("Ratings"):
			i += 1
			continue
		# A block header is three consecutive non-empty lines whose MIDDLE one
		# parses as a date. Anchoring on the date rather than on position is
		# what lets `Jan 21` and `06/14/2023` — both present on one page — be
		# read by the same rule.
		if i + 2 < stop:
			day = _parse_date(rows[i + 1], today_day)
			if day > 0 and rows[i] != "" and rows[i + 2] != "":
				title = _short(rows[i], MAX_TITLE)
				name = rows[i + 2]
				body = ""
				j = i + 3
				while j < stop:
					if rows[j] == "more":
						break
					nxt = _parse_date(rows[j + 1], today_day) if j + 2 < stop else 0
					if nxt > 0 and rows[j] != "" and body != "":
						break
					if rows[j] != "":
						body += (" " if body != "" else "") + rows[j]
					j += 1
				if body != "":
					reviews.append({"name": name, "rating": 0, "title": title,
						"day": day, "verified": False, "body": body,
						"helpful": -1})
				i = j + 1
				continue
		i += 1

	out["reviews"] = reviews
	return out


# ──────────────────────────────────────────────── reviewer identity heuristics

GENERIC_NAMES = ("amazon customer", "customer", "a customer", "anonymous",
	"kindle customer", "google user", "a google user", "app store user",
	"user", "guest", "buyer", "verified buyer")

VOWELS = "aeiouy"


def _weak_handle(name: str) -> bool:
	"""Does this reviewer identity look generated rather than chosen?

	Four shapes, each of which shows up in bought-review batches and rarely in
	organic ones: a platform's own placeholder, a digit-heavy handle, a long
	single token with almost no vowels, and a repeated syllable. None of them
	PROVES anything on its own — which is why this feeds a percentage across the
	whole page rather than a verdict on one reviewer."""
	n = name.strip()
	if len(n) < 3:
		return True
	if n.lower() in GENERIC_NAMES:
		return True

	digits = 0
	letters = 0
	vowels = 0
	for ch in n:
		if ch.isdigit():
			digits += 1
		elif ch.isalpha():
			letters += 1
			if ch.lower() in VOWELS:
				vowels += 1
	if digits >= 3:
		return True
	if letters == 0:
		return True

	best_run = 1
	run = 1
	for i in range(1, len(n)):
		if n[i] == n[i - 1]:
			run += 1
			if run > best_run:
				best_run = run
		else:
			run = 1
	if best_run >= 4:
		return True

	# A two-character syllable repeated three times running: `hahahaha`.
	low = n.lower()
	for i in range(len(low) - 5):
		bi = low[i:i + 2]
		if bi[0].isalpha() and bi[1].isalpha() and low[i:i + 6] == bi + bi + bi:
			return True

	tokens = []
	for t in n.split(" "):
		if t.strip() != "":
			tokens.append(t)
	if len(tokens) == 1 and letters >= 7 and vowels * 100 < letters * 30:
		return True
	return False


def _ttr(body: str) -> int:
	"""Type-token ratio over a FIXED-LENGTH sample of one review, in percent.

	Standardised to the first 100 words on purpose. A raw distinct/total ratio
	falls as text gets longer — Heaps' law — so an unstandardised measure would
	score a page of long, thoughtful reviews as less varied than a page of
	three-line ones, which is backwards."""
	w = _words(body)
	if len(w) < 12:
		return -1
	sample = w[:100]
	seen = {}
	for word in sample:
		seen[word] = 1
	return _pct(len(seen), len(sample))


def _opening(body: str) -> str:
	w = _words(body)
	if len(w) < PREFIX_WORDS:
		return " ".join(w)
	return " ".join(w[:PREFIX_WORDS])


def _pack(value: typing.Any, available: bool, step: int) -> int:
	"""THE ONLY place UNAVAIL is written. Every nullable vector field goes
	through here, so "this page does not publish that" has one spelling in the
	whole contract rather than forty."""
	if not available:
		return UNAVAIL
	return _q(_as_int(value, 0), step)


def _features(parsed: dict, platform: str) -> dict:
	"""The feature vector: twenty integers, every one quantised.

	THIS is the consensus axis. Two validators render the same page seconds
	apart, and `_agrees` demands exact equality, so every figure here is rounded
	before it can ever be compared — ordinals to eight buckets, counts to three
	significant figures, percentages to the nearest five. The tolerance lives in
	the quantisation and never in the comparison."""
	dims = PLATFORM_DIMS[platform]
	reviews = parsed.get("reviews") or []
	n = len(reviews)

	days = []
	bodies = []
	names = []
	verified = 0
	helpful_shown = 0
	helpful_sum = 0
	for r in reviews:
		d = _as_int(r.get("day"), 0)
		if d > 0:
			days.append(d)
		bodies.append(str(r.get("body") or ""))
		names.append(str(r.get("name") or ""))
		if r.get("verified"):
			verified += 1
		h = _as_int(r.get("helpful"), -1)
		if h >= 0:
			helpful_shown += 1
			helpful_sum += h

	# --- timing
	day_counts = {}
	for d in days:
		day_counts[d] = int(day_counts.get(d, 0)) + 1
	max_same = 0
	for d in day_counts:
		if day_counts[d] > max_same:
			max_same = day_counts[d]
	span = 0
	if len(days) >= 2:
		span = max(days) - min(days)

	# --- quality
	lengths = []
	short = 0
	for b in bodies:
		lengths.append(len(b))
		if len(b) < SHORT_REVIEW_CHARS:
			short += 1
	openings = {}
	for b in bodies:
		key = _opening(b)
		if key != "":
			openings[key] = int(openings.get(key, 0)) + 1
	dup = 0
	for key in openings:
		if openings[key] > 1:
			dup += openings[key]
	ttrs = []
	for b in bodies:
		t = _ttr(b)
		if t >= 0:
			ttrs.append(t)
	lex = 0
	if len(ttrs) > 0:
		total = 0
		for t in ttrs:
			total += t
		lex = total // len(ttrs)

	# --- identity
	distinct_names = {}
	weak = 0
	for nm in names:
		key = nm.strip().lower()
		if key != "":
			distinct_names[key] = 1
		if _weak_handle(nm):
			weak += 1

	pct = parsed.get("pct") or [UNAVAIL] * 5
	has_hist = len(pct) == 5 and _avail(pct[0]) and dims["rating"]

	return {
		"reviews_parsed": n,
		"avg_rating_x10": _pack(parsed.get("avg_rating_x10"),
			_avail(parsed.get("avg_rating_x10")), 1),
		"total_ratings": _pack(_sig3(_as_int(parsed.get("total_ratings"), 0)),
			_avail(parsed.get("total_ratings")), 1),
		"pct_5": _pack(pct[0] if has_hist else 0, has_hist, 1),
		"pct_4": _pack(pct[1] if has_hist else 0, has_hist, 1),
		"pct_3": _pack(pct[2] if has_hist else 0, has_hist, 1),
		"pct_2": _pack(pct[3] if has_hist else 0, has_hist, 1),
		"pct_1": _pack(pct[4] if has_hist else 0, has_hist, 1),
		"dated_reviews": len(days),
		"distinct_days": len(day_counts),
		"max_same_day": max_same,
		"span_days": _q(span, 5),
		"median_chars": _q(_median(lengths), 25),
		"short_pct": _q(_pct(short, n), Q_STEP),
		"dup_open_pct": _q(_pct(dup, n), Q_STEP),
		"lexical_pct": _q(lex, Q_STEP),
		"verified_pct": _pack(_pct(verified, n), dims["credibility_basis"]
			== "verified-purchase" and n > 0, Q_STEP),
		"distinct_names_pct": _q(_pct(len(distinct_names), n), Q_STEP),
		"weak_handle_pct": _q(_pct(weak, n), Q_STEP),
		"helpful_pct": _pack(_pct(helpful_shown, n),
			dims["engagement"] and n > 0, Q_STEP),
		"helpful_total": _pack(_sig3(helpful_sum), dims["engagement"], 1),
		"has_photos": 1 if parsed.get("has_photos") else 0,
		"has_response": 1 if parsed.get("has_response") else 0,
		# Quantised to 500 so that a page differing by a few bytes of markup
		# between two renders is not a disagreement.
		"page_chars": _clamp(_q(_as_int(parsed.get("page_chars"), 0), 500),
			0, PAGE_CAP),
		"reviews_section": 1 if parsed.get("has_review_section") else 0,
	}


# ───────────────────────────────────────────────────── the rubric: five ladders
#
# Every ladder takes the AGREED vector and returns an ordinal 0-7 where 0 is the
# worst outcome and 7 the best, or UNAVAIL where the platform does not publish
# the evidence. These are pure functions of the vector: `_write` runs them AGAIN
# after consensus rather than storing the leader's numbers, and `verify_check`
# runs them a third time years later off nothing but the stored record.


def _dim_timing(f: dict, dims: dict) -> int:
	"""Are the reviews clustered on particular dates, or spread out?

	Needs DATES, not reviews: a page whose reviews all rendered without a
	parseable date cannot be measured on this axis and says so."""
	n = _as_int(f.get("reviews_parsed"), 0)
	dated = _as_int(f.get("dated_reviews"), 0)
	if not dims["timing"] or dated < MIN_REVIEWS:
		return UNAVAIL
	distinct = _as_int(f.get("distinct_days"), 0)
	burst = _as_int(f.get("max_same_day"), 0)
	span = _as_int(f.get("span_days"), 0)

	spread = _pct(distinct, dated)
	if spread >= 95:
		score = 7
	elif spread >= 85:
		score = 6
	elif spread >= 70:
		score = 5
	elif spread >= 55:
		score = 4
	elif spread >= 40:
		score = 3
	elif spread >= 30:
		score = 2
	elif spread >= 20:
		score = 1
	else:
		score = 0

	burst_pct = _pct(burst, dated)
	if burst_pct >= 60:
		score -= 3
	elif burst_pct >= 40:
		score -= 2
	elif burst_pct >= 25:
		score -= 1

	# Span matters independently of spread: eight reviews on eight consecutive
	# days are perfectly "spread" and still a campaign.
	if span >= 365:
		score += 1
	elif span <= 14 and dated >= 5:
		score -= 2
	elif span <= 30 and dated >= 5:
		score -= 1
	return _clamp(score, 0, ORDINAL_MAX)


def _dim_rating(f: dict, dims: dict) -> int:
	"""Is the rating histogram a shape a real product produces?

	The signature of a bought page is an overwhelming five-star share with no
	negative tail and no middle at all. Seven additive steps rather than one
	cliff, so that a genuinely well-liked product is not called manipulated for
	being well liked."""
	if not dims["rating"] or not _avail(f.get("pct_5")):
		return UNAVAIL
	p5 = _as_int(f.get("pct_5"), 0)
	p4 = _as_int(f.get("pct_4"), 0)
	p3 = _as_int(f.get("pct_3"), 0)
	p2 = _as_int(f.get("pct_2"), 0)
	p1 = _as_int(f.get("pct_1"), 0)
	if p5 + p4 + p3 + p2 + p1 == 0:
		return UNAVAIL
	neg = p1 + p2
	mid = p3 + p4

	score = 0
	if p5 <= 95:
		score += 1
	if p5 <= 88:
		score += 1
	if p5 <= 80:
		score += 1
	if neg >= 1:
		score += 1
	if neg >= 4:
		score += 1
	if mid >= 8:
		score += 1
	if mid >= 15:
		score += 1
	return _clamp(score, 0, ORDINAL_MAX)


def _dim_quality(f: dict, dims: dict) -> int:
	"""Are the reviews written, or generated?

	Length is the base, variety adds, duplication and a page full of one-liners
	subtract. `median_chars` rather than a mean: one 4,000-character essay must
	not carry nine ten-word reviews."""
	n = _as_int(f.get("reviews_parsed"), 0)
	if not dims["quality"] or n < MIN_REVIEWS:
		return UNAVAIL
	med = _as_int(f.get("median_chars"), 0)
	short = _as_int(f.get("short_pct"), 0)
	dup = _as_int(f.get("dup_open_pct"), 0)
	lex = _as_int(f.get("lexical_pct"), 0)

	if med >= 600:
		score = 4
	elif med >= 350:
		score = 3
	elif med >= 200:
		score = 2
	elif med >= 100:
		score = 1
	else:
		score = 0

	if lex >= 60:
		score += 2
	elif lex >= 45:
		score += 1

	if dup == 0:
		score += 1
	elif dup >= 40:
		score -= 2
	elif dup >= 20:
		score -= 1

	if short >= 60:
		score -= 2
	elif short >= 35:
		score -= 1
	return _clamp(score, 0, ORDINAL_MAX)


def _dim_credibility(f: dict, dims: dict) -> int:
	"""Do the reviewers look like people with a history?

	TWO BASES, and which one was used is stored on the record and shown in the
	UI, because they are not the same claim:

	  verified-purchase  Amazon says outright that the reviewer bought the item.
	                     Strong, and the only basis that can reach 7.
	  identity-shape     Google Play and the App Store publish no purchase
	                     signal at all, so all that is left is whether the
	                     reviewer identities look chosen or generated. That
	                     starts at a NEUTRAL 4 and moves only on evidence — a
	                     page of ordinary-looking names is not evidence of
	                     anything and must not be scored as though it were.
	"""
	n = _as_int(f.get("reviews_parsed"), 0)
	if not dims["credibility"] or n < MIN_REVIEWS:
		return UNAVAIL
	distinct = _as_int(f.get("distinct_names_pct"), 0)
	weak = _as_int(f.get("weak_handle_pct"), 0)

	if dims["credibility_basis"] == "verified-purchase":
		if not _avail(f.get("verified_pct")):
			return UNAVAIL
		v = _as_int(f.get("verified_pct"), 0)
		if v >= 95:
			score = 7
		elif v >= 85:
			score = 6
		elif v >= 70:
			score = 5
		elif v >= 55:
			score = 4
		elif v >= 40:
			score = 3
		elif v >= 25:
			score = 2
		elif v >= 10:
			score = 1
		else:
			score = 0
		if weak >= 50:
			score -= 2
		elif weak >= 30:
			score -= 1
		if distinct < 90:
			score -= 1
		return _clamp(score, 0, ORDINAL_MAX)

	score = 4
	if distinct >= 100:
		score += 1
	elif distinct < 80:
		score -= 1
	if weak >= 50:
		score -= 3
	elif weak >= 30:
		score -= 2
	elif weak >= 15:
		score -= 1
	# 6, not 7. The top of this ladder is "established reviewers", and no page
	# without a purchase signal can support that claim. Declared, not hidden:
	# the basis travels with the record.
	return _clamp(score, 0, 6)


def _dim_engagement(f: dict, dims: dict) -> int:
	"""Did anyone react to these reviews?

	Scored as EARNED OUT OF POSSIBLE for the platform, not on a fixed ladder.
	Amazon publishes helpful votes, a vote total, customer photos and seller
	responses — four signals, eight points. Google Play publishes two of them,
	five points. Normalising by what the platform actually offers is what stops
	an app being marked down for Google not having a photo feature."""
	n = _as_int(f.get("reviews_parsed"), 0)
	if not dims["engagement"] or n < MIN_REVIEWS:
		return UNAVAIL
	if not _avail(f.get("helpful_pct")):
		return UNAVAIL
	possible = _as_int(dims.get("engagement_max"), 0)
	if possible <= 0:
		return UNAVAIL

	hp = _as_int(f.get("helpful_pct"), 0)
	if hp >= 80:
		earned = 4
	elif hp >= 60:
		earned = 3
	elif hp >= 40:
		earned = 2
	elif hp >= 20:
		earned = 1
	else:
		earned = 0

	if _as_int(f.get("helpful_total"), 0) >= 50:
		earned += 1
	if possible >= 8:
		if _as_int(f.get("has_photos"), 0) == 1:
			earned += 2
		if _as_int(f.get("has_response"), 0) == 1:
			earned += 1
	earned = _clamp(earned, 0, possible)
	return _clamp((earned * ORDINAL_MAX) // possible, 0, ORDINAL_MAX)


DIM_FUNCS = {
	"timing_pattern": _dim_timing,
	"rating_distribution": _dim_rating,
	"review_quality": _dim_quality,
	"reviewer_credibility": _dim_credibility,
	"engagement_signals": _dim_engagement,
}


def _why_inconclusive(f: dict, n: int, available: int) -> str:
	"""Say WHICH failure this was, in words a submitter can act on.

	"0 reviews parsed" is ambiguous between a product nobody has reviewed and a
	page that was served without its review section — and those call for
	opposite responses (believe it, versus check again later). The vector
	already carries both facts; this reads them."""
	if n < MIN_REVIEWS:
		if _as_int(f.get("reviews_section"), 0) == 0:
			return ("the page rendered "
				+ str(_as_int(f.get("page_chars"), 0))
				+ " characters and stopped before its review list, so there "
				"was nothing to read")
		return ("the review list rendered but only " + str(n)
			+ " individual reviews were on it; "
			+ str(MIN_REVIEWS) + " is the minimum to judge a page")
	return ("only " + str(available) + " of 100 rubric points could be "
		"measured on this page")


def _score(f: dict, platform: str) -> dict:
	"""Ordinals, the weighted overall, and the trust level. PURE.

	Recomputed from the agreed vector in `_write` and again in `verify_check`.
	The leader's own arithmetic never reaches storage — rule 8."""
	dims = PLATFORM_DIMS.get(platform) or PLATFORM_DIMS[P_AMAZON]
	scores = {}
	available = 0
	weighted = 0
	for key in DIM_KEYS:
		val = DIM_FUNCS[key](f, dims)
		scores[key] = val
		if _avail(val):
			w = DIM_WEIGHTS[key]
			available += w
			weighted += _as_int(val, 0) * w

	n = _as_int(f.get("reviews_parsed"), 0)
	if n < MIN_REVIEWS or available < MIN_AVAILABLE_WEIGHT:
		# RULE 7. Not a low score, and not a pass. `is_authentic` answers False
		# here, and `require_authentic` reverts — a guard that waved through
		# every page it could not read would be a guard on nothing.
		return {"scores": scores, "overall": 0, "trust_level": T_INCONCLUSIVE,
			"available_weight": available,
			"credibility_basis": str(dims["credibility_basis"]),
			"why": _why_inconclusive(f, n, available)}

	overall = _q(_clamp((weighted * 100) // (ORDINAL_MAX * available), 0, 100),
		Q_STEP)
	if overall >= AUTHENTIC_MIN:
		level = T_AUTHENTIC
	elif overall >= SUSPICIOUS_MIN:
		level = T_SUSPICIOUS
	else:
		level = T_MANIPULATED
	return {"scores": scores, "overall": overall, "trust_level": level,
		"available_weight": available,
		"credibility_basis": str(dims["credibility_basis"]), "why": ""}


# ─────────────────────────────────────────── the content hash and the two gates

def _fnv(s: str) -> str:
	"""FNV-1a 64, length-prefixed.

	Hashes THE AGREED VECTOR, never the raw page. A rendered Amazon page is 38 KB
	of live text whose "Top reviews" selection rotates, so a body hash would
	differ between two honest nodes for reasons no rubric reads — the exact
	failure docs/PROBE.md §4 exists to rule out."""
	h = 0xCBF29CE484222325
	for b in str(s).encode("utf-8"):
		h = h ^ b
		h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
	return str(len(s)) + ":" + format(h, "016x")


def _canon(features: dict) -> str:
	"""The consensus object in one canonical form: sorted keys, plain ints, no
	spaces. Two nodes that agree produce identical bytes whatever order they
	happened to fill the dict in."""
	out = {}
	for key in sorted(FEATURE_RANGE.keys()):
		out[key] = _as_int(features.get(key, 0), UNAVAIL)
	return json.dumps(out, sort_keys=True, separators=(",", ":"))


def _digest(identity: dict, features: dict) -> str:
	"""content_hash = hash(identity strings + feature vector).

	The identity strings are IN the hash, not beside it. A hash over the vector
	alone would be identical for two different products that happened to score
	the same, so it could not tell a check of one listing from a check of a
	clone wearing its numbers."""
	parts = []
	for k in IDENTITY_KEYS:
		parts.append(str(identity.get(k, "")))
	return _fnv("|".join(parts) + "|" + _canon(features))


def _coherent(out: dict) -> bool:
	"""Is this result one the rubric could have produced, judged on the LEADER'S
	OWN BYTES?

	Applied by every validator BEFORE it re-fetches anything, so an incoherent
	leader is voted down identically by all of them and no validator becomes a
	source of disagreement itself. Applied again in `check_reviews` after
	consensus, belt and braces.

	This is the gate that makes rule 8 true: a leader that reports a vector and
	a set of scores that do not follow from it is refused here, so the only
	numbers that can reach storage are ones that follow from the vector — and
	`_write` then recomputes them anyway."""
	if not isinstance(out, dict):
		return False
	feats = out.get("features")
	if not isinstance(feats, dict):
		return False

	# Every vector field present, an int (never a bool), and inside its declared
	# range or exactly UNAVAIL where that is allowed.
	for key in FEATURE_RANGE:
		if key not in feats:
			return False
		raw = feats[key]
		if isinstance(raw, bool) or not isinstance(raw, int):
			return False
		lo, hi = FEATURE_RANGE[key]
		if raw == UNAVAIL:
			if key not in NULLABLE:
				return False
			continue
		if raw < lo or raw > hi:
			return False
	if len(feats) != len(FEATURE_RANGE):
		return False

	platform = str(out.get("platform", ""))
	if platform not in PLATFORMS:
		return False
	for k in IDENTITY_KEYS:
		if not isinstance(out.get(k), str):
			return False
	if len(str(out.get("url_key", ""))) == 0:
		return False
	if len(str(out.get("title", ""))) > MAX_TITLE:
		return False

	# Internal consistency the leader cannot fake past: counts that cannot
	# exceed the number of reviews, a histogram that sums to roughly 100.
	n = _as_int(feats.get("reviews_parsed"), 0)
	for key in ("dated_reviews", "distinct_days", "max_same_day"):
		if _as_int(feats.get(key), 0) > n:
			return False
	if _as_int(feats.get("distinct_days"), 0) > _as_int(feats.get("dated_reviews"), 0):
		return False
	if _as_int(feats.get("max_same_day"), 0) > _as_int(feats.get("dated_reviews"), 0):
		return False
	if _avail(feats.get("pct_5")):
		total = 0
		for key in ("pct_5", "pct_4", "pct_3", "pct_2", "pct_1"):
			if not _avail(feats.get(key)):
				return False
			total += _as_int(feats.get(key), 0)
		# Amazon rounds each band to a whole percent, so the five need not sum
		# to exactly 100 — but they must sum to something near it, or they are
		# not a histogram.
		if total < 90 or total > 110:
			return False

	# The leader's arithmetic must match the rubric run on the leader's own
	# vector. This is where a forged score dies.
	mine = _score(feats, platform)
	theirs = out.get("scores")
	if not isinstance(theirs, dict):
		return False
	for key in DIM_KEYS:
		if _as_int(theirs.get(key), -2) != _as_int(mine["scores"][key], -3):
			return False
	if _as_int(out.get("overall"), -2) != _as_int(mine["overall"], -3):
		return False
	if str(out.get("trust_level", "")) != mine["trust_level"]:
		return False
	if _as_int(out.get("available_weight"), -2) != _as_int(
			mine["available_weight"], -3):
		return False
	if str(out.get("credibility_basis", "")) != mine["credibility_basis"]:
		return False
	if str(out.get("content_hash", "")) != _digest(out, feats):
		return False
	return True


def _agrees(theirs: dict, mine: dict) -> bool:
	"""Does the leader's result match what this validator independently found?

	EVERY FIELD ON THE AXIS, compared exactly — the twenty vector integers, the
	three identity strings and the content hash. Rule 1: a field that is not
	compared here is a field the leader can forge.

	There is no tolerance in this function and there never will be. The noise
	two renders apart is absorbed by the QUANTISERS in `_features`; a tolerance
	here would mean two different accepted outputs for one request, and then
	which one is the check?"""
	if not isinstance(theirs, dict) or not isinstance(mine, dict):
		return False
	a = theirs.get("features")
	b = mine.get("features")
	if not isinstance(a, dict) or not isinstance(b, dict):
		return False
	for key in FEATURE_RANGE:
		if _as_int(a.get(key), -1) != _as_int(b.get(key), -2):
			return False
	for key in IDENTITY_KEYS:
		if str(theirs.get(key, "")) != str(mine.get(key, "")):
			return False
	return str(theirs.get("content_hash", "")) != "" and \
		str(theirs.get("content_hash", "")) == str(mine.get("content_hash", ""))


def _collect(url_key: str, fetch_url: str, platform: str, now_day: int) -> dict:
	"""Fetch, extract, quantise, score. RUN IDENTICALLY BY THE LEADER AND BY
	EVERY VALIDATOR — that symmetry is the whole of the consensus design.

	Returns a dict with `ok` false and a reason rather than raising, so that a
	page which cannot be read is a refusal the caller gets refunded for rather
	than a revert that keeps their deposit."""
	try:
		text = _render_page(fetch_url)
	except Exception as e:
		# render() raises on every non-2xx and on a blocked page alike. Both are
		# NO EVIDENCE. Settling low on a fetch that never happened would let a
		# competitor manufacture a MANIPULATED verdict by making a page briefly
		# unreachable.
		return {"ok": False, "retry": True,
			"why": "the page could not be rendered (" + _short(str(e), 80) + ")"}
	if len(text.strip()) < 200:
		return {"ok": False, "retry": True,
			"why": "the page rendered almost empty; nothing to read"}

	low = text.lower()
	for wall in ("robot or human", "are you a human", "enter the characters",
			"verifying connection", "access denied", "captcha"):
		if wall in low:
			return {"ok": False, "retry": True,
				"why": "the platform served a bot challenge instead of the page"}
	if platform == P_AMAZON and "page not found" in low and len(text) < 4000:
		return {"ok": False, "fail": True,
			"why": "Amazon has no product at that ASIN"}

	if platform == P_AMAZON:
		parsed = _parse_amazon(text, now_day)
	elif platform == P_GPLAY:
		parsed = _parse_gplay(text, now_day)
	elif platform == P_APPSTORE:
		parsed = _parse_appstore(text, now_day)
	else:
		return {"ok": False, "fail": True, "why": "unsupported platform"}

	feats = _features(parsed, platform)
	scored = _score(feats, platform)
	out = {
		"ok": True,
		"url_key": str(url_key),
		"platform": str(platform),
		"title": _short(str(parsed.get("title") or ""), MAX_TITLE),
		"features": feats,
		"scores": scored["scores"],
		"overall": scored["overall"],
		"trust_level": scored["trust_level"],
		"available_weight": scored["available_weight"],
		"credibility_basis": scored["credibility_basis"],
		"why": scored["why"],
	}
	out["content_hash"] = _digest(out, feats)
	return out


# The PLATFORM_DIMS key for a dimension. The table is keyed by short names
# (`timing`) and the rubric by long ones (`timing_pattern`); one mapping in one
# place beats a parallel pair of strings that can drift apart.
DIM_FLAG = {
	"timing_pattern": "timing",
	"rating_distribution": "rating",
	"review_quality": "quality",
	"reviewer_credibility": "credibility",
	"engagement_signals": "engagement",
}


def _dim_flag(dim_key: str) -> str:
	return DIM_FLAG[dim_key]


def _stored_vector(rec) -> dict:
	"""The feature vector read back OUT of a stored record.

	`verify_check` runs the rubric on this, so it has to reproduce exactly what
	`_features` produced — including UNAVAIL where a platform published nothing.
	Storage holds the sentinel verbatim, so this is a straight read; the one
	thing it must not do is "clean up" a 255 into a 0, which would make every
	unavailable dimension verify as a real zero."""
	return {
		"reviews_parsed": int(rec.reviews_parsed),
		"avg_rating_x10": int(rec.avg_rating_x10),
		"total_ratings": int(rec.total_ratings),
		"pct_5": int(rec.pct_5), "pct_4": int(rec.pct_4),
		"pct_3": int(rec.pct_3), "pct_2": int(rec.pct_2),
		"pct_1": int(rec.pct_1),
		"dated_reviews": int(rec.dated_reviews),
		"distinct_days": int(rec.distinct_days),
		"max_same_day": int(rec.max_same_day),
		"span_days": int(rec.span_days),
		"median_chars": int(rec.median_chars),
		"short_pct": int(rec.short_pct),
		"dup_open_pct": int(rec.dup_open_pct),
		"lexical_pct": int(rec.lexical_pct),
		"verified_pct": int(rec.verified_pct),
		"distinct_names_pct": int(rec.distinct_names_pct),
		"weak_handle_pct": int(rec.weak_handle_pct),
		"helpful_pct": int(rec.helpful_pct),
		"helpful_total": int(rec.helpful_total),
		"has_photos": 1 if rec.has_photos else 0,
		"has_response": 1 if rec.has_response else 0,
		"page_chars": int(rec.page_chars),
		"reviews_section": 1 if rec.reviews_section else 0,
	}


def _pay(who: Address, amount: int) -> None:
	"""Send native value. THE ONLY WAY MONEY LEAVES THIS CONTRACT.

	Written out here rather than inlined because getting it wrong is SILENT. The
	obvious-looking spelling inherited from earlier projects —

	    _Payee(who).emit(value=u256(amount))

	— posts NO MESSAGE AT ALL on this runner. `Proxy.emit()` returns a method
	GETTER, a namespace you are then supposed to call a method on, so an `emit()`
	with nothing after it constructs an object and drops it. Every refund
	appeared to succeed: the transaction settled ACCEPTED, the internal ledger
	zeroed, `claim_refund` returned OK, and not one wei moved. It was caught only
	by comparing the contract's ON-CHAIN BALANCE before and after a claim.

	`emit_transfer` is the spelling that posts a bare value transfer."""
	if int(amount) <= 0:
		return
	gl.contract.get_at(who).emit_transfer(u256(int(amount)))


@gl.storage.allow
@dataclass
class Check:
	"""One scored check. WRITTEN ONCE AND NEVER MUTATED.

	A re-check appends a new record; it does not edit this one. That is why
	`fee_paid_wei` can be trusted as the price of THIS work — nothing in the
	contract can reach back and restate it after the owner changes the fee.

	Every field below is one of exactly three things, and
	`test_EVERY_STORED_FIELD_IS_ON_THE_AXIS` fails if a field is none of them:

	  * ON THE AXIS      — a vector integer or an identity string the validators
	                       compared directly;
	  * DERIVED          — recomputed by `_score()` from the agreed vector;
	  * BOOKKEEPING      — set by the contract, never by the leader.
	"""
	check_id: u32
	seq: u32
	url_key: str
	platform: str
	title: str

	# --- the vector. Compared field by field in `_agrees`.
	reviews_parsed: u32
	avg_rating_x10: u32
	total_ratings: u256
	pct_5: u32
	pct_4: u32
	pct_3: u32
	pct_2: u32
	pct_1: u32
	dated_reviews: u32
	distinct_days: u32
	max_same_day: u32
	span_days: u32
	median_chars: u32
	short_pct: u32
	dup_open_pct: u32
	lexical_pct: u32
	verified_pct: u32
	distinct_names_pct: u32
	weak_handle_pct: u32
	helpful_pct: u32
	helpful_total: u256
	has_photos: bool
	has_response: bool
	page_chars: u32
	reviews_section: bool

	# --- derived from the vector by `_score`, recomputed after consensus.
	d_timing: u32
	d_rating: u32
	d_quality: u32
	d_credibility: u32
	d_engagement: u32
	overall: u32
	trust_level: str
	available_weight: u32
	credibility_basis: str
	content_hash: str
	rubric_version: str

	# --- bookkeeping. The contract's, never the leader's.
	checked_at: u64
	checker: Address
	fee_paid_wei: u256


@gl.storage.allow
@dataclass
class UrlFeed:
	"""Everything tracked for one url_key, plus a bounded ring of its checks.

	A ring rather than an unbounded list because a product checked weekly for a
	year would otherwise make `get_check_by_url` walk 52 records to find the
	newest one, and storage is not free."""
	url_key: str
	platform: str
	title: str
	capacity: u32
	cursor: u32
	check_count: u32
	last_checked: u64
	first_checked: u64
	best_score: u32
	worst_score: u32
	latest_score: u32
	latest_level: str
	latest_id: u32
	history: gl.storage.DynArray[Check]


class ReviewGuard(gl.contract.Contract):
	"""A fake-review detector any contract can read."""

	owner: Address
	paused: bool
	fee_wei: u256
	next_id: u32

	feeds: gl.storage.TreeMap[str, UrlFeed]
	url_keys: gl.storage.DynArray[str]
	url_seen: gl.storage.TreeMap[str, bool]
	by_platform: gl.storage.TreeMap[str, gl.storage.DynArray[str]]
	id_to_url: gl.storage.TreeMap[u32, str]
	recent: gl.storage.DynArray[u32]

	last_request: gl.storage.TreeMap[Address, u64]
	pending: gl.storage.TreeMap[str, u64]

	balance_wei: u256
	refunds_owed: u256
	refunds: gl.storage.TreeMap[Address, u256]

	total_requests: u256
	total_checked: u256
	total_fees_wei: u256
	count_authentic: u32
	count_suspicious: u32
	count_manipulated: u32
	count_inconclusive: u32

	def __init__(self):
		self.owner = gl.message.sender_address
		self.paused = False
		self.fee_wei = u256(DEFAULT_FEE_WEI)
		self.next_id = u32(1)
		self.balance_wei = u256(0)
		self.refunds_owed = u256(0)
		self.total_requests = u256(0)
		self.total_checked = u256(0)
		self.total_fees_wei = u256(0)
		self.count_authentic = u32(0)
		self.count_suspicious = u32(0)
		self.count_manipulated = u32(0)
		self.count_inconclusive = u32(0)

	# ─────────────────────────────────────────────────────────── internals

	def _now(self) -> int:
		"""Block time. From `gl.message.raw`, which is part of the transaction
		and therefore IDENTICAL FOR EVERY VALIDATOR. A wall clock read inside a
		nondet block would differ per node and put the clock on the
		disagreement side of consensus."""
		return _epoch_from_iso(gl.message.raw.get("datetime", ""))

	def _only_owner(self) -> None:
		if gl.message.sender_address != self.owner:
			raise gl.vm.UserError(ERR_EXPECTED + " owner only")

	def _credit(self, who: Address, amount: int) -> None:
		if int(amount) <= 0:
			return
		self.refunds[who] = u256(int(self.refunds.get(who) or 0) + int(amount))
		self.refunds_owed = u256(int(self.refunds_owed) + int(amount))

	def _reject(self, why: str, extra: dict) -> dict:
		"""RULE 2. The only way `check_reviews` refuses.

		A payable method that raises rolls back storage but NOT the incoming
		value, which then sits in the contract with no record saying whose it
		was. So a refusal credits the full deposit to the pull-based ledger and
		RETURNS — the caller can always get their money back, and the reason is
		in the return value rather than in a revert string."""
		value = int(gl.message.value)
		self._credit(gl.message.sender_address, value)
		out = {"status": "REJECTED", "reason": str(why),
			"refunded_wei": str(value)}
		for k in extra:
			out[k] = extra[k]
		return out

	# ───────────────────────────────────────────────────────── the one write

	@gl.public.write.payable
	def check_reviews(self, url: str, platform: str = "") -> typing.Any:
		"""Check one review page. THE ONLY METHOD THAT CREATES A RECORD.

		`platform` is optional: it is DETECTED from the URL, and if the caller
		also names one it must match what the URL actually is. A caller who
		could declare a platform that disagreed with the host would choose which
		parser ran against somebody else's page."""
		value = int(gl.message.value)
		sender = gl.message.sender_address

		# The deposit is booked BEFORE anything can refuse, because a rejection
		# credits a refund out of this same balance and the ledger would
		# otherwise go negative on the very first bad URL.
		self.balance_wei = u256(int(self.balance_wei) + value)

		if self.paused:
			return self._reject("ReviewGuard is paused; no new checks are "
				"being accepted", {})

		raw = _short(str(url or "").strip(), MAX_URL)
		if raw == "":
			return self._reject("no URL given", {})
		detected = _detect_platform(raw)
		if detected == "":
			return self._reject(
				"that host is not one ReviewGuard can read. Supported: "
				+ ", ".join(PLATFORMS)
				+ ". Trustpilot, Yelp and Google Maps were measured and block "
				"validators outright — see the methodology page.",
				{"url": raw})
		declared = str(platform or "").strip().upper()
		if declared != "" and declared != detected:
			return self._reject(
				"that URL is " + detected + ", not " + declared,
				{"url": raw, "detected": detected})

		url_key, fetch_url, why = _canonical(raw, detected)
		if why != "":
			return self._reject(why, {"url": raw, "platform": detected})

		fee = int(self.fee_wei)
		if value < fee:
			return self._reject("fee is " + str(fee) + " wei; " + str(value)
				+ " was sent", {"url_key": url_key})

		now = self._now()
		last = int(self.last_request.get(sender) or 0)
		if last > 0 and now - last < RATE_LIMIT_SECONDS:
			return self._reject("rate limited, retry in "
				+ str(RATE_LIMIT_SECONDS - now + last) + "s",
				{"url_key": url_key})
		if url_key in self.feeds:
			since = now - int(self.feeds[url_key].last_checked)
			if since < URL_COOLDOWN:
				return self._reject(
					"that page was checked " + str(since) + "s ago; retry in "
					+ str(URL_COOLDOWN - since) + "s",
					{"url_key": url_key,
					 "check_id": int(self.feeds[url_key].latest_id)})
		started = int(self.pending.get(url_key) or 0)
		if started > 0 and now - started < PENDING_TTL:
			return self._reject(
				"a check of that page is already in flight; settle_stalled "
				"clears a stuck round after " + str(PENDING_TTL) + "s",
				{"url_key": url_key})
		if url_key not in self.url_seen and len(self.url_keys) >= MAX_URLS:
			return self._reject("URL capacity reached (" + str(MAX_URLS) + ")",
				{"url_key": url_key})

		# RULE 3: nothing above this line has moved a counter, and nothing below
		# it can refuse without going through `_reject`. The in-flight marker
		# and the rate-limit stamp are the first mutations, and both are
		# anti-abuse state rather than statistics — a caller who gets rate
		# limited on their next call did make this call.
		self.pending[url_key] = u64(now)
		self.last_request[sender] = u64(now)
		self.total_requests = u256(int(self.total_requests) + 1)

		now_day = now // 86400

		def leader_fn() -> dict:
			return _collect(url_key, fetch_url, detected, now_day)

		def validator_fn(leaders_res: gl.vm.Result) -> bool:
			if not isinstance(leaders_res, gl.vm.Return):
				# A leader ERROR must be re-run, never voted False on its
				# merits: answering False turns a transient crash into a genuine
				# disagreement and burns a round for nothing.
				return False
			data = leaders_res.calldata
			if not isinstance(data, dict):
				return False
			if not data.get("ok"):
				# The leader says it could not read the page. A validator agrees
				# only if IT cannot read it either — otherwise a leader could
				# suppress any check by claiming a fetch failure.
				try:
					mine = _collect(url_key, fetch_url, detected, now_day)
				except Exception:
					return True
				return not mine.get("ok")
			if not _coherent(data):
				return False
			try:
				mine = _collect(url_key, fetch_url, detected, now_day)
			except Exception:
				return False          # could not do the leader's job — rotate
			if not mine.get("ok"):
				return False
			return _agrees(data, mine)

		out = gl.vm.run_nondet(leader_fn, validator_fn)
		if not isinstance(out, dict):
			self.pending[url_key] = u64(0)
			return self._reject("the validators returned no usable result; "
				"nothing changed", {"url_key": url_key})

		if out.get("retry"):
			# A transient failure is NOT a check. Clearing the marker and
			# refunding is the right direction to fail in: the caller pays
			# nothing, the page keeps whatever score it already had, and the
			# next call can try again immediately.
			self.pending[url_key] = u64(0)
			return self._reject(
				ERR_TRANSIENT + " " + _short(str(out.get("why", "the page did "
				"not answer just now")), 200) + ". Nothing changed; try again "
				"shortly.", {"url_key": url_key, "transient": True})

		if out.get("fail"):
			self.pending[url_key] = u64(0)
			return self._reject(
				ERR_EXTERNAL + " " + _short(str(out.get("why", "unusable")), 200),
				{"url_key": url_key})

		if not _coherent(out):
			# Belt and braces. The validators already applied this gate, so
			# reaching here means the agreed object is not one this rubric can
			# have produced — refuse rather than store something unexplainable.
			self.pending[url_key] = u64(0)
			return self._reject("the agreed result did not match the rubric; "
				"nothing was stored", {"url_key": url_key})

		return self._write(out, url_key, detected, sender, now, fee, value)

	def _write(self, out: dict, url_key: str, platform: str, sender: Address,
			now: int, fee: int, value: int) -> dict:
		"""Post-consensus. THE ONLY PLACE A CHECK IS WRITTEN.

		RULE 1 LIVES HERE. Every field below is read either from
		`out["features"]` — the vector every validator independently reproduced
		— or from `out`'s identity strings, which are on the same compared axis.
		NOTHING is read from a closure variable that only the leader saw.

		RULE 8 lives here too: `_score()` runs AGAIN on the agreed vector rather
		than storing the leader's `scores` dict. `_coherent` has already proved
		the leader's arithmetic matches, so this is belt and braces — but it
		means that even if that gate were weakened, no number the leader chose
		could reach storage."""
		feats = out["features"]
		rescored = _score(feats, platform)

		title = _short(str(out.get("title", "")), MAX_TITLE)
		check_id = int(self.next_id)

		if url_key not in self.url_seen:
			self.url_seen[url_key] = True
			self.url_keys.append(url_key)
			self.by_platform.get_or_insert_default(platform).append(url_key)

		feed = self.feeds.get(url_key)
		if feed is None:
			feed = self.feeds.get_or_insert_default(url_key)
			feed.url_key = url_key
			feed.platform = platform
			feed.capacity = u32(HISTORY_CAP)
			feed.cursor = u32(0)
			feed.check_count = u32(0)
			feed.first_checked = u64(now)
			feed.best_score = u32(0)
			feed.worst_score = u32(100)
		feed.title = title

		if len(feed.history) < HISTORY_CAP:
			rec = feed.history.append_new_get()
		else:
			rec = feed.history[int(feed.cursor) % HISTORY_CAP]
		feed.cursor = u32((int(feed.cursor) + 1) % HISTORY_CAP)

		rec.check_id = u32(check_id)
		rec.seq = u32(int(feed.check_count) + 1)
		rec.url_key = url_key
		rec.platform = platform
		rec.title = title

		rec.reviews_parsed = u32(_as_int(feats["reviews_parsed"], 0))
		rec.avg_rating_x10 = u32(_as_int(feats["avg_rating_x10"], UNAVAIL))
		rec.total_ratings = u256(_as_int(feats["total_ratings"], UNAVAIL))
		rec.pct_5 = u32(_as_int(feats["pct_5"], UNAVAIL))
		rec.pct_4 = u32(_as_int(feats["pct_4"], UNAVAIL))
		rec.pct_3 = u32(_as_int(feats["pct_3"], UNAVAIL))
		rec.pct_2 = u32(_as_int(feats["pct_2"], UNAVAIL))
		rec.pct_1 = u32(_as_int(feats["pct_1"], UNAVAIL))
		rec.dated_reviews = u32(_as_int(feats["dated_reviews"], 0))
		rec.distinct_days = u32(_as_int(feats["distinct_days"], 0))
		rec.max_same_day = u32(_as_int(feats["max_same_day"], 0))
		rec.span_days = u32(_as_int(feats["span_days"], 0))
		rec.median_chars = u32(_as_int(feats["median_chars"], 0))
		rec.short_pct = u32(_as_int(feats["short_pct"], 0))
		rec.dup_open_pct = u32(_as_int(feats["dup_open_pct"], 0))
		rec.lexical_pct = u32(_as_int(feats["lexical_pct"], 0))
		rec.verified_pct = u32(_as_int(feats["verified_pct"], UNAVAIL))
		rec.distinct_names_pct = u32(_as_int(feats["distinct_names_pct"], 0))
		rec.weak_handle_pct = u32(_as_int(feats["weak_handle_pct"], 0))
		rec.helpful_pct = u32(_as_int(feats["helpful_pct"], UNAVAIL))
		rec.helpful_total = u256(_as_int(feats["helpful_total"], UNAVAIL))
		rec.has_photos = bool(_as_int(feats["has_photos"], 0) == 1)
		rec.has_response = bool(_as_int(feats["has_response"], 0) == 1)
		rec.page_chars = u32(_as_int(feats["page_chars"], 0))
		rec.reviews_section = bool(_as_int(feats["reviews_section"], 0) == 1)

		rec.d_timing = u32(_as_int(rescored["scores"]["timing_pattern"], UNAVAIL))
		rec.d_rating = u32(_as_int(rescored["scores"]["rating_distribution"], UNAVAIL))
		rec.d_quality = u32(_as_int(rescored["scores"]["review_quality"], UNAVAIL))
		rec.d_credibility = u32(_as_int(rescored["scores"]["reviewer_credibility"], UNAVAIL))
		rec.d_engagement = u32(_as_int(rescored["scores"]["engagement_signals"], UNAVAIL))
		rec.overall = u32(_as_int(rescored["overall"], 0))
		rec.trust_level = str(rescored["trust_level"])
		rec.available_weight = u32(_as_int(rescored["available_weight"], 0))
		rec.credibility_basis = str(rescored["credibility_basis"])
		rec.content_hash = str(out["content_hash"])
		rec.rubric_version = RUBRIC_VERSION

		# RULE 4: the fee this check actually cost, frozen into the record.
		rec.checked_at = u64(now)
		rec.checker = sender
		rec.fee_paid_wei = u256(fee)

		score = int(rec.overall)
		feed.check_count = u32(int(feed.check_count) + 1)
		feed.last_checked = u64(now)
		feed.latest_score = u32(score)
		feed.latest_level = str(rec.trust_level)
		feed.latest_id = u32(check_id)
		if score > int(feed.best_score):
			feed.best_score = u32(score)
		if score < int(feed.worst_score):
			feed.worst_score = u32(score)

		self.id_to_url[u32(check_id)] = url_key
		self.recent.append(u32(check_id))
		self.next_id = u32(check_id + 1)
		self.total_checked = u256(int(self.total_checked) + 1)
		self.total_fees_wei = u256(int(self.total_fees_wei) + fee)
		level = str(rec.trust_level)
		if level == T_AUTHENTIC:
			self.count_authentic = u32(int(self.count_authentic) + 1)
		elif level == T_SUSPICIOUS:
			self.count_suspicious = u32(int(self.count_suspicious) + 1)
		elif level == T_MANIPULATED:
			self.count_manipulated = u32(int(self.count_manipulated) + 1)
		else:
			self.count_inconclusive = u32(int(self.count_inconclusive) + 1)

		# Overpayment is credited, not kept. The caller asked for one check and
		# sent too much; the excess is theirs.
		if value > fee:
			self._credit(sender, value - fee)

		self.pending[url_key] = u64(0)
		return {"status": "OK", "check_id": check_id, "url_key": url_key,
			"platform": platform, "title": title,
			"overall": score, "trust_level": level,
			"available_weight": int(rec.available_weight),
			"reviews_parsed": int(rec.reviews_parsed),
			"content_hash": str(rec.content_hash),
			"refunded_wei": str(value - fee if value > fee else 0)}

	@gl.public.write
	def settle_stalled(self, url: str) -> typing.Any:
		"""Clear an in-flight marker a failed round left behind.

		PERMISSIONLESS AND WORKS WHILE PAUSED. An owner who could keep a page
		locked by declining to unstick it could censor the oracle, which is the
		same power as forging a verdict by a slower route.

		A round that never settles applies no state, so the usual case needs
		nothing at all. This is for the other case: a round that DID set the
		marker and then failed in a way that left it set."""
		detected = _detect_platform(_short(str(url or "").strip(), MAX_URL))
		if detected == "":
			raise gl.vm.UserError(ERR_EXPECTED + " unsupported platform")
		url_key, _fetch, why = _canonical(_short(str(url).strip(), MAX_URL),
			detected)
		if why != "":
			raise gl.vm.UserError(ERR_EXPECTED + " " + why)
		started = int(self.pending.get(url_key) or 0)
		if started == 0:
			return {"status": "NOOP", "url_key": url_key,
				"reason": "no round is in flight for that page"}
		age = self._now() - started
		if age < PENDING_TTL:
			return {"status": "TOO_EARLY", "url_key": url_key,
				"age_s": age, "retry_in_s": PENDING_TTL - age,
				"reason": "a round may still be settling"}
		self.pending[url_key] = u64(0)
		return {"status": "CLEARED", "url_key": url_key, "age_s": age}

	@gl.public.write
	def claim_refund(self) -> typing.Any:
		"""Pull a credited refund. UNGATED ON `paused` — rule 6. An owner who
		could freeze a refund could hold a user's deposit hostage."""
		who = gl.message.sender_address
		amount = int(self.refunds.get(who) or 0)
		if amount <= 0:
			return {"status": "NOOP", "reason": "nothing owed to you"}
		self.refunds[who] = u256(0)
		self.refunds_owed = u256(int(self.refunds_owed) - amount)
		self.balance_wei = u256(int(self.balance_wei) - amount)
		_pay(who, amount)
		return {"status": "OK", "paid_wei": str(amount)}

	# ───────────────────────────────────────────── owner controls, deliberately few
	#
	# Four, and no more. `TestImmutabilityAfterWrite` enumerates every public
	# write and asserts the only owner-gated ones are these — price, pause,
	# ownership and revenue. Nothing here can reach a score, a record or a
	# user's refund.

	@gl.public.write
	def set_fee(self, new_fee_wei: int) -> typing.Any:
		self._only_owner()
		fee = _as_int(new_fee_wei, -1)
		if fee < 0 or fee > MAX_FEE_WEI:
			raise gl.vm.UserError(ERR_EXPECTED + " fee must be 0.."
				+ str(MAX_FEE_WEI) + " wei")
		old = int(self.fee_wei)
		self.fee_wei = u256(fee)
		# Rule 4 again, from the other side: this changes what the NEXT check
		# costs and nothing about what past checks cost.
		return {"status": "OK", "old_fee_wei": str(old),
			"new_fee_wei": str(fee)}

	@gl.public.write
	def set_paused(self, value: bool) -> typing.Any:
		self._only_owner()
		self.paused = bool(value)
		return {"status": "OK", "paused": bool(self.paused)}

	@gl.public.write
	def transfer_ownership(self, new_owner: Address) -> typing.Any:
		self._only_owner()
		self.owner = new_owner
		return {"status": "OK", "owner": self.owner.as_hex}

	@gl.public.write
	def withdraw_fees(self, amount_wei: int) -> typing.Any:
		"""Revenue only. `refunds_owed` is subtracted BEFORE a balance is
		offered, so credited-but-unclaimed refunds are never withdrawable —
		rule 6. The owner's money is what is left after every user is paid."""
		self._only_owner()
		owed = int(self.refunds_owed)
		free = int(self.balance_wei) - owed
		if free < 0:
			free = 0
		want = _as_int(amount_wei, 0)
		if want <= 0 or want > free:
			want = free
		if want <= 0:
			return {"status": "NOOP", "reason": "no withdrawable balance",
				"reserved_for_refunds_wei": str(owed)}
		self.balance_wei = u256(int(self.balance_wei) - want)
		_pay(self.owner, want)
		return {"status": "OK", "paid_wei": str(want),
			"reserved_for_refunds_wei": str(owed)}

	# ────────────────────────────────────────────────────────────────── reads
	#
	# Every read below is UNGATED ON `paused` — rule 6. Pause stops new risk
	# arriving; it does not take the record away from the people who paid for it.

	def _unavail(self, v: typing.Any) -> typing.Any:
		"""UNAVAIL crosses the API boundary as `None`, not as 255.

		A reader who saw a bare 255 in `pct_5` would have to know this
		contract's sentinel to avoid rendering a product as 255% five-star. One
		place in, one place out."""
		n = _as_int(v, UNAVAIL)
		return None if n == UNAVAIL else n

	def _record(self, rec: Check) -> dict:
		scores = {}
		labels = {}
		pairs = (("timing_pattern", rec.d_timing),
			("rating_distribution", rec.d_rating),
			("review_quality", rec.d_quality),
			("reviewer_credibility", rec.d_credibility),
			("engagement_signals", rec.d_engagement))
		for key, raw in pairs:
			val = _as_int(raw, UNAVAIL)
			if val == UNAVAIL:
				scores[key] = None
				labels[key] = "not published by this platform"
			else:
				scores[key] = val
				labels[key] = BUCKETS[key][_clamp(val, 0, ORDINAL_MAX)]
		return {
			"found": True,
			"check_id": int(rec.check_id),
			"seq": int(rec.seq),
			"url_key": str(rec.url_key),
			"platform": str(rec.platform),
			"title": str(rec.title),
			"source_url": _source_url(str(rec.url_key)),
			"overall": int(rec.overall),
			"trust_level": str(rec.trust_level),
			"available_weight": int(rec.available_weight),
			"credibility_basis": str(rec.credibility_basis),
			"weights": {k: DIM_WEIGHTS[k] for k in DIM_KEYS},
			"scores": scores,
			"labels": labels,
			"evidence": {
				"reviews_parsed": int(rec.reviews_parsed),
				"avg_rating_x10": self._unavail(rec.avg_rating_x10),
				"total_ratings": self._unavail(rec.total_ratings),
				"rating_histogram": {
					"5": self._unavail(rec.pct_5),
					"4": self._unavail(rec.pct_4),
					"3": self._unavail(rec.pct_3),
					"2": self._unavail(rec.pct_2),
					"1": self._unavail(rec.pct_1)},
				"dated_reviews": int(rec.dated_reviews),
				"distinct_days": int(rec.distinct_days),
				"max_same_day": int(rec.max_same_day),
				"span_days": int(rec.span_days),
				"median_chars": int(rec.median_chars),
				"short_pct": int(rec.short_pct),
				"dup_open_pct": int(rec.dup_open_pct),
				"lexical_pct": int(rec.lexical_pct),
				"verified_pct": self._unavail(rec.verified_pct),
				"distinct_names_pct": int(rec.distinct_names_pct),
				"weak_handle_pct": int(rec.weak_handle_pct),
				"helpful_pct": self._unavail(rec.helpful_pct),
				"helpful_total": self._unavail(rec.helpful_total),
				"has_photos": bool(rec.has_photos),
				"has_response": bool(rec.has_response),
				"page_chars": int(rec.page_chars),
				"reviews_section": bool(rec.reviews_section)},
			"content_hash": str(rec.content_hash),
			"rubric_version": str(rec.rubric_version),
			"checked_at": int(rec.checked_at),
			"checker": rec.checker.as_hex,
			"fee_paid_wei": str(rec.fee_paid_wei),
		}

	def _feed_latest(self, url_key: str) -> typing.Any:
		feed = self.feeds.get(url_key)
		if feed is None or int(feed.check_count) == 0:
			return None
		target = int(feed.latest_id)
		for i in range(len(feed.history)):
			if int(feed.history[i].check_id) == target:
				return feed.history[i]
		return None

	@gl.public.view
	def get_check(self, check_id: int) -> typing.Any:
		"""One check, in full. An id whose record has rotated out of the ring
		says SO BY NAME rather than returning whatever now occupies the slot."""
		want = _as_int(check_id, 0)
		url_key = str(self.id_to_url.get(u32(want)) or "")
		if url_key == "":
			return {"found": False, "check_id": want,
				"reason": "no check with that id"}
		feed = self.feeds.get(url_key)
		if feed is not None:
			for i in range(len(feed.history)):
				if int(feed.history[i].check_id) == want:
					return self._record(feed.history[i])
		return {"found": False, "check_id": want, "url_key": url_key,
			"reason": "record rotated out of the " + str(HISTORY_CAP)
				+ "-check history window for " + url_key}

	@gl.public.view
	def get_check_by_url(self, url: str) -> typing.Any:
		"""The latest check for a URL. Takes any URL SHAPE for the page — the
		same canonicalisation the write path uses, so a caller who pastes a long
		Amazon search URL and a caller who pastes `/dp/ASIN` reach one record."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			return {"found": False, "reason": "unsupported platform",
				"supported": list(PLATFORMS)}
		url_key, _fetch, why = _canonical(raw, detected)
		if why != "":
			return {"found": False, "reason": why, "platform": detected}
		rec = self._feed_latest(url_key)
		if rec is None:
			return {"found": False, "url_key": url_key, "platform": detected,
				"reason": "that page has not been checked yet"}
		return self._record(rec)

	@gl.public.view
	def get_checks_by_platform(self, platform: str, count: int = 20) -> typing.Any:
		want = str(platform or "").strip().upper()
		if want not in PLATFORMS:
			return {"platform": want, "count": 0, "items": [],
				"reason": "unsupported platform", "supported": list(PLATFORMS)}
		limit = _clamp(_as_int(count, 20), 1, 100)
		keys = self.by_platform.get(want)
		items = []
		if keys is not None:
			total = len(keys)
			scanned = 0
			i = total - 1
			while i >= 0 and len(items) < limit and scanned < SCAN_CAP:
				scanned += 1
				rec = self._feed_latest(str(keys[i]))
				if rec is not None:
					items.append(self._summary(rec))
				i -= 1
		return {"platform": want, "count": len(items), "items": items}

	def _summary(self, rec: Check) -> dict:
		"""The card view: what a listing needs and nothing more."""
		return {
			"check_id": int(rec.check_id),
			"url_key": str(rec.url_key),
			"platform": str(rec.platform),
			"title": str(rec.title),
			"source_url": _source_url(str(rec.url_key)),
			"overall": int(rec.overall),
			"trust_level": str(rec.trust_level),
			"reviews_parsed": int(rec.reviews_parsed),
			"total_ratings": self._unavail(rec.total_ratings),
			"avg_rating_x10": self._unavail(rec.avg_rating_x10),
			"available_weight": int(rec.available_weight),
			"checked_at": int(rec.checked_at),
		}

	@gl.public.view
	def get_recent_checks(self, count: int = 20) -> typing.Any:
		limit = _clamp(_as_int(count, 20), 1, 100)
		items = []
		i = len(self.recent) - 1
		scanned = 0
		while i >= 0 and len(items) < limit and scanned < SCAN_CAP:
			scanned += 1
			cid = int(self.recent[i])
			url_key = str(self.id_to_url.get(u32(cid)) or "")
			if url_key != "":
				feed = self.feeds.get(url_key)
				if feed is not None:
					for j in range(len(feed.history)):
						if int(feed.history[j].check_id) == cid:
							items.append(self._summary(feed.history[j]))
							break
			i -= 1
		return {"count": len(items), "items": items}

	@gl.public.view
	def is_authentic(self, url: str) -> bool:
		"""FALSE for unchecked, for INCONCLUSIVE, for SUSPICIOUS and for
		MANIPULATED. Only AUTHENTIC is true.

		A contract asking this question is about to list a product, and "we have
		never heard of it" must not read the same as "we checked and the reviews
		are real"."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			return False
		url_key, _fetch, why = _canonical(raw, detected)
		if why != "":
			return False
		rec = self._feed_latest(url_key)
		if rec is None:
			return False
		return str(rec.trust_level) == T_AUTHENTIC

	@gl.public.view
	def require_authentic(self, url: str) -> typing.Any:
		"""Reverts unless the latest check says AUTHENTIC.

		STRICTER THAN "reverts if MANIPULATED", deliberately. The brief asks for
		the weaker guard and `require_not_manipulated` below is exactly that,
		kept for callers who want it. But a method named `require_authentic`
		that waved through SUSPICIOUS, INCONCLUSIVE and never-checked pages
		would be a rubber stamp for precisely the listings nobody has verified —
		which is the opposite of what a marketplace calls it for."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			raise gl.vm.UserError(ERR_EXPECTED + " unsupported platform: "
				+ raw[:80])
		url_key, _fetch, why = _canonical(raw, detected)
		if why != "":
			raise gl.vm.UserError(ERR_EXPECTED + " " + why)
		rec = self._feed_latest(url_key)
		if rec is None:
			raise gl.vm.UserError(ERR_EXPECTED + " " + url_key
				+ " has never been checked")
		level = str(rec.trust_level)
		if level != T_AUTHENTIC:
			raise gl.vm.UserError(ERR_EXPECTED + " " + url_key + " is "
				+ level + " (score " + str(int(rec.overall)) + ")")
		return {"ok": True, "url_key": url_key, "check_id": int(rec.check_id),
			"overall": int(rec.overall), "trust_level": level,
			"content_hash": str(rec.content_hash),
			"checked_at": int(rec.checked_at)}

	@gl.public.view
	def require_not_manipulated(self, url: str) -> typing.Any:
		"""The brief's literal guard: reverts on MANIPULATED, on INCONCLUSIVE
		and on never-checked. INCONCLUSIVE reverts because an unreadable page is
		not evidence of authenticity — rule 7."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			raise gl.vm.UserError(ERR_EXPECTED + " unsupported platform")
		url_key, _fetch, why = _canonical(raw, detected)
		if why != "":
			raise gl.vm.UserError(ERR_EXPECTED + " " + why)
		rec = self._feed_latest(url_key)
		if rec is None:
			raise gl.vm.UserError(ERR_EXPECTED + " " + url_key
				+ " has never been checked")
		level = str(rec.trust_level)
		if level == T_MANIPULATED or level == T_INCONCLUSIVE:
			raise gl.vm.UserError(ERR_EXPECTED + " " + url_key + " is " + level)
		return {"ok": True, "url_key": url_key, "trust_level": level,
			"overall": int(rec.overall), "check_id": int(rec.check_id)}

	@gl.public.view
	def get_trust_summary(self, url: str) -> typing.Any:
		"""NEVER RAISES. The read surface a consumer contract should depend on.

		`require_authentic` would be shorter to call and would make every
		refusal a revert — which on a payable path means keeping the caller's
		deposit. A consumer that wants to refund needs an answer, not an
		exception."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			return {"found": False, "trust_level": T_INCONCLUSIVE,
				"overall": 0, "reason": "unsupported platform",
				"supported": list(PLATFORMS)}
		url_key, _fetch, why = _canonical(raw, detected)
		if why != "":
			return {"found": False, "trust_level": T_INCONCLUSIVE,
				"overall": 0, "reason": why, "platform": detected}
		rec = self._feed_latest(url_key)
		if rec is None:
			return {"found": False, "url_key": url_key, "platform": detected,
				"trust_level": T_INCONCLUSIVE, "overall": 0,
				"reason": "never checked"}
		return {"found": True, "url_key": url_key, "platform": detected,
			"title": str(rec.title), "trust_level": str(rec.trust_level),
			"overall": int(rec.overall), "check_id": int(rec.check_id),
			"reviews_parsed": int(rec.reviews_parsed),
			"available_weight": int(rec.available_weight),
			"content_hash": str(rec.content_hash),
			"checked_at": int(rec.checked_at), "reason": ""}

	@gl.public.view
	def get_stats(self) -> typing.Any:
		total = int(self.total_checked)
		auth = int(self.count_authentic)
		susp = int(self.count_suspicious)
		manip = int(self.count_manipulated)
		inconc = int(self.count_inconclusive)
		per_platform = {}
		for plat in PLATFORMS:
			keys = self.by_platform.get(plat)
			per_platform[plat] = len(keys) if keys is not None else 0
		return {
			"pages_tracked": len(self.url_keys),
			"total_requests": str(self.total_requests),
			"total_checked": total,
			"authentic": auth,
			"suspicious": susp,
			"manipulated": manip,
			"inconclusive": inconc,
			# The share that showed manipulation, out of checks that COULD be
			# called. Inconclusive checks are excluded from the denominator:
			# counting a page nobody could read as "not manipulated" would make
			# the headline number improve every time the oracle failed.
			"manipulation_rate_pct": _pct(manip, auth + susp + manip),
			"conclusive_checks": auth + susp + manip,
			"pages_by_platform": per_platform,
			"total_fees_wei": str(self.total_fees_wei),
			"balance_wei": str(self.balance_wei),
			"refunds_owed_wei": str(self.refunds_owed),
			"paused": bool(self.paused),
		}

	@gl.public.view
	def get_config(self) -> typing.Any:
		platforms = {}
		for plat in PLATFORMS:
			d = PLATFORM_DIMS[plat]
			avail = 0
			dims = {}
			for key in DIM_KEYS:
				flag = bool(d[_dim_flag(key)])
				dims[key] = flag
				if flag:
					avail += DIM_WEIGHTS[key]
			platforms[plat] = {
				"hosts": list(PLATFORM_HOSTS[plat]),
				"dimensions": dims,
				"available_weight": avail,
				"credibility_basis": str(d["credibility_basis"]),
			}
		return {
			"rubric_version": RUBRIC_VERSION,
			"owner": self.owner.as_hex,
			"paused": bool(self.paused),
			"fee_wei": str(self.fee_wei),
			"max_fee_wei": str(MAX_FEE_WEI),
			"rate_limit_seconds": RATE_LIMIT_SECONDS,
			"url_cooldown_seconds": URL_COOLDOWN,
			"pending_ttl_seconds": PENDING_TTL,
			"history_cap": HISTORY_CAP,
			"min_reviews": MIN_REVIEWS,
			"min_available_weight": MIN_AVAILABLE_WEIGHT,
			"quantisation_step": Q_STEP,
			"thresholds": {"authentic_min": AUTHENTIC_MIN,
				"suspicious_min": SUSPICIOUS_MIN},
			"trust_levels": list(TRUST_LEVELS),
			"weights": {k: DIM_WEIGHTS[k] for k in DIM_KEYS},
			"buckets": {k: list(BUCKETS[k]) for k in DIM_KEYS},
			"platforms": platforms,
			"unsupported": {
				"TRUSTPILOT": "403 at the AWS WAF; render() fails outright",
				"YELP": "403 with a captcha challenge",
				"GOOGLE_MAPS": "renders 234 characters of map chrome, no reviews",
				"WALMART": "bot wall", "BEST_BUY": "render fails",
				"TRIPADVISOR": "render fails", "ETSY": "render fails",
				"G2": "render fails", "IMDB": "render fails",
				"NEWEGG": "captcha", "GOODREADS": "403",
				"TARGET": "every product renders as unavailable",
				"STEAM": "aggregate counts only, no review bodies",
			},
		}

	@gl.public.view
	def verify_check(self, check_id: int) -> typing.Any:
		"""Recompute a stored check from its own stored evidence.

		This is what makes the record auditable years later without trusting
		anybody: the vector is read back out of storage, `_score()` and
		`_digest()` are run on it again, and every derived field is compared to
		what was stored. A mismatch means the record was not produced by the
		rubric it claims — and this view says which field disagreed."""
		want = _as_int(check_id, 0)
		url_key = str(self.id_to_url.get(u32(want)) or "")
		if url_key == "":
			return {"verified": False, "check_id": want,
				"reason": "no check with that id"}
		feed = self.feeds.get(url_key)
		rec = None
		if feed is not None:
			for i in range(len(feed.history)):
				if int(feed.history[i].check_id) == want:
					rec = feed.history[i]
		if rec is None:
			return {"verified": False, "check_id": want, "url_key": url_key,
				"reason": "record rotated out of the history window"}

		feats = _stored_vector(rec)
		platform = str(rec.platform)
		if platform not in PLATFORMS:
			return {"verified": False, "check_id": want,
				"reason": "stored platform is not one this rubric knows"}
		again = _score(feats, platform)
		rehash = _digest({"url_key": str(rec.url_key), "platform": platform,
			"title": str(rec.title)}, feats)

		checks = [
			("timing_pattern", _as_int(rec.d_timing, UNAVAIL),
				_as_int(again["scores"]["timing_pattern"], UNAVAIL)),
			("rating_distribution", _as_int(rec.d_rating, UNAVAIL),
				_as_int(again["scores"]["rating_distribution"], UNAVAIL)),
			("review_quality", _as_int(rec.d_quality, UNAVAIL),
				_as_int(again["scores"]["review_quality"], UNAVAIL)),
			("reviewer_credibility", _as_int(rec.d_credibility, UNAVAIL),
				_as_int(again["scores"]["reviewer_credibility"], UNAVAIL)),
			("engagement_signals", _as_int(rec.d_engagement, UNAVAIL),
				_as_int(again["scores"]["engagement_signals"], UNAVAIL)),
			("overall", int(rec.overall), _as_int(again["overall"], -1)),
			("available_weight", int(rec.available_weight),
				_as_int(again["available_weight"], -1)),
		]
		mismatches = []
		for name, stored, fresh in checks:
			if stored != fresh:
				mismatches.append({"field": name, "stored": stored,
					"recomputed": fresh})
		if str(rec.trust_level) != again["trust_level"]:
			mismatches.append({"field": "trust_level",
				"stored": str(rec.trust_level),
				"recomputed": again["trust_level"]})
		if str(rec.credibility_basis) != again["credibility_basis"]:
			mismatches.append({"field": "credibility_basis",
				"stored": str(rec.credibility_basis),
				"recomputed": again["credibility_basis"]})
		if str(rec.content_hash) != rehash:
			mismatches.append({"field": "content_hash",
				"stored": str(rec.content_hash), "recomputed": rehash})

		return {
			"verified": len(mismatches) == 0,
			"check_id": want,
			"url_key": url_key,
			"platform": platform,
			"rubric_version": str(rec.rubric_version),
			"current_rubric_version": RUBRIC_VERSION,
			"recomputed": {
				"scores": {k: (None if _as_int(again["scores"][k], UNAVAIL)
					== UNAVAIL else _as_int(again["scores"][k], 0))
					for k in DIM_KEYS},
				"overall": _as_int(again["overall"], 0),
				"trust_level": again["trust_level"],
				"available_weight": _as_int(again["available_weight"], 0),
				"content_hash": rehash},
			"mismatches": mismatches,
		}

	@gl.public.view
	def get_history(self, url: str, count: int = 6) -> typing.Any:
		"""Every check kept for one page, newest first. The ring holds
		HISTORY_CAP; older ones are gone and this says how many there were."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			return {"found": False, "reason": "unsupported platform"}
		url_key, _fetch, why = _canonical(raw, detected)
		if why != "":
			return {"found": False, "reason": why}
		feed = self.feeds.get(url_key)
		if feed is None or int(feed.check_count) == 0:
			return {"found": False, "url_key": url_key,
				"reason": "that page has not been checked yet"}
		limit = _clamp(_as_int(count, HISTORY_CAP), 1, HISTORY_CAP)
		rows = []
		for i in range(len(feed.history)):
			rows.append(self._summary(feed.history[i]))
		rows.sort(key=lambda r: -int(r["check_id"]))
		return {"found": True, "url_key": url_key, "platform": detected,
			"title": str(feed.title),
			"total_checks": int(feed.check_count),
			"kept": len(rows), "history_cap": HISTORY_CAP,
			"best_score": int(feed.best_score),
			"worst_score": int(feed.worst_score),
			"first_checked": int(feed.first_checked),
			"last_checked": int(feed.last_checked),
			"items": rows[:limit]}

	@gl.public.view
	def get_refund_owed(self, who: Address) -> typing.Any:
		return {"address": who.as_hex, "owed_wei": str(self.refunds.get(who) or 0)}

	@gl.public.view
	def detect_platform(self, url: str) -> typing.Any:
		"""What the front end calls as you type. Pure, free, and the SAME
		function the write path uses — a preview that disagreed with the
		submission would be worse than no preview."""
		raw = _short(str(url or "").strip(), MAX_URL)
		detected = _detect_platform(raw)
		if detected == "":
			return {"supported": False, "platform": "", "url_key": "",
				"reason": "that host is not one ReviewGuard can read",
				"platforms": list(PLATFORMS)}
		url_key, fetch_url, why = _canonical(raw, detected)
		if why != "":
			return {"supported": False, "platform": detected, "url_key": "",
				"reason": why}
		d = PLATFORM_DIMS[detected]
		avail = 0
		for key in DIM_KEYS:
			if d[_dim_flag(key)]:
				avail += DIM_WEIGHTS[key]
		return {"supported": True, "platform": detected, "url_key": url_key,
			"canonical_url": fetch_url, "available_weight": avail,
			"credibility_basis": str(d["credibility_basis"]),
			"already_checked": url_key in self.feeds, "reason": ""}
