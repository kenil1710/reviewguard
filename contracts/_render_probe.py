# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *

import json

# Throwaway diagnostic, NOT part of ReviewGuard. It answers the one question
# that decides whether this project is buildable at all, and which platforms it
# can honestly claim to support:
#
#   For each candidate review platform — does a GenLayer validator actually SEE
#   the reviews?
#
# Four distinct failure modes hide behind a single "it didn't work", and they
# call for opposite responses:
#
#   * egress blocked      — 403/451 at the edge. Platform is impossible.
#   * bot wall / captcha  — 200 with a challenge page. Platform is impossible.
#   * JS-only shell       — 200, real HTML, zero review text. render() may fix
#                           it; a plain GET never will.
#   * works               — review text present and countable.
#
# So every URL is measured THREE ways: a plain GET, a render(mode="text"), and a
# keyword census over whatever came back. A platform ships only if the census
# finds real review data.
#
# The two header lines above are the whole of what GenVM reads before the code:
# the version line and the runner pin, in that order. Nothing else may sit
# between line 1 and the imports — GenVM parses the contiguous leading `#` block
# as the runner header, and a stray comment there makes the contract
# undeployable with no error reported but `invalid_contract`.


def _status(res) -> int:
	s = getattr(res, "status_code", None)
	if s is None:
		s = getattr(res, "status", None)
	if s is None:
		return 0
	return int(s)


def _body(res) -> str:
	b = getattr(res, "body", None)
	if b is None:
		b = getattr(res, "text", None)
	if b is None:
		return ""
	if isinstance(b, bytes):
		return b.decode("utf-8", errors="ignore")
	return str(b)


def _get(url: str) -> tuple:
	"""(status, body, err). Never raises. Both spellings of the web API are
	tried because prior projects split between them and a probe must not die on
	which one this runner build happens to expose."""
	try:
		try:
			res = gl.nondet.web.request(url, method="GET")
		except AttributeError:
			res = gl.nondet.web.get(url)
	except Exception as e:
		return (0, "", str(e)[:400])
	return (_status(res), _body(res), "")


def _render(url: str, mode: str, wait: str) -> tuple:
	"""(ok, text, err). render() has NO status code: it returns the body on
	success and RAISES on every non-2xx, carrying the status in the exception
	text. The exception string is kept verbatim — on a blocked platform it IS
	the finding."""
	try:
		out = gl.nondet.web.render(url, mode=mode, wait_after_loaded=wait)
		if not isinstance(out, str):
			out = str(out)
		return (True, out, "")
	except Exception as e:
		return (False, "", str(e)[:500])


# Keyword census. Three families, because they answer three different questions
# and a single "does it contain 'review'" would call a captcha page a success.
_BLOCK_WORDS = (
	"captcha", "are you a robot", "robot check", "access denied",
	"unusual traffic", "verify you are human", "cf-browser-verification",
	"just a moment", "enable javascript", "request blocked",
	"pardon our interruption", "px-captcha", "perimeterx", "datadome",
	"cloudflare", "bot detection", "security check",
)
_REVIEW_WORDS = (
	"review", "reviews", "rating", "ratings", "star", "stars", "trustscore",
	"verified", "helpful", "out of 5", "written by", "recommend",
)
_STRUCT_WORDS = (
	"aggregaterating", "reviewbody", "ratingvalue", "reviewcount",
	"datepublished", "\"author\"", "schema.org/review", "itemreviewed",
)


def _slug(text: str) -> str:
	"""Spaces to underscores WITHOUT str.replace() — the runner rejects that
	method outright, and a probe that cannot deploy measures nothing."""
	out = ""
	for ch in text:
		if ch == " ":
			out += "_"
		else:
			out += ch
	return out


def _census(text: str) -> dict:
	"""What is actually IN the bytes, counted rather than eyeballed.

	A length alone lies in both directions: a 900 KB captcha page looks like
	success and a 12 KB review list looks like failure. The counts are what the
	go/no-go decision is made on."""
	low = text.lower()
	out = {"len": len(text)}

	blocked = {}
	for w in _BLOCK_WORDS:
		n = low.count(w)
		if n > 0:
			blocked[w] = n
	out["block_hits"] = blocked

	rev = {}
	for w in _REVIEW_WORDS:
		n = low.count(w)
		if n > 0:
			rev[w] = n
	out["review_hits"] = rev

	st = {}
	for w in _STRUCT_WORDS:
		n = low.count(w)
		if n > 0:
			st[w] = n
	out["struct_hits"] = st

	# Crude shape signals that survive any markup style.
	out["digits"] = sum(1 for c in text if c.isdigit())
	out["lines"] = len(text.split("\n"))
	out["has_html_tag"] = ("<html" in low) or ("<!doctype" in low)
	out["has_json_ld"] = "application/ld+json" in low
	return out


class RenderProbe(gl.contract.Contract):
	out: str
	window: str
	window_len: u32

	def __init__(self):
		self.out = ""
		self.window = ""
		self.window_len = u32(0)

	@gl.public.write
	def probe_get_batch(self, urls: list) -> None:
		"""Plain GET status + length + head for each URL, one transaction.

		Distinguishes 'blocked at the edge' from 'served but empty': a 403 is a
		wall, a 200 with an 800-byte body is a JS shell, and the two call for
		opposite pivots."""
		targets = [str(u) for u in urls][:8]

		def leader_fn() -> dict:
			found = {}
			for u in targets:
				st, body, err = _get(u)
				row = {"status": st, "len": len(body)}
				if err:
					row["err"] = err
				if body:
					row["head"] = body[:300]
					row["census"] = _census(body)
				found[u] = row
			return found

		def validator_fn(leader_result) -> bool:
			# Shape only. A validator that re-fetched a live review page would
			# disagree on every byte and the probe would never commit — which is
			# exactly why ReviewGuard itself agrees on BUCKETS, not on bytes.
			return isinstance(leader_result, gl.vm.Return)

		self.out = json.dumps(gl.vm.run_nondet(leader_fn, validator_fn))

	@gl.public.write
	def probe_render_batch(self, urls: list, wait: str) -> None:
		"""render(mode="text") for each URL: does a real browser get through?

		This is the load-bearing call. A platform that answers here with review
		text is buildable; one that answers with a captcha is not, and no amount
		of scoring cleverness changes that."""
		targets = [str(u) for u in urls][:6]
		hold = str(wait) if wait else "3s"

		def leader_fn() -> dict:
			found = {}
			for u in targets:
				ok, text, err = _render(u, "text", hold)
				row = {"rendered": ok}
				if err:
					row["err"] = err
				if text:
					row["census"] = _census(text)
					row["head"] = text[:600]
					row["tail"] = text[-300:]
				found[u] = row
			return found

		def validator_fn(leader_result) -> bool:
			return isinstance(leader_result, gl.vm.Return)

		self.out = json.dumps(gl.vm.run_nondet(leader_fn, validator_fn))

	@gl.public.write
	def probe_window(self, url: str, start: int, count: int, wait: str,
			use_render: bool) -> None:
		"""A WINDOW of one page's text, walked forward across calls.

		Windowed rather than whole: a rendered review page is hundreds of
		kilobytes and the interesting part is found by moving the window, not by
		pushing the page through consensus."""
		begin = int(start)
		span = int(count)
		if span <= 0 or span > 10000:
			span = 10000
		hold = str(wait) if wait else "3s"
		render_it = bool(use_render)
		target = str(url)

		def leader_fn() -> dict:
			if render_it:
				ok, text, err = _render(target, "text", hold)
				if not ok:
					return {"len": 0, "window": "", "err": err, "mode": "render"}
				return {"len": len(text), "window": text[begin:begin + span],
					"mode": "render"}
			st, body, err = _get(target)
			return {"len": len(body), "window": body[begin:begin + span],
				"status": st, "err": err, "mode": "get"}

		def validator_fn(leader_result) -> bool:
			return isinstance(leader_result, gl.vm.Return)

		res = gl.vm.run_nondet(leader_fn, validator_fn)
		self.window_len = u32(int(res.get("len", 0)))
		self.window = str(res.get("window", "")) + " || " + json.dumps(
			{"mode": res.get("mode"), "err": res.get("err", ""),
			 "status": res.get("status", "")})

	@gl.public.write
	def probe_review_shape(self, url: str, wait: str) -> None:
		"""The exact numbers ReviewGuard's five dimensions would need, pulled
		from a live review page.

		probe_render_batch says the page is REACHABLE; this says it is USABLE —
		that dates, star ratings, review bodies and reviewer names can all be
		located in one render, deterministically, by pure Python. If this comes
		back empty the platform is dropped even though it fetched fine."""
		target = str(url)
		hold = str(wait) if wait else "5s"

		def leader_fn() -> dict:
			ok, text, err = _render(target, "text", hold)
			if not ok:
				return {"rendered": False, "err": err}
			low = text.lower()
			out = {"rendered": True, "census": _census(text)}

			# Star / rating mentions, by the spellings each platform uses.
			for pat in ("rated 5 out of 5", "rated 4 out of 5",
					"rated 3 out of 5", "rated 2 out of 5",
					"rated 1 out of 5", "out of 5 stars", "star rating",
					"5 star", "4 star", "3 star", "2 star", "1 star"):
				n = low.count(pat)
				if n > 0:
					out["rate_" + _slug(pat)] = n

			# Date-ish tokens: the timing dimension lives or dies on these.
			months = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
				"sep", "oct", "nov", "dec")
			mc = 0
			for m in months:
				mc += low.count(m + " ")
			out["month_tokens"] = mc
			for pat in ("days ago", "hours ago", "weeks ago", "months ago",
					"years ago", "updated", "date of experience"):
				n = low.count(pat)
				if n > 0:
					out["when_" + _slug(pat)] = n

			# Reviewer credibility markers.
			for pat in ("review", "reviews", "verified", "helpful",
					"useful", "funny", "cool", "photos", "elite",
					"replied", "reply from", "response from"):
				n = low.count(pat)
				if n > 0:
					out["sig_" + _slug(pat)] = n

			# Where in the text do the reviews start? Tells us how much of the
			# page is chrome before anything worth reading.
			for anchor in ("most relevant", "recent reviews", "reviews",
					"customer reviews", "top reviews"):
				i = low.find(anchor)
				if i >= 0:
					out["anchor_" + _slug(anchor)] = i
			out["sample_mid"] = text[len(text) // 3: len(text) // 3 + 700]
			return out

		def validator_fn(leader_result) -> bool:
			return isinstance(leader_result, gl.vm.Return)

		self.out = json.dumps(gl.vm.run_nondet(leader_fn, validator_fn))

	@gl.public.view
	def read(self) -> str:
		return self.out

	@gl.public.view
	def read_window(self) -> str:
		return json.dumps({"len": int(self.window_len), "window": self.window})
