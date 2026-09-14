# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
from dataclasses import dataclass
import typing

# MarketplaceConsumer — a worked example of reading ReviewGuard from another
# contract.
#
# It models a curated marketplace with ONE rule: a product may only be listed if
# ReviewGuard says its reviews are AUTHENTIC. That is the whole product.
# Everything else here exists to make the refusal observable — a listing book, a
# seller ledger, and a log of what was turned away and why.
#
# Why this contract is worth reading:
#
#   1. IT TREATS THE ORACLE AS UNTRUSTED-BY-DEFAULT. `get_trust_summary` never
#      raises, so the happy path never depends on catching an exception, and
#      every field it returns is checked here before it is used. A consumer that
#      assumed `found` was true would treat "never checked" as a score of zero —
#      or worse, as a pass.
#
#   2. IT PINS THE CHECK IT ACTED ON. Every accepted listing records the check
#      id, the content hash and the trust level that admitted it. A product
#      whose reviews are later gamed does not rewrite history, and an auditor
#      can ask "what did you know when you listed this" and get an answer.
#
#   3. IT HAS A STALENESS RULE, AND IT IS THE CONSUMER'S, NOT THE ORACLE'S. An
#      AUTHENTIC verdict from a year ago is not evidence about today.
#      `max_check_age_s` is a constructor argument, because the oracle's job is
#      to report what it measured and when, and each integrator decides how old
#      is too old.
#
#   4. ITS REFUSALS REFUND. Same rule as ReviewGuard itself: a payable method
#      that raises keeps the deposit with no record to refund it from.
#
#   5. IT REFUSES INCONCLUSIVE. A page ReviewGuard could not read is not a page
#      that passed. Treating "we could not tell" as "fine" would make the whole
#      guard decorative for exactly the listings that most need checking.

ERR_EXPECTED = "[EXPECTED]"

T_AUTHENTIC = "AUTHENTIC"
T_SUSPICIOUS = "SUSPICIOUS"
T_MANIPULATED = "MANIPULATED"
T_INCONCLUSIVE = "INCONCLUSIVE"

# Defaults. Both are constructor arguments so a deployer states their own
# appetite rather than inheriting one.
DEFAULT_MIN_SCORE = 70             # matches ReviewGuard's AUTHENTIC threshold
DEFAULT_MAX_AGE_S = 30 * 24 * 3600
MAX_LISTINGS = 200
MAX_LOG = 50
MAX_URL = 300
MAX_TEXT = 120


def _as_int(v: typing.Any, default: int = 0) -> int:
	"""bool is EXCLUDED explicitly: `bool` is an `int` in Python, and a `True`
	arriving where a score belongs would silently read as 1."""
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


def _short(s: typing.Any, n: int) -> str:
	t = str(s)
	return t if len(t) <= n else t[:n]


def _days_from_civil(y: int, m: int, d: int) -> int:
	y -= 1 if m <= 2 else 0
	era = (y if y >= 0 else y - 399) // 400
	yoe = y - era * 400
	doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
	doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
	return era * 146097 + doe - 719468


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


def _pay(who: Address, amount: int) -> None:
	"""THE ONLY WAY MONEY LEAVES THIS CONTRACT. `emit_transfer`, never a bare
	`emit()` — see the note on the same helper in ReviewGuard.py, which cost a
	round of silent no-op refunds to find."""
	if int(amount) <= 0:
		return
	gl.contract.get_at(who).emit_transfer(u256(int(amount)))


@gl.contract.interface
class IReviewGuard:
	"""The read surface MarketplaceConsumer depends on.

	DELIBERATELY NARROW: `get_trust_summary` is the only method that matters
	here, because it is the only one that never raises. `require_authentic`
	would be shorter to call and would make every refusal a revert — which on a
	payable path means keeping the caller's deposit."""

	class View:
		def get_trust_summary(self, url: str) -> typing.Any:
			pass

		def get_config(self) -> typing.Any:
			pass

	class Write:
		"""No write methods. A consumer that could make the oracle write would
		be a consumer that could spend somebody else's rate limit."""
		pass


@gl.storage.allow
@dataclass
class Listing:
	url_key: str
	title: str
	platform: str
	seller: Address
	price_wei: u256
	listed_at: u64
	active: bool
	# --- what was known at listing time. Never updated: that is the point.
	check_id: u32
	trust_level: str
	overall: u32
	content_hash: str
	checked_at: u64


@gl.storage.allow
@dataclass
class Refusal:
	url: str
	who: Address
	at: u64
	trust_level: str
	overall: u32
	reason: str
	refunded_wei: u256


class MarketplaceConsumer(gl.contract.Contract):
	owner: Address
	oracle: Address
	min_score: u32
	max_check_age_s: u64

	listings: gl.storage.TreeMap[str, Listing]
	listing_keys: gl.storage.DynArray[str]
	refusals: gl.storage.DynArray[Refusal]

	balance_wei: u256
	refunds_owed: u256
	refunds: gl.storage.TreeMap[Address, u256]

	total_attempts: u256
	total_listed: u256
	total_refused: u256

	def __init__(self, oracle: Address, min_score: int = DEFAULT_MIN_SCORE,
			max_check_age_s: int = DEFAULT_MAX_AGE_S):
		self.owner = gl.message.sender_address
		self.oracle = oracle
		score = _as_int(min_score, DEFAULT_MIN_SCORE)
		self.min_score = u32(score if 0 <= score <= 100 else DEFAULT_MIN_SCORE)
		age = _as_int(max_check_age_s, DEFAULT_MAX_AGE_S)
		self.max_check_age_s = u64(age if age > 0 else DEFAULT_MAX_AGE_S)
		self.balance_wei = u256(0)
		self.refunds_owed = u256(0)
		self.total_attempts = u256(0)
		self.total_listed = u256(0)
		self.total_refused = u256(0)

	def _now(self) -> int:
		return _epoch_from_iso(gl.message.raw.get("datetime", ""))

	def _credit(self, who: Address, amount: int) -> None:
		if int(amount) <= 0:
			return
		self.refunds[who] = u256(int(self.refunds.get(who) or 0) + int(amount))
		self.refunds_owed = u256(int(self.refunds_owed) + int(amount))

	def _log_refusal(self, url: str, level: str, overall: int, why: str,
			refunded: int) -> None:
		if len(self.refusals) >= MAX_LOG:
			# A ring, so a long-running marketplace does not grow storage
			# without bound — and the NEWEST refusals are the ones kept, which
			# is the opposite of what an append-and-truncate would do.
			rec = self.refusals[int(self.total_refused) % MAX_LOG]
		else:
			rec = self.refusals.append_new_get()
		rec.url = _short(url, MAX_URL)
		rec.who = gl.message.sender_address
		rec.at = u64(self._now())
		rec.trust_level = _short(level, 24)
		rec.overall = u32(_as_int(overall, 0))
		rec.reason = _short(why, 200)
		rec.refunded_wei = u256(int(refunded))

	def _refuse(self, url: str, level: str, overall: int, why: str) -> dict:
		"""RULE 4. Every refusal on the payable path comes through here."""
		value = int(gl.message.value)
		self._credit(gl.message.sender_address, value)
		self.total_refused = u256(int(self.total_refused) + 1)
		self._log_refusal(url, level, overall, why, value)
		return {"status": "REJECTED", "reason": str(why),
			"trust_level": str(level), "overall": _as_int(overall, 0),
			"refunded_wei": str(value)}

	@gl.public.write.payable
	def list_product(self, url: str, price_wei: int) -> typing.Any:
		"""List a product, IF ReviewGuard says its reviews are authentic.

		The whole composability story is the twenty lines after the oracle call:
		every field that comes back is checked before it is used, because a
		summary from a contract this one does not control is INPUT, not truth."""
		value = int(gl.message.value)
		seller = gl.message.sender_address
		# Booked before anything can refuse: a refusal credits out of this same
		# balance, and the ledger would otherwise go negative on the first bad
		# URL.
		self.balance_wei = u256(int(self.balance_wei) + value)

		raw = _short(str(url or "").strip(), MAX_URL)
		if raw == "":
			return self._refuse(raw, T_INCONCLUSIVE, 0, "no URL given")
		price = _as_int(price_wei, -1)
		if price < 0:
			return self._refuse(raw, T_INCONCLUSIVE, 0, "price must be >= 0")

		self.total_attempts = u256(int(self.total_attempts) + 1)

		summary = IReviewGuard(self.oracle).view().get_trust_summary(raw)
		if not isinstance(summary, dict):
			return self._refuse(raw, T_INCONCLUSIVE, 0,
				"the oracle returned something unreadable")
		if not summary.get("found"):
			return self._refuse(raw, T_INCONCLUSIVE, 0,
				"ReviewGuard has never checked that page: "
				+ _short(summary.get("reason", ""), 120))

		level = _short(summary.get("trust_level", ""), 24)
		overall = _as_int(summary.get("overall"), 0)
		checked_at = _as_int(summary.get("checked_at"), 0)
		url_key = _short(summary.get("url_key", ""), MAX_URL)
		if url_key == "":
			return self._refuse(raw, level, overall,
				"the oracle returned no url_key")

		# INCONCLUSIVE is refused explicitly rather than falling through the
		# score test. Its overall is 0, so the score test WOULD catch it — but
		# only by accident, and a future rubric that reported a nonzero score
		# alongside INCONCLUSIVE would silently start admitting them.
		if level == T_INCONCLUSIVE:
			return self._refuse(raw, level, overall,
				"ReviewGuard could not read enough of that page to judge it")
		if level != T_AUTHENTIC:
			return self._refuse(raw, level, overall,
				"reviews are " + level + " (score " + str(overall) + ")")
		if overall < int(self.min_score):
			return self._refuse(raw, level, overall,
				"score " + str(overall) + " is below this marketplace's "
				"minimum of " + str(int(self.min_score)))

		now = self._now()
		age = now - checked_at
		if checked_at <= 0:
			return self._refuse(raw, level, overall,
				"the oracle reported no check time")
		if age > int(self.max_check_age_s):
			return self._refuse(raw, level, overall,
				"that check is " + str(age // 86400) + " days old; this "
				"marketplace requires one within "
				+ str(int(self.max_check_age_s) // 86400) + " days")

		if url_key not in self.listings and len(self.listing_keys) >= MAX_LISTINGS:
			return self._refuse(raw, level, overall, "listing capacity reached")

		existing = self.listings.get(url_key)
		if existing is not None and bool(existing.active):
			return self._refuse(raw, level, overall,
				"that product is already listed")

		if url_key not in self.listings:
			self.listing_keys.append(url_key)
		rec = self.listings.get_or_insert_default(url_key)
		rec.url_key = url_key
		rec.title = _short(summary.get("title", ""), MAX_TEXT)
		rec.platform = _short(summary.get("platform", ""), 24)
		rec.seller = seller
		rec.price_wei = u256(price)
		rec.listed_at = u64(now)
		rec.active = True
		# RULE 2: what was known at listing time, pinned.
		rec.check_id = u32(_as_int(summary.get("check_id"), 0))
		rec.trust_level = level
		rec.overall = u32(overall)
		rec.content_hash = _short(summary.get("content_hash", ""), 64)
		rec.checked_at = u64(checked_at)

		self.total_listed = u256(int(self.total_listed) + 1)
		if value > 0:
			# This marketplace charges nothing to list. The deposit is the
			# seller's and goes straight back to their refund balance.
			self._credit(seller, value)
		return {"status": "OK", "url_key": url_key, "title": str(rec.title),
			"platform": str(rec.platform), "price_wei": str(price),
			"admitted_on": {"check_id": int(rec.check_id),
				"trust_level": level, "overall": overall,
				"content_hash": str(rec.content_hash),
				"checked_at": checked_at},
			"refunded_wei": str(value)}

	@gl.public.write
	def delist(self, url_key: str) -> typing.Any:
		"""A seller may withdraw their own listing; the owner may withdraw any.
		Neither can EDIT one — the admitted-on record is immutable."""
		key = _short(str(url_key or "").strip(), MAX_URL)
		rec = self.listings.get(key)
		if rec is None or not bool(rec.active):
			return {"status": "NOOP", "reason": "not an active listing"}
		who = gl.message.sender_address
		if who != rec.seller and who != self.owner:
			raise gl.vm.UserError(ERR_EXPECTED
				+ " only the seller or the owner can delist")
		rec.active = False
		return {"status": "OK", "url_key": key}

	@gl.public.write
	def claim_refund(self) -> typing.Any:
		who = gl.message.sender_address
		amount = int(self.refunds.get(who) or 0)
		if amount <= 0:
			return {"status": "NOOP", "reason": "nothing owed to you"}
		self.refunds[who] = u256(0)
		self.refunds_owed = u256(int(self.refunds_owed) - amount)
		self.balance_wei = u256(int(self.balance_wei) - amount)
		_pay(who, amount)
		return {"status": "OK", "paid_wei": str(amount)}

	@gl.public.write
	def set_policy(self, min_score: int, max_check_age_s: int) -> typing.Any:
		"""The marketplace's own risk appetite. Changing it does NOT re-judge
		listings already accepted — they carry the verdict that admitted them,
		and rewriting that would be rewriting history."""
		if gl.message.sender_address != self.owner:
			raise gl.vm.UserError(ERR_EXPECTED + " owner only")
		score = _as_int(min_score, -1)
		if score < 0 or score > 100:
			raise gl.vm.UserError(ERR_EXPECTED + " min_score must be 0..100")
		age = _as_int(max_check_age_s, 0)
		if age <= 0:
			raise gl.vm.UserError(ERR_EXPECTED + " max age must be > 0")
		self.min_score = u32(score)
		self.max_check_age_s = u64(age)
		return {"status": "OK", "min_score": score, "max_check_age_s": age}

	@gl.public.view
	def get_listing(self, url_key: str) -> typing.Any:
		key = _short(str(url_key or "").strip(), MAX_URL)
		rec = self.listings.get(key)
		if rec is None:
			return {"found": False, "url_key": key}
		return {"found": True, "url_key": str(rec.url_key),
			"title": str(rec.title), "platform": str(rec.platform),
			"seller": rec.seller.as_hex, "price_wei": str(rec.price_wei),
			"listed_at": int(rec.listed_at), "active": bool(rec.active),
			"admitted_on": {"check_id": int(rec.check_id),
				"trust_level": str(rec.trust_level),
				"overall": int(rec.overall),
				"content_hash": str(rec.content_hash),
				"checked_at": int(rec.checked_at)}}

	@gl.public.view
	def get_listings(self, count: int = 50) -> typing.Any:
		limit = int(count) if 0 < int(count) <= MAX_LISTINGS else 50
		items = []
		i = len(self.listing_keys) - 1
		while i >= 0 and len(items) < limit:
			rec = self.listings.get(str(self.listing_keys[i]))
			if rec is not None and bool(rec.active):
				items.append({"url_key": str(rec.url_key),
					"title": str(rec.title), "platform": str(rec.platform),
					"price_wei": str(rec.price_wei),
					"overall": int(rec.overall),
					"trust_level": str(rec.trust_level),
					"check_id": int(rec.check_id),
					"listed_at": int(rec.listed_at)})
			i -= 1
		return {"count": len(items), "items": items}

	@gl.public.view
	def get_refusals(self, count: int = 20) -> typing.Any:
		"""The refusal log. THE POINT OF THIS CONTRACT: a guard whose refusals
		are invisible is a guard nobody can audit."""
		limit = int(count) if 0 < int(count) <= MAX_LOG else 20
		items = []
		for i in range(len(self.refusals)):
			rec = self.refusals[i]
			if str(rec.url) == "":
				continue
			items.append({"url": str(rec.url), "who": rec.who.as_hex,
				"at": int(rec.at), "trust_level": str(rec.trust_level),
				"overall": int(rec.overall), "reason": str(rec.reason),
				"refunded_wei": str(rec.refunded_wei)})
		items.sort(key=lambda r: -int(r["at"]))
		return {"count": len(items[:limit]), "items": items[:limit]}

	@gl.public.view
	def get_policy(self) -> typing.Any:
		return {"owner": self.owner.as_hex, "oracle": self.oracle.as_hex,
			"min_score": int(self.min_score),
			"max_check_age_s": int(self.max_check_age_s),
			"max_listings": MAX_LISTINGS,
			"active_listings": len(self.listing_keys),
			"total_attempts": str(self.total_attempts),
			"total_listed": str(self.total_listed),
			"total_refused": str(self.total_refused),
			"balance_wei": str(self.balance_wei),
			"refunds_owed_wei": str(self.refunds_owed),
			"policy_note": "AUTHENTIC only. SUSPICIOUS, MANIPULATED, "
				"INCONCLUSIVE and never-checked are all refused, and the "
				"deposit is refunded in every case."}

	@gl.public.view
	def get_refund_owed(self, who: Address) -> typing.Any:
		return {"address": who.as_hex,
			"owed_wei": str(self.refunds.get(who) or 0)}
