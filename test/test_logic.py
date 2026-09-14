#!/usr/bin/env python3
"""Offline tests for ReviewGuard. No chain, no network, no model, no genlayer
install — stdlib only:

    python3 test/test_logic.py

Nine things are under test, not one.

1.  **URL handling**, which is both the first line of the design and the first
    line of the attack surface. The submitted URL decides which page five
    validators fetch, so a canonicaliser that lets a host through is a
    canonicaliser that lets a submitter manufacture any verdict they like.

2.  **The pure rubric**: five ladders, the quantisers, the three-significant-
    figure rounding that makes a live review count agreeable, the weighted
    overall, the trust bands and the content hash. This is the half every
    validator computes after the bytes come back. If two validators disagree
    here, no check ever settles.

3.  **Extraction against REAL RENDERED PAGES.** `test/fixtures/*.txt` are the
    verbatim outputs of `gl.nondet.web.render` captured off studio-dev by the
    render probe on 2026-09-14 — an Amazon product page, a Google Play listing
    and an App Store listing. An extraction test written against invented text
    proves nothing about on-chain behaviour.

4.  **That the rubric DISCRIMINATES.** A detector that calls everything
    authentic is not a detector. Synthetic pages built to each shape — a
    bought-review batch, an organic page, and the middle ground — must land in
    the band they belong in, and every band must be reachable.

5.  **Rule 7, conservatism.** Evidence that is absent is UNAVAILABLE and carries
    no weight. Tests pin that it is never scored as zero, that it never earns
    points either, and that too little evidence produces INCONCLUSIVE rather
    than a guess.

6.  **The consensus gates.** `_coherent` and `_agrees` are what stop a leader
    forging a stored value, so they are tested by BUILDING FORGERIES and
    checking each one is refused.

7.  **A static undefined-name check** over the WHOLE file, class bodies
    included. The pure region can be exec'd and exercised, but a name error
    inside a `@gl.public.view` only fires when that view is called on chain. A
    parser catches it in a millisecond; a deploy catches it in ten minutes.

8.  **The stateful contract**, driven through a storage stub rich enough to run
    check -> read -> verify end to end with consensus wired up. This is where
    the money invariants are proved: that a rejected payable call REFUNDS rather
    than confiscating, that no counter moves before a refusal, and that the
    owner can never reach a score or a refund.

9.  **MarketplaceConsumer**, the composability story, driven across a real
    cross-contract call boundary against the real ReviewGuard instance.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H
from harness import (ROOT, SOURCE, CONSUMER, GEN, DAY, HOUR, MINUTE,
                     undefined_names, fixture)

H._install_stub()
MOD = H.load_pure(SOURCE, "reviewguard_pure")
FULL = H.load_full(SOURCE, "reviewguard_full")
CONS = H.load_full(CONSUMER, "marketplace_full")

H._STRUCT_HINTS[("ReviewGuard", "feeds")] = FULL.UrlFeed
H._STRUCT_HINTS[("UrlFeed", "history")] = FULL.Check
H._STRUCT_HINTS[("MarketplaceConsumer", "listings")] = CONS.Listing
H._STRUCT_HINTS[("MarketplaceConsumer", "refusals")] = CONS.Refusal

UNAVAIL = MOD.UNAVAIL
P_AMAZON = MOD.P_AMAZON
P_GPLAY = MOD.P_GPLAY
P_APPSTORE = MOD.P_APPSTORE

AMAZON_URL = "https://www.amazon.com/dp/B07FZ8S74R"
AMAZON_KEY = "AMAZON:amazon.com:B07FZ8S74R"
GPLAY_URL = "https://play.google.com/store/apps/details?id=com.whatsapp"
GPLAY_FETCH = ("https://play.google.com/store/apps/details?id=com.whatsapp"
               "&hl=en&gl=US")
GPLAY_KEY = "GOOGLE_PLAY:com.whatsapp"
APPSTORE_URL = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"
APPSTORE_FETCH = "https://apps.apple.com/us/app/id310633997"
APPSTORE_KEY = "APP_STORE:us:310633997"

ALICE = H._Addr("0x" + "a" * 40)
BOB = H._Addr("0x" + "b" * 40)
CAROL = H._Addr("0x" + "c" * 40)
OWNER = H._Addr("0x" + "d" * 40)

TODAY = MOD._days_from_civil(2026, 9, 14)
NOW_ISO = "2026-09-14T12:00:00Z"
NOW = MOD._epoch_from_iso(NOW_ISO)


def reset_chain(sender=ALICE, value=0, when=NOW_ISO):
    H.MESSAGE.sender_address = sender
    H.MESSAGE.value = value
    H.MESSAGE.raw = {"datetime": when}
    H.TRANSFERS.clear()
    H.RENDER_LOG.clear()
    H.PAGE_MAP.clear()
    H.PAGE_MAP[AMAZON_URL] = fixture("amazon_echo_dot")
    H.PAGE_MAP[GPLAY_FETCH] = fixture("gplay_whatsapp")
    H.PAGE_MAP[APPSTORE_FETCH] = fixture("appstore_whatsapp")


def at(when):
    H.MESSAGE.raw = {"datetime": when}


def as_sender(who, value=0):
    H.MESSAGE.sender_address = who
    H.MESSAGE.value = value


def fresh_guard(owner=OWNER):
    reset_chain(sender=owner)
    c = FULL.ReviewGuard()
    as_sender(ALICE)
    return c


# ---------------------------------------------------------------------------
# synthetic page builders
#
# Used only where a REAL page cannot supply the shape under test — a page with
# a bought-review signature, a page with two reviews, a page whose dates are all
# one day. The three real fixtures cover everything else, and every test that
# CAN use a real page does.
# ---------------------------------------------------------------------------

GENERIC_BODY = ("Great product! Works exactly as described. "
                "Highly recommend to everyone.")

LONG_WORDS = ("battery life charge cable port sound bass treble volume setup "
              "app pairing comfortable travel commute noise cancelling "
              "wireless case firmware update price value durable plastic "
              "metal bluetooth range latency microphone ambient transparency "
              "seal fit ear tips foam silicone charging dock indicator").split()


def _varied_body(seed, n_words=90):
    out = []
    x = seed * 7919 + 13
    for _ in range(n_words):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        out.append(LONG_WORDS[x % len(LONG_WORDS)])
    return " ".join(out)


def amazon_page(title="A Product Under Test", hist=(70, 15, 7, 3, 5),
                reviews=(), photos=False, response=False, avg="4.3",
                total="12,431"):
    L = ["Skip to", "Main content", "", "Click to see full view", title,
         "Visit the Store", avg, avg + " out of 5 stars", "(" + total + ")",
         "", "Customer reviews", avg + " out of 5 stars", avg + " out of 5",
         total + " global ratings"]
    for star, p in zip((5, 4, 3, 2, 1), hist):
        L += ["%d star" % star, "%d%%" % p]
    if photos:
        L += ["Reviews with images", "See all photos"]
    if response:
        L += ["Manufacturer's response", "Thanks for the feedback."]
    L += ["Top reviews from the United States"]
    for r in reviews:
        L += [r["name"], "%d out of 5 stars" % r["rating"], r.get("title", "T"),
              "Reviewed in the United States on " + r["date"]]
        if r.get("verified", True):
            L.append("Verified Purchase")
        L += ["", r["body"], ""]
        if r.get("helpful") is not None:
            n = r["helpful"]
            L.append("One person found this helpful" if n == 1
                     else "%d people found this helpful" % n)
        L += ["Helpful", "Report"]
    return "\n".join(L)


def organic_reviews(n=9):
    names = ["Dan R.", "Priya S.", "Marcus Webb", "J. Kemp", "Ana Liu",
             "T. Okafor", "Sam Delgado", "Wei Zhang", "Nora B.", "Kit Alvarez",
             "Ruth Mbeki", "Leo Fontana"]
    dates = ["June 2, 2023", "January 14, 2024", "August 9, 2024",
             "March 22, 2025", "November 5, 2022", "May 30, 2025",
             "February 2, 2024", "July 18, 2023", "April 4, 2026",
             "September 1, 2022", "December 12, 2024", "October 7, 2025"]
    ratings = [5, 5, 4, 5, 3, 5, 4, 1, 5, 2, 4, 5]
    helpful = [12, 3, 44, 0, 7, 19, 2, 88, 5, 31, 6, 14]
    out = []
    for i in range(n):
        out.append({"name": names[i % 12], "rating": ratings[i % 12],
                    "title": "Review %d" % i, "date": dates[i % 12],
                    "verified": True, "body": _varied_body(i, 110),
                    "helpful": helpful[i % 12]})
    return out


def bought_reviews(n=10):
    out = []
    for i in range(n):
        out.append({"name": "Mike284%d" % i if i % 2 == 0 else "Amazon Customer",
                    "rating": 5, "title": "Five Stars",
                    "date": "March 3, 2026", "verified": False,
                    "body": GENERIC_BODY, "helpful": None})
    return out


class Case(unittest.TestCase):
    def setUp(self):
        reset_chain()


# ---------------------------------------------------------------------------
# 1. URL handling — detection, extraction, canonicalisation
# ---------------------------------------------------------------------------

class TestPlatformDetection(Case):
    def test_amazon_com(self):
        self.assertEqual(MOD._detect_platform(AMAZON_URL), P_AMAZON)

    def test_amazon_locales_all_detect(self):
        for host in MOD.PLATFORM_HOSTS[P_AMAZON]:
            url = "https://www." + host + "/dp/B07FZ8S74R"
            self.assertEqual(MOD._detect_platform(url), P_AMAZON, host)

    def test_google_play(self):
        self.assertEqual(MOD._detect_platform(GPLAY_URL), P_GPLAY)

    def test_app_store(self):
        self.assertEqual(MOD._detect_platform(APPSTORE_URL), P_APPSTORE)

    def test_no_scheme_still_detects(self):
        self.assertEqual(MOD._detect_platform("amazon.com/dp/B07FZ8S74R"),
                         P_AMAZON)

    def test_bare_www_still_detects(self):
        self.assertEqual(MOD._detect_platform("www.amazon.com/dp/B07FZ8S74R"),
                         P_AMAZON)

    def test_a_LOOKALIKE_HOST_IS_NOT_AMAZON(self):
        """`amazon.com.evil.test` must not match `amazon.com`.

        A suffix test written as `known in host` would match it, and a
        submitter who could get that through would point five validators at a
        server they control and manufacture any verdict they liked."""
        for bad in ("https://amazon.com.evil.test/dp/B07FZ8S74R",
                    "https://notamazon.com/dp/B07FZ8S74R",
                    "https://amazon.com.co/dp/B07FZ8S74R",
                    "https://play.google.com.evil.test/store/apps/"
                    "details?id=com.x",
                    "https://apps.apple.com.attacker.io/us/app/id1"):
            self.assertEqual(MOD._detect_platform(bad), "", bad)

    def test_subdomain_of_a_known_host_is_accepted(self):
        self.assertEqual(
            MOD._detect_platform("https://smile.amazon.com/dp/B07FZ8S74R"),
            P_AMAZON)

    def test_blocked_platforms_are_not_detected(self):
        """The eleven platforms the probe measured as unreadable are absent
        from the host table, so they detect as nothing — see docs/PROBE.md."""
        for url in ("https://www.trustpilot.com/review/amazon.com",
                    "https://www.yelp.com/biz/starbucks-new-york",
                    "https://www.google.com/maps/place/Starbucks",
                    "https://www.walmart.com/ip/x/123",
                    "https://www.bestbuy.com/site/x/1.p",
                    "https://www.tripadvisor.com/Restaurant_Review-x",
                    "https://www.etsy.com/listing/1",
                    "https://www.g2.com/products/slack/reviews",
                    "https://www.imdb.com/title/tt0111161/reviews/",
                    "https://www.newegg.com/p/N82E1",
                    "https://www.goodreads.com/book/show/1",
                    "https://www.target.com/p/-/A-1",
                    "https://store.steampowered.com/app/730/"):
            self.assertEqual(MOD._detect_platform(url), "", url)

    def test_empty_and_garbage(self):
        for bad in ("", "   ", "not a url", "ftp://", "://", "/dp/B07FZ8S74R"):
            self.assertEqual(MOD._detect_platform(bad), "")

    def test_a_path_traversal_host_is_refused(self):
        self.assertEqual(MOD._detect_platform("https://../../amazon.com/dp/X"),
                         "")


class TestAmazonAsin(Case):
    def test_plain_dp(self):
        self.assertEqual(MOD._amazon_asin(AMAZON_URL), "B07FZ8S74R")

    def test_seo_url_with_ref(self):
        self.assertEqual(MOD._amazon_asin(
            "https://www.amazon.com/Echo-Dot-3rd-Gen/dp/B07FZ8S74R/"
            "ref=sr_1_3?crid=X&keywords=echo"), "B07FZ8S74R")

    def test_gp_product(self):
        self.assertEqual(MOD._amazon_asin(
            "https://www.amazon.com/gp/product/B07FZ8S74R"), "B07FZ8S74R")

    def test_lowercase_asin_is_uppercased(self):
        self.assertEqual(MOD._amazon_asin(
            "https://www.amazon.com/dp/b07fz8s74r"), "B07FZ8S74R")

    def test_no_asin(self):
        for bad in ("https://www.amazon.com/",
                    "https://www.amazon.com/s?k=echo+dot",
                    "https://www.amazon.com/dp/TOO_SHORT"):
            self.assertEqual(MOD._amazon_asin(bad), "", bad)

    def test_an_asin_with_punctuation_is_refused(self):
        self.assertEqual(MOD._amazon_asin(
            "https://www.amazon.com/dp/B07FZ8S7.R"), "")


class TestCanonicalisation(Case):
    def test_amazon_key_and_fetch_url(self):
        key, fetch, why = MOD._canonical(AMAZON_URL, P_AMAZON)
        self.assertEqual(why, "")
        self.assertEqual(key, AMAZON_KEY)
        self.assertEqual(fetch, "https://www.amazon.com/dp/B07FZ8S74R")

    def test_every_amazon_url_shape_reaches_one_key(self):
        shapes = [AMAZON_URL,
                  "http://amazon.com/dp/B07FZ8S74R",
                  "www.amazon.com/dp/b07fz8s74r?th=1",
                  "https://www.amazon.com/Echo-Dot/dp/B07FZ8S74R/ref=x",
                  "https://smile.amazon.com/gp/product/B07FZ8S74R"]
        keys = set()
        for s in shapes:
            key, _f, why = MOD._canonical(s, MOD._detect_platform(s))
            self.assertEqual(why, "", s)
            keys.add(key)
        self.assertEqual(keys, {AMAZON_KEY})

    def test_AMAZON_LOCALE_IS_PART_OF_IDENTITY(self):
        """amazon.com and amazon.co.uk are DIFFERENT catalogues with different
        reviews. Collapsing them would file one country's manipulation under
        another country's listing."""
        a, _f, _w = MOD._canonical("https://www.amazon.com/dp/B07FZ8S74R",
                                   P_AMAZON)
        b, _f, _w = MOD._canonical("https://www.amazon.co.uk/dp/B07FZ8S74R",
                                   P_AMAZON)
        self.assertNotEqual(a, b)

    def test_THE_FETCH_URL_IS_REBUILT_NOT_ECHOED(self):
        """The host is never taken from the caller. Whatever path, query or
        fragment a submitter sends, the fetched URL is assembled from the fixed
        host table and the extracted identifier."""
        key, fetch, why = MOD._canonical(
            "https://www.amazon.com/dp/B07FZ8S74R/@evil.test/?x=1#y", P_AMAZON)
        self.assertEqual(why, "")
        self.assertEqual(fetch, "https://www.amazon.com/dp/B07FZ8S74R")
        self.assertNotIn("evil", fetch)

    def test_amazon_reviews_page_is_never_the_fetch_target(self):
        """docs/PROBE.md §2.4: /product-reviews/ renders a 607-character
        SIGN-IN WALL. Only /dp/ carries the reviews."""
        _k, fetch, _w = MOD._canonical(
            "https://www.amazon.com/product-reviews/B07FZ8S74R", P_AMAZON)
        self.assertIn("/dp/", fetch)
        self.assertNotIn("product-reviews", fetch)

    def test_gplay_key_and_pinned_language(self):
        key, fetch, why = MOD._canonical(GPLAY_URL, P_GPLAY)
        self.assertEqual(why, "")
        self.assertEqual(key, GPLAY_KEY)
        self.assertIn("hl=en", fetch)
        self.assertIn("gl=US", fetch)

    def test_gplay_rejects_a_non_package_id(self):
        for bad in ("https://play.google.com/store/apps/details?id=nodots",
                    "https://play.google.com/store/apps/details",
                    "https://play.google.com/store/apps/details?id=a b.c",
                    "https://play.google.com/store/apps/details?id=" + "x" * 200):
            key, _f, why = MOD._canonical(bad, P_GPLAY)
            self.assertNotEqual(why, "", bad)
            self.assertEqual(key, "")

    def test_appstore_key_keeps_country(self):
        key, fetch, why = MOD._canonical(APPSTORE_URL, P_APPSTORE)
        self.assertEqual(why, "")
        self.assertEqual(key, APPSTORE_KEY)
        self.assertEqual(fetch, APPSTORE_FETCH)
        gb, _f, _w = MOD._canonical(
            "https://apps.apple.com/gb/app/whatsapp/id310633997", P_APPSTORE)
        self.assertNotEqual(key, gb)

    def test_appstore_without_country_defaults_to_us(self):
        key, _f, why = MOD._canonical(
            "https://apps.apple.com/app/whatsapp-messenger/id310633997",
            P_APPSTORE)
        self.assertEqual(why, "")
        self.assertEqual(key, APPSTORE_KEY)

    def test_appstore_rejects_missing_id(self):
        key, _f, why = MOD._canonical(
            "https://apps.apple.com/us/app/whatsapp-messenger", P_APPSTORE)
        self.assertNotEqual(why, "")
        self.assertEqual(key, "")

    def test_unsupported_platform_string(self):
        key, _f, why = MOD._canonical("https://x.test/y", "YELP")
        self.assertEqual(key, "")
        self.assertEqual(why, "unsupported platform")

    def test_source_url_round_trips_every_platform(self):
        for url in (AMAZON_URL, GPLAY_URL, APPSTORE_URL):
            plat = MOD._detect_platform(url)
            key, _f, _w = MOD._canonical(url, plat)
            back = MOD._source_url(key)
            self.assertEqual(MOD._detect_platform(back), plat, key)
            again, _f2, _w2 = MOD._canonical(back, plat)
            self.assertEqual(again, key)

    def test_source_url_of_garbage_is_empty(self):
        self.assertEqual(MOD._source_url(""), "")
        self.assertEqual(MOD._source_url("NOPLATFORM"), "")
        self.assertEqual(MOD._source_url("WEIRD:thing"), "")


# ---------------------------------------------------------------------------
# 2. The quantisers — where ALL the consensus tolerance lives
# ---------------------------------------------------------------------------

class TestQuantisers(Case):
    def test_q_rounds_half_up(self):
        self.assertEqual(MOD._q(0, 5), 0)
        self.assertEqual(MOD._q(2, 5), 0)
        self.assertEqual(MOD._q(3, 5), 5)
        self.assertEqual(MOD._q(7, 5), 5)
        self.assertEqual(MOD._q(8, 5), 10)
        self.assertEqual(MOD._q(100, 5), 100)

    def test_q_step_one_is_identity(self):
        for v in (0, 1, 7, 99, 12345):
            self.assertEqual(MOD._q(v, 1), v)

    def test_q_is_idempotent(self):
        for v in range(0, 200):
            once = MOD._q(v, 5)
            self.assertEqual(MOD._q(once, 5), once, v)

    def test_sig3_keeps_three_figures(self):
        self.assertEqual(MOD._sig3(0), 0)
        self.assertEqual(MOD._sig3(7), 7)
        self.assertEqual(MOD._sig3(999), 999)
        self.assertEqual(MOD._sig3(1234), 1230)
        self.assertEqual(MOD._sig3(1235), 1240)
        self.assertEqual(MOD._sig3(1037930), 1040000)
        self.assertEqual(MOD._sig3(239000000), 239000000)

    def test_sig3_is_idempotent(self):
        for v in (0, 5, 999, 1234, 99999, 1037930, 987654321):
            once = MOD._sig3(v)
            self.assertEqual(MOD._sig3(once), once, v)

    def test_A_LIVE_REVIEW_COUNT_TICK_STILL_AGREES(self):
        """The load-bearing property. Two validators render the same Amazon
        page seconds apart and the global-ratings figure has moved by one.
        `_agrees` demands exact equality, so the quantiser must absorb it."""
        self.assertEqual(MOD._sig3(1037930), MOD._sig3(1037931))
        self.assertEqual(MOD._sig3(1037930), MOD._sig3(1038000))

    def test_A_REAL_MOVE_CORRECTLY_DOES_NOT_AGREE(self):
        """And it must NOT absorb news. A quantiser that flattened everything
        would make the oracle agree on a number that means nothing."""
        self.assertNotEqual(MOD._sig3(1037930), MOD._sig3(1237930))
        self.assertNotEqual(MOD._q(40, 5), MOD._q(60, 5))

    def test_pct_never_divides_by_zero(self):
        self.assertEqual(MOD._pct(5, 0), 0)
        self.assertEqual(MOD._pct(0, 0), 0)

    def test_pct_is_clamped(self):
        self.assertEqual(MOD._pct(10, 5), 100)
        self.assertEqual(MOD._pct(3, 4), 75)

    def test_median_of_empty_is_zero(self):
        self.assertEqual(MOD._median([]), 0)

    def test_median_odd_and_even(self):
        self.assertEqual(MOD._median([3, 1, 2]), 2)
        self.assertEqual(MOD._median([4, 1, 2, 3]), 2)

    def test_median_is_order_independent(self):
        self.assertEqual(MOD._median([9, 1, 5, 3, 7]),
                         MOD._median([1, 3, 5, 7, 9]))


class TestAsIntExcludesBool(Case):
    def test_BOOL_IS_NOT_AN_INT_HERE(self):
        """`bool` IS an `int` in Python. Without the explicit exclusion a
        `True` arriving in a vector field would silently score as 1 rather than
        being caught as the wrong type."""
        self.assertEqual(MOD._as_int(True, -9), -9)
        self.assertEqual(MOD._as_int(False, -9), -9)

    def test_ints_pass_through(self):
        self.assertEqual(MOD._as_int(0), 0)
        self.assertEqual(MOD._as_int(-4), -4)

    def test_numeric_strings(self):
        self.assertEqual(MOD._as_int("42"), 42)
        self.assertEqual(MOD._as_int("-42"), -42)
        self.assertEqual(MOD._as_int(" 7 "), 7)

    def test_garbage_returns_default(self):
        for bad in ("", "abc", "4.5", None, [], {}, "0x10"):
            self.assertEqual(MOD._as_int(bad, -1), -1, repr(bad))


class TestNoStrReplace(Case):
    def test_swap_matches_what_replace_would_do(self):
        for text, old, new in (("a b c", " ", "_"), ("aaa", "a", "bb"),
                               ("", "x", "y"), ("abc", "z", "q"),
                               ("hello world", "o", "0"),
                               ("xx", "xx", ""), ("abcabc", "abc", "-")):
            self.assertEqual(MOD._swap(text, old, new),
                             text.replace(old, new), (text, old, new))

    def test_swap_with_empty_needle_terminates(self):
        self.assertEqual(MOD._swap("abc", "", "X"), "abc")

    def test_STR_REPLACE_IS_NEVER_USED(self):
        """The runner REJECTS `str.replace()`. The first render probe carried
        one and would not deploy. This walks the AST of both contracts rather
        than grepping, so a call spelled across a line break is still caught."""
        import ast
        for path in (SOURCE, CONSUMER):
            tree = ast.parse(path.read_text(encoding="utf8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "replace":
                    self.fail("%s uses .replace() at line %d"
                              % (path.name, node.lineno))


class TestIntFromCommas(Case):
    def test_plain_commas(self):
        self.assertEqual(MOD._int_from_commas("1,037,930"), 1037930)

    def test_compact_forms(self):
        self.assertEqual(MOD._int_from_commas("239M"), 239000000)
        self.assertEqual(MOD._int_from_commas("19M"), 19000000)
        self.assertEqual(MOD._int_from_commas("3.5K"), 3500)
        self.assertEqual(MOD._int_from_commas("1.2B"), 1200000000)

    def test_A_COMPACT_FORM_IS_NOT_READ_AS_ITS_DIGITS(self):
        """`239M` read by a plain digit strip is 239 — a thousand-fold
        understatement that would make a hugely-reviewed app look obscure."""
        self.assertNotEqual(MOD._int_from_commas("239M"), 239)

    def test_empty_and_garbage(self):
        for bad in ("", "   ", "abc", "M"):
            self.assertEqual(MOD._int_from_commas(bad), 0, repr(bad))

    def test_trailing_words_ignored(self):
        self.assertEqual(MOD._int_from_commas("1,037,930 "), 1037930)


# ---------------------------------------------------------------------------
# 3. Dates — three formats, one integer calendar, block time as the only clock
# ---------------------------------------------------------------------------

class TestDates(Case):
    def test_civil_epoch_anchor(self):
        self.assertEqual(MOD._days_from_civil(1970, 1, 1), 0)
        self.assertEqual(MOD._days_from_civil(1970, 1, 2), 1)
        self.assertEqual(MOD._days_from_civil(2000, 3, 1), 11017)

    def test_leap_day(self):
        a = MOD._days_from_civil(2024, 2, 28)
        b = MOD._days_from_civil(2024, 2, 29)
        c = MOD._days_from_civil(2024, 3, 1)
        self.assertEqual(b - a, 1)
        self.assertEqual(c - b, 1)

    def test_amazon_long_form(self):
        self.assertEqual(MOD._parse_date("December 14, 2019", TODAY),
                         MOD._days_from_civil(2019, 12, 14))

    def test_google_play_long_form(self):
        self.assertEqual(MOD._parse_date("August 28, 2026", TODAY),
                         MOD._days_from_civil(2026, 8, 28))

    def test_appstore_slash_form(self):
        self.assertEqual(MOD._parse_date("06/14/2023", TODAY),
                         MOD._days_from_civil(2023, 6, 14))

    def test_two_digit_year(self):
        self.assertEqual(MOD._parse_date("6/14/23", TODAY),
                         MOD._days_from_civil(2023, 6, 14))

    def test_abbreviated_month(self):
        self.assertEqual(MOD._parse_date("Sep 11, 2026", TODAY),
                         MOD._days_from_civil(2026, 9, 11))

    def test_A_YEARLESS_DATE_RESOLVES_AGAINST_BLOCK_TIME(self):
        """`Jan 21` is what the App Store prints for a recent review. It has no
        year, and resolving it against a WALL CLOCK would differ per validator
        and put the date on the disagreement side of consensus. It is resolved
        against block time — part of the transaction, identical for everyone."""
        got = MOD._parse_date("Jan 21", TODAY)
        self.assertEqual(got, MOD._days_from_civil(2026, 1, 21))

    def test_a_yearless_date_never_resolves_into_the_future(self):
        """`Dec 30` seen on 14 September 2026 means LAST December, not one
        three months away. A future review date is not a thing."""
        got = MOD._parse_date("Dec 30", TODAY)
        self.assertLessEqual(got, TODAY)
        self.assertEqual(got, MOD._days_from_civil(2025, 12, 30))

    def test_a_yearless_date_is_deterministic_for_one_block_time(self):
        a = MOD._parse_date("Jan 21", TODAY)
        b = MOD._parse_date("Jan 21", TODAY)
        self.assertEqual(a, b)

    def test_a_yearless_date_needs_a_clock(self):
        self.assertEqual(MOD._parse_date("Jan 21", 0), 0)

    def test_unparseable_dates_are_zero_not_a_guess(self):
        for bad in ("", "   ", "yesterday", "2 days ago", "Smarch 4, 2020",
                    "13/45/2020", "December", "2019", "on Tuesday",
                    "June 99, 2020", "0/0/0"):
            self.assertEqual(MOD._parse_date(bad, TODAY), 0, repr(bad))

    def test_implausible_years_are_refused(self):
        self.assertEqual(MOD._parse_date("June 2, 1066", TODAY), 0)
        self.assertEqual(MOD._parse_date("June 2, 3999", TODAY), 0)

    def test_iso_epoch(self):
        self.assertEqual(MOD._epoch_from_iso("1970-01-01T00:00:00Z"), 0)
        self.assertEqual(MOD._epoch_from_iso("2026-09-14T12:00:00Z"),
                         MOD._days_from_civil(2026, 9, 14) * 86400 + 43200)

    def test_iso_garbage_is_zero(self):
        for bad in ("", "nope", "2026-13-45T99:99:99Z", None, 12345):
            self.assertEqual(MOD._epoch_from_iso(bad), 0, repr(bad))


# ---------------------------------------------------------------------------
# 4. Extraction against REAL RENDERED PAGES
#
# Every assertion below is against bytes a validator actually saw, pulled off
# studio-dev on 2026-09-14 by contracts/_render_probe.py. An extraction test
# written against invented text proves nothing about on-chain behaviour.
# ---------------------------------------------------------------------------

class TestAmazonExtraction(Case):
    def setUp(self):
        super().setUp()
        self.p = MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY)

    def test_title_is_the_product_not_the_chrome(self):
        """The first version of this took the first substantial line and got
        "To move between items, use your keyboard's up or down arrows." The
        title is anchored on the buy-box rating and found by walking BACK."""
        self.assertEqual(
            self.p["title"],
            "Echo Dot (3rd Gen, 2018 release) - Smart speaker with Alexa - "
            "Charcoal")

    def test_average_rating(self):
        self.assertEqual(self.p["avg_rating_x10"], 47)

    def test_total_ratings(self):
        self.assertEqual(self.p["total_ratings"], 1037930)

    def test_rating_histogram(self):
        self.assertEqual(self.p["pct"], [83, 12, 4, 0, 1])

    def test_histogram_sums_near_100(self):
        self.assertGreaterEqual(sum(self.p["pct"]), 90)
        self.assertLessEqual(sum(self.p["pct"]), 110)

    def test_eight_reviews_parsed(self):
        self.assertEqual(len(self.p["reviews"]), 8)

    def test_CAROUSEL_RATINGS_ARE_NOT_COUNTED_AS_REVIEWS(self):
        """The page carries a carousel of RELATED products above the review
        section whose lines read `4.2 out of 5 stars`. A whole-page scan reads
        those as reviews of this product. Six such lines sit above the customer
        reviews on this fixture; the parser starts at `Top reviews from`."""
        text = fixture("amazon_echo_dot")
        above = text[:text.find("Top reviews from")]
        self.assertGreaterEqual(above.count(" out of 5 stars"), 6)
        self.assertEqual(len(self.p["reviews"]), 8)

    def test_every_review_has_a_rating_in_range(self):
        for r in self.p["reviews"]:
            self.assertTrue(1 <= r["rating"] <= 5, r)

    def test_every_review_has_a_date(self):
        for r in self.p["reviews"]:
            self.assertGreater(r["day"], 0, r["name"])

    def test_every_review_has_a_body(self):
        for r in self.p["reviews"]:
            self.assertGreater(len(r["body"]), 200, r["name"])

    def test_reviewer_names(self):
        names = [r["name"] for r in self.p["reviews"]]
        self.assertIn("Tango's product reviews", names)
        self.assertIn("Amazon Customer", names)
        self.assertIn("Okie1010", names)

    def test_verified_purchase_flags(self):
        self.assertEqual(sum(1 for r in self.p["reviews"] if r["verified"]), 8)

    def test_helpful_counts_including_the_word_one(self):
        """Amazon spells the singular as `One person found this helpful`. A
        digit-only parse reads it as zero — reporting a review that HAD
        engagement as having none."""
        helpful = sorted(r["helpful"] for r in self.p["reviews"])
        self.assertIn(1, helpful)
        self.assertIn(119, helpful)
        self.assertEqual(sum(1 for h in helpful if h < 0), 3)

    def test_photos_detected(self):
        self.assertTrue(self.p["has_photos"])

    def test_no_seller_response_on_this_page(self):
        self.assertFalse(self.p["has_response"])

    def test_body_does_not_swallow_the_helpful_line(self):
        for r in self.p["reviews"]:
            self.assertNotIn("found this helpful", r["body"])
            self.assertNotIn("Verified Purchase", r["body"])

    def test_body_does_not_swallow_the_next_review(self):
        for r in self.p["reviews"]:
            self.assertNotIn("out of 5 stars", r["body"])


class TestGooglePlayExtraction(Case):
    def setUp(self):
        super().setUp()
        self.p = MOD._parse_gplay(fixture("gplay_whatsapp"), TODAY)

    def test_title(self):
        self.assertEqual(self.p["title"], "WhatsApp Messenger")

    def test_average_rating(self):
        self.assertEqual(self.p["avg_rating_x10"], 46)

    def test_THE_SECTION_HEADING_IS_NOT_READ_AS_A_COUNT(self):
        """The heading is `Ratings and reviews`, which also ends in
        " reviews". Without a digit test the count parses out of the word
        "and" as ZERO — and a zero review count is a real measurement, so
        nothing downstream would have caught it."""
        self.assertEqual(self.p["total_ratings"], 239000000)

    def test_no_rating_histogram_is_published(self):
        """RULE 7. The labels `5 4 3 2 1` render; the bar values are DRAWN, not
        written. There is nothing there to read, so it is UNAVAILABLE."""
        self.assertEqual(self.p["pct"], [UNAVAIL] * 5)

    def test_three_reviews_parsed(self):
        self.assertEqual(len(self.p["reviews"]), 3)

    def test_reviewer_names(self):
        names = [r["name"] for r in self.p["reviews"]]
        self.assertEqual(names,
                         ["Jonathan Spencer", "Yehudah Schwartz",
                          "Grace De Jesus"])

    def test_dates_parsed(self):
        for r in self.p["reviews"]:
            self.assertGreater(r["day"], 0, r["name"])

    def test_helpful_counts(self):
        self.assertEqual([r["helpful"] for r in self.p["reviews"]],
                         [6, 15, 21])

    def test_bodies_are_substantial(self):
        for r in self.p["reviews"]:
            self.assertGreater(len(r["body"]), 300, r["name"])

    def test_body_stops_before_the_helpful_line(self):
        for r in self.p["reviews"]:
            self.assertNotIn("people found this review helpful", r["body"])
            self.assertNotIn("Did you find this helpful", r["body"])


class TestAppStoreExtraction(Case):
    def setUp(self):
        super().setUp()
        self.p = MOD._parse_appstore(fixture("appstore_whatsapp"), TODAY)

    def test_title(self):
        self.assertEqual(self.p["title"], "WhatsApp Messenger")

    def test_average_and_total(self):
        self.assertEqual(self.p["avg_rating_x10"], 47)
        self.assertEqual(self.p["total_ratings"], 19000000)

    def test_four_reviews_parsed(self):
        self.assertEqual(len(self.p["reviews"]), 4)

    def test_BOTH_DATE_FORMATS_ON_ONE_PAGE(self):
        """`Jan 21` for the newest review and `06/14/2023` for older ones, on
        the same page. Anchoring the block on whichever middle line PARSES as a
        date is what lets one rule read both."""
        days = sorted(r["day"] for r in self.p["reviews"])
        self.assertEqual(len(days), 4)
        self.assertIn(MOD._days_from_civil(2026, 1, 21), days)
        self.assertIn(MOD._days_from_civil(2023, 6, 14), days)

    def test_nicknames(self):
        names = [r["name"] for r in self.p["reviews"]]
        self.assertIn("Lol_hahahahahah", names)
        self.assertIn("Rubdujbj", names)

    def test_titles_captured(self):
        titles = [r["title"] for r in self.p["reviews"]]
        self.assertIn("WhatsApp not bad", titles)
        self.assertIn("Audio Calls", titles)

    def test_no_helpful_votes_are_published(self):
        for r in self.p["reviews"]:
            self.assertEqual(r["helpful"], -1)

    def test_no_per_review_rating_is_published(self):
        for r in self.p["reviews"]:
            self.assertEqual(r["rating"], 0)

    def test_the_reviews_section_stops_before_whats_new(self):
        for r in self.p["reviews"]:
            self.assertNotIn("We update the app regularly", r["body"])
            self.assertNotIn("Data Linked to You", r["body"])


class TestParsersOnAlienInput(Case):
    """No parser may raise on anything. A page that changed shape overnight
    must produce an empty extraction the caller gets refunded for, never a
    revert that keeps their deposit."""

    ALIEN = ("", "   ", "\n\n\n", "<html></html>", "x" * 5000,
             "Customer reviews", "Top reviews from the United States",
             "Ratings and reviews", "Ratings & Reviews",
             "5 out of 5 stars", "more_vert", "Reviewed in the United States",
             "Ratings & Reviews\n4.7\nout of 5\n19M Ratings",
             "Customer reviews\n5 star\n" + "9" * 40)

    def test_amazon_parser_never_raises(self):
        for text in self.ALIEN:
            MOD._parse_amazon(text, TODAY)

    def test_gplay_parser_never_raises(self):
        for text in self.ALIEN:
            MOD._parse_gplay(text, TODAY)

    def test_appstore_parser_never_raises(self):
        for text in self.ALIEN:
            MOD._parse_appstore(text, TODAY)

    def test_each_parser_survives_the_others_page(self):
        for name in ("amazon_echo_dot", "gplay_whatsapp",
                     "appstore_whatsapp"):
            text = fixture(name)
            for fn in (MOD._parse_amazon, MOD._parse_gplay,
                       MOD._parse_appstore):
                out = fn(text, TODAY)
                self.assertIsInstance(out["reviews"], list)

    def test_a_page_of_only_stop_words_yields_nothing(self):
        text = "\n".join(["Helpful", "Report", "Read more"] * 50)
        self.assertEqual(len(MOD._parse_amazon(text, TODAY)["reviews"]), 0)


# ---------------------------------------------------------------------------
# 5. The five ladders
# ---------------------------------------------------------------------------

def vec(**over):
    """A complete, valid feature vector with everything at a neutral middle,
    so a ladder test moves exactly one thing."""
    f = {
        "reviews_parsed": 8, "avg_rating_x10": 43, "total_ratings": 12400,
        "pct_5": 70, "pct_4": 15, "pct_3": 7, "pct_2": 3, "pct_1": 5,
        "dated_reviews": 8, "distinct_days": 8, "max_same_day": 1,
        "span_days": 400, "median_chars": 400, "short_pct": 0,
        "dup_open_pct": 0, "lexical_pct": 60, "verified_pct": 100,
        "distinct_names_pct": 100, "weak_handle_pct": 0, "helpful_pct": 75,
        "helpful_total": 120, "has_photos": 1, "has_response": 0,
        "page_chars": 38000, "reviews_section": 1,
    }
    f.update(over)
    return f


AMZ = MOD.PLATFORM_DIMS[P_AMAZON]
GP = MOD.PLATFORM_DIMS[P_GPLAY]
AS_ = MOD.PLATFORM_DIMS[P_APPSTORE]


class TestTimingLadder(Case):
    def test_all_on_one_day_is_the_floor(self):
        f = vec(dated_reviews=10, reviews_parsed=10, distinct_days=1,
                max_same_day=10, span_days=0)
        self.assertEqual(MOD._dim_timing(f, AMZ), 0)

    def test_spread_over_years_is_the_ceiling(self):
        f = vec(dated_reviews=9, reviews_parsed=9, distinct_days=9,
                max_same_day=1, span_days=1200)
        self.assertEqual(MOD._dim_timing(f, AMZ), 7)

    def test_the_ladder_is_monotone_in_spread(self):
        prev = -1
        for distinct in range(2, 11):
            f = vec(dated_reviews=10, reviews_parsed=10,
                    distinct_days=distinct,
                    max_same_day=10 - distinct + 1, span_days=400)
            got = MOD._dim_timing(f, AMZ)
            self.assertGreaterEqual(got, prev, distinct)
            prev = got

    def test_a_tight_window_is_penalised_even_when_spread(self):
        """Eight reviews on eight consecutive days are perfectly 'spread' and
        are still a campaign."""
        wide = vec(dated_reviews=8, reviews_parsed=8, distinct_days=8,
                   max_same_day=1, span_days=800)
        tight = vec(dated_reviews=8, reviews_parsed=8, distinct_days=8,
                    max_same_day=1, span_days=8)
        self.assertGreater(MOD._dim_timing(wide, AMZ),
                           MOD._dim_timing(tight, AMZ))

    def test_a_burst_is_penalised(self):
        clean = vec(dated_reviews=10, reviews_parsed=10, distinct_days=8,
                    max_same_day=2, span_days=400)
        burst = vec(dated_reviews=10, reviews_parsed=10, distinct_days=8,
                    max_same_day=7, span_days=400)
        self.assertGreater(MOD._dim_timing(clean, AMZ),
                           MOD._dim_timing(burst, AMZ))

    def test_UNAVAILABLE_WITHOUT_ENOUGH_DATES(self):
        """A page whose reviews rendered without parseable dates cannot be
        measured on this axis, and must say so rather than score zero."""
        f = vec(dated_reviews=2, reviews_parsed=8)
        self.assertEqual(MOD._dim_timing(f, AMZ), UNAVAIL)
        f0 = vec(dated_reviews=0, reviews_parsed=8)
        self.assertEqual(MOD._dim_timing(f0, AMZ), UNAVAIL)

    def test_always_in_range(self):
        for d in range(1, 13):
            for s in (0, 3, 20, 100, 4000):
                f = vec(dated_reviews=12, reviews_parsed=12, distinct_days=d,
                        max_same_day=13 - d, span_days=s)
                got = MOD._dim_timing(f, AMZ)
                self.assertTrue(got == UNAVAIL or 0 <= got <= 7, (d, s, got))


class TestRatingLadder(Case):
    def test_all_five_star_is_the_floor(self):
        f = vec(pct_5=100, pct_4=0, pct_3=0, pct_2=0, pct_1=0)
        self.assertEqual(MOD._dim_rating(f, AMZ), 0)

    def test_a_natural_spread_is_the_ceiling(self):
        f = vec(pct_5=62, pct_4=19, pct_3=9, pct_2=4, pct_1=6)
        self.assertEqual(MOD._dim_rating(f, AMZ), 7)

    def test_the_real_echo_dot_histogram_is_mid_high(self):
        """83/12/4/0/1 with a million ratings: genuinely well liked, with a
        thin negative tail. It should score well but not perfectly."""
        f = vec(pct_5=83, pct_4=12, pct_3=4, pct_2=0, pct_1=1)
        got = MOD._dim_rating(f, AMZ)
        self.assertGreaterEqual(got, 4)
        self.assertLessEqual(got, 6)

    def test_A_WELL_LIKED_PRODUCT_IS_NOT_CALLED_MANIPULATED(self):
        """The failure mode that matters most: punishing a good product for
        being good. A 90%-five-star page with a real negative tail and a real
        middle must still clear the floor comfortably."""
        f = vec(pct_5=88, pct_4=8, pct_3=2, pct_2=1, pct_1=1)
        self.assertGreaterEqual(MOD._dim_rating(f, AMZ), 3)

    def test_monotone_in_five_star_share(self):
        prev = 99
        for p5 in (60, 70, 80, 85, 90, 95, 99):
            rest = 100 - p5
            f = vec(pct_5=p5, pct_4=rest, pct_3=0, pct_2=0, pct_1=0)
            got = MOD._dim_rating(f, AMZ)
            self.assertLessEqual(got, prev, p5)
            prev = got

    def test_a_negative_tail_helps(self):
        none = vec(pct_5=80, pct_4=20, pct_3=0, pct_2=0, pct_1=0)
        some = vec(pct_5=80, pct_4=11, pct_3=4, pct_2=2, pct_1=3)
        self.assertGreater(MOD._dim_rating(some, AMZ),
                           MOD._dim_rating(none, AMZ))

    def test_UNAVAILABLE_WHERE_NO_HISTOGRAM_IS_PUBLISHED(self):
        f = vec(pct_5=UNAVAIL, pct_4=UNAVAIL, pct_3=UNAVAIL, pct_2=UNAVAIL,
                pct_1=UNAVAIL)
        self.assertEqual(MOD._dim_rating(f, GP), UNAVAIL)
        self.assertEqual(MOD._dim_rating(f, AS_), UNAVAIL)

    def test_unavailable_on_amazon_too_if_the_page_lacked_one(self):
        f = vec(pct_5=UNAVAIL, pct_4=UNAVAIL, pct_3=UNAVAIL, pct_2=UNAVAIL,
                pct_1=UNAVAIL)
        self.assertEqual(MOD._dim_rating(f, AMZ), UNAVAIL)

    def test_an_all_zero_histogram_is_unavailable_not_zero(self):
        f = vec(pct_5=0, pct_4=0, pct_3=0, pct_2=0, pct_1=0)
        self.assertEqual(MOD._dim_rating(f, AMZ), UNAVAIL)


class TestQualityLadder(Case):
    def test_short_generic_identical_is_the_floor(self):
        f = vec(median_chars=60, short_pct=100, dup_open_pct=100,
                lexical_pct=10)
        self.assertEqual(MOD._dim_quality(f, AMZ), 0)

    def test_long_varied_distinct_is_the_ceiling(self):
        f = vec(median_chars=1200, short_pct=0, dup_open_pct=0,
                lexical_pct=70)
        self.assertEqual(MOD._dim_quality(f, AMZ), 7)

    def test_monotone_in_median_length(self):
        prev = -1
        for med in (0, 120, 220, 400, 700, 2000):
            f = vec(median_chars=med, short_pct=0, dup_open_pct=0,
                    lexical_pct=50)
            got = MOD._dim_quality(f, AMZ)
            self.assertGreaterEqual(got, prev, med)
            prev = got

    def test_duplicate_openings_cost_points(self):
        clean = vec(dup_open_pct=0)
        dupes = vec(dup_open_pct=60)
        self.assertGreater(MOD._dim_quality(clean, AMZ),
                           MOD._dim_quality(dupes, AMZ))

    def test_a_page_of_one_liners_costs_points(self):
        full = vec(short_pct=0)
        thin = vec(short_pct=80)
        self.assertGreater(MOD._dim_quality(full, AMZ),
                           MOD._dim_quality(thin, AMZ))

    def test_unavailable_below_min_reviews(self):
        self.assertEqual(MOD._dim_quality(vec(reviews_parsed=2), AMZ), UNAVAIL)

    def test_available_on_every_platform(self):
        for d in (AMZ, GP, AS_):
            self.assertNotEqual(MOD._dim_quality(vec(), d), UNAVAIL)

    def test_always_in_range(self):
        for med in (0, 100, 500, 5000):
            for sp in (0, 40, 100):
                for du in (0, 30, 100):
                    for lx in (0, 50, 100):
                        f = vec(median_chars=med, short_pct=sp,
                                dup_open_pct=du, lexical_pct=lx)
                        self.assertTrue(0 <= MOD._dim_quality(f, AMZ) <= 7)


class TestCredibilityLadder(Case):
    def test_amazon_all_verified_is_the_ceiling(self):
        f = vec(verified_pct=100, weak_handle_pct=0, distinct_names_pct=100)
        self.assertEqual(MOD._dim_credibility(f, AMZ), 7)

    def test_amazon_none_verified_is_the_floor(self):
        f = vec(verified_pct=0, weak_handle_pct=100, distinct_names_pct=50)
        self.assertEqual(MOD._dim_credibility(f, AMZ), 0)

    def test_amazon_monotone_in_verified_share(self):
        prev = -1
        for v in (0, 15, 30, 45, 60, 75, 90, 100):
            f = vec(verified_pct=v, weak_handle_pct=0, distinct_names_pct=100)
            got = MOD._dim_credibility(f, AMZ)
            self.assertGreaterEqual(got, prev, v)
            prev = got

    def test_IDENTITY_BASIS_STARTS_NEUTRAL(self):
        """RULE 7 in its subtlest form. Google Play and the App Store publish
        no purchase signal, so a page of ordinary-looking reviewer names is NOT
        evidence of credibility — and must not be evidence against it either.
        It starts at a neutral 4 and moves only on actual evidence."""
        f = vec(weak_handle_pct=0, distinct_names_pct=90, verified_pct=UNAVAIL)
        self.assertEqual(MOD._dim_credibility(f, GP), 4)

    def test_identity_basis_cannot_reach_seven(self):
        """The top of this ladder reads 'established reviewers'. No page
        without a purchase signal can support that claim, and the basis that
        was used travels with the record so nobody is misled."""
        f = vec(weak_handle_pct=0, distinct_names_pct=100,
                verified_pct=UNAVAIL)
        self.assertEqual(MOD._dim_credibility(f, GP), 5)
        for w in range(0, 101, 5):
            g = vec(weak_handle_pct=w, distinct_names_pct=100,
                    verified_pct=UNAVAIL)
            self.assertLessEqual(MOD._dim_credibility(g, AS_), 6)

    def test_generated_looking_handles_cost_points_on_both_bases(self):
        for d in (AMZ, GP):
            clean = vec(weak_handle_pct=0)
            junk = vec(weak_handle_pct=80)
            self.assertGreater(MOD._dim_credibility(clean, d),
                               MOD._dim_credibility(junk, d), d)

    def test_amazon_without_a_verified_figure_is_unavailable(self):
        f = vec(verified_pct=UNAVAIL)
        self.assertEqual(MOD._dim_credibility(f, AMZ), UNAVAIL)

    def test_unavailable_below_min_reviews(self):
        self.assertEqual(MOD._dim_credibility(vec(reviews_parsed=1), AMZ),
                         UNAVAIL)


class TestEngagementLadder(Case):
    def test_amazon_no_engagement_is_the_floor(self):
        f = vec(helpful_pct=0, helpful_total=0, has_photos=0, has_response=0)
        self.assertEqual(MOD._dim_engagement(f, AMZ), 0)

    def test_amazon_full_engagement_is_the_ceiling(self):
        f = vec(helpful_pct=100, helpful_total=500, has_photos=1,
                has_response=1)
        self.assertEqual(MOD._dim_engagement(f, AMZ), 7)

    def test_NORMALISED_BY_WHAT_THE_PLATFORM_OFFERS(self):
        """Google Play has no photo feature and no seller replies. Scoring it
        on Amazon's eight-point scale would mark every app down for something
        Google does not do. Full marks on what Play DOES publish is 7."""
        f = vec(helpful_pct=100, helpful_total=500, has_photos=0,
                has_response=0)
        self.assertEqual(MOD._dim_engagement(f, GP), 7)
        self.assertLess(MOD._dim_engagement(f, AMZ), 7)

    def test_app_store_publishes_none_of_it(self):
        self.assertEqual(MOD._dim_engagement(vec(helpful_pct=UNAVAIL), AS_),
                         UNAVAIL)

    def test_monotone_in_helpful_share(self):
        prev = -1
        for h in (0, 25, 45, 65, 85, 100):
            f = vec(helpful_pct=h, helpful_total=0, has_photos=0,
                    has_response=0)
            got = MOD._dim_engagement(f, AMZ)
            self.assertGreaterEqual(got, prev, h)
            prev = got

    def test_photos_and_responses_add_on_amazon(self):
        bare = vec(has_photos=0, has_response=0)
        rich = vec(has_photos=1, has_response=1)
        self.assertGreater(MOD._dim_engagement(rich, AMZ),
                           MOD._dim_engagement(bare, AMZ))

    def test_unavailable_below_min_reviews(self):
        self.assertEqual(MOD._dim_engagement(vec(reviews_parsed=2), AMZ),
                         UNAVAIL)

    def test_always_in_range(self):
        for d in (AMZ, GP):
            for h in range(0, 101, 5):
                for p in (0, 1):
                    f = vec(helpful_pct=h, has_photos=p, has_response=p,
                            helpful_total=h * 3)
                    got = MOD._dim_engagement(f, d)
                    self.assertTrue(0 <= got <= 7, (d, h, p, got))


class TestEveryBucketLabelExists(Case):
    def test_eight_labels_per_dimension(self):
        for key in MOD.DIM_KEYS:
            self.assertEqual(len(MOD.BUCKETS[key]), 8, key)

    def test_every_ordinal_has_a_label(self):
        for key in MOD.DIM_KEYS:
            for i in range(8):
                self.assertIsInstance(MOD.BUCKETS[key][i], str)
                self.assertGreater(len(MOD.BUCKETS[key][i]), 2)

    def test_weights_sum_to_one_hundred(self):
        self.assertEqual(sum(MOD.DIM_WEIGHTS[k] for k in MOD.DIM_KEYS), 100)
        self.assertEqual(MOD.WEIGHT_TOTAL, 100)

    def test_the_brief_weights_are_what_shipped(self):
        self.assertEqual(MOD.DIM_WEIGHTS["timing_pattern"], 25)
        self.assertEqual(MOD.DIM_WEIGHTS["rating_distribution"], 20)
        self.assertEqual(MOD.DIM_WEIGHTS["review_quality"], 20)
        self.assertEqual(MOD.DIM_WEIGHTS["reviewer_credibility"], 20)
        self.assertEqual(MOD.DIM_WEIGHTS["engagement_signals"], 15)

    def test_every_dimension_has_a_flag_and_a_function(self):
        for key in MOD.DIM_KEYS:
            self.assertIn(key, MOD.DIM_FLAG)
            self.assertIn(key, MOD.DIM_FUNCS)
            for plat in MOD.PLATFORMS:
                self.assertIn(MOD.DIM_FLAG[key], MOD.PLATFORM_DIMS[plat])


# ---------------------------------------------------------------------------
# 6. Weak-handle detection
# ---------------------------------------------------------------------------

class TestWeakHandle(Case):
    def test_real_names_are_not_weak(self):
        for name in ("Jonathan Spencer", "Yehudah Schwartz", "Grace De Jesus",
                     "Dan R.", "Marcus Webb", "Priya S.", "Onahunch",
                     "ForeverYOUNG", "Hello Joseph", "Barb & Reid", "Isaac",
                     "Tango's product reviews", "Cutmeslack pennyless",
                     "Ed Bradway “Dad Warrior”"):
            self.assertFalse(MOD._weak_handle(name), name)

    def test_platform_placeholders_are_weak(self):
        for name in ("Amazon Customer", "amazon customer", "Anonymous",
                     "Kindle Customer", "A Google user", "Customer", "User",
                     "Verified Buyer"):
            self.assertTrue(MOD._weak_handle(name), name)

    def test_digit_heavy_handles_are_weak(self):
        for name in ("Mike2847", "user12345", "abc999", "Okie1010"):
            self.assertTrue(MOD._weak_handle(name), name)

    def test_repeated_syllables_are_weak(self):
        for name in ("Lol_hahahahahah", "bababababa", "xoxoxoxo"):
            self.assertTrue(MOD._weak_handle(name), name)

    def test_long_repeated_characters_are_weak(self):
        self.assertTrue(MOD._weak_handle("Jooooooe"))
        self.assertTrue(MOD._weak_handle("aaaa"))

    def test_consonant_heavy_single_tokens_are_weak(self):
        for name in ("Rubdujbj", "Ksjdhfgt", "Bcdfghjkl"):
            self.assertTrue(MOD._weak_handle(name), name)

    def test_very_short_is_weak(self):
        for name in ("", " ", "a", "ab", "  x "):
            self.assertTrue(MOD._weak_handle(name), repr(name))

    def test_two_digits_alone_are_not_enough(self):
        self.assertFalse(MOD._weak_handle("Anna B 42"))

    def test_never_raises(self):
        for name in ("", "éèê", "中文名", "!!!",
                     "x" * 500, "123", "\n\t"):
            MOD._weak_handle(name)


class TestTypeTokenRatio(Case):
    def test_short_text_is_not_measured(self):
        self.assertEqual(MOD._ttr("too short"), -1)
        self.assertEqual(MOD._ttr(""), -1)

    def test_identical_words_score_low(self):
        self.assertLess(MOD._ttr("same " * 40), 10)

    def test_varied_words_score_high(self):
        self.assertGreater(MOD._ttr(_varied_body(3, 80)), 30)

    def test_STANDARDISED_SO_LENGTH_DOES_NOT_DECIDE_IT(self):
        """A raw distinct/total ratio falls as text gets longer (Heaps' law),
        so an unstandardised measure would call a page of long, thoughtful
        reviews LESS varied than a page of three-line ones. The sample is
        capped at 100 words, so both are measured on the same footing."""
        short = _varied_body(11, 100)
        long_ = _varied_body(11, 1000)
        self.assertEqual(MOD._ttr(short), MOD._ttr(long_))

    def test_words_splits_on_punctuation(self):
        self.assertEqual(MOD._words("Hello, world! It's fine."),
                         ["hello", "world", "it", "s", "fine"])

    def test_words_is_case_insensitive(self):
        self.assertEqual(MOD._words("ABC abc"), ["abc", "abc"])

    def test_opening_is_the_first_six_words(self):
        self.assertEqual(MOD._opening("one two three four five six seven"),
                         "one two three four five six")

    def test_opening_of_short_text_is_the_whole_thing(self):
        self.assertEqual(MOD._opening("one two"), "one two")

    def test_identical_openings_collide(self):
        a = "Great product works exactly as described and more"
        b = "Great product works exactly as described but less"
        self.assertEqual(MOD._opening(a), MOD._opening(b))


# ---------------------------------------------------------------------------
# 7. The rubric DISCRIMINATES, and every band is reachable
#
# A detector that calls everything authentic is not a detector.
# ---------------------------------------------------------------------------

def score_amazon(text):
    p = MOD._parse_amazon(text, TODAY)
    f = MOD._features(p, P_AMAZON)
    return f, MOD._score(f, P_AMAZON)


class TestDiscrimination(Case):
    def test_a_bought_review_batch_is_MANIPULATED(self):
        """Ten five-star reviews, one date, one body, no verified purchases, no
        engagement, a 99% five-star histogram. If this is not caught, nothing
        is."""
        f, s = score_amazon(amazon_page(hist=(99, 1, 0, 0, 0),
                                        reviews=bought_reviews(10),
                                        avg="5.0", total="2,431"))
        self.assertEqual(s["trust_level"], MOD.T_MANIPULATED)
        self.assertLess(s["overall"], 40)
        for k in MOD.DIM_KEYS:
            self.assertLessEqual(s["scores"][k], 2, k)

    def test_an_organic_page_is_AUTHENTIC(self):
        f, s = score_amazon(amazon_page(hist=(62, 19, 9, 4, 6),
                                        reviews=organic_reviews(9),
                                        photos=True))
        self.assertEqual(s["trust_level"], MOD.T_AUTHENTIC)
        self.assertGreaterEqual(s["overall"], 70)

    def test_THE_REAL_ECHO_DOT_PAGE_IS_AUTHENTIC(self):
        """A million ratings, eight verified reviews spread over six years,
        with photos and helpful votes. Any rubric that calls this manipulated
        is broken."""
        f, s = score_amazon(fixture("amazon_echo_dot"))
        self.assertEqual(s["trust_level"], MOD.T_AUTHENTIC)
        self.assertGreaterEqual(s["overall"], 70)
        self.assertEqual(s["available_weight"], 100)

    def test_SUSPICIOUS_IS_REACHABLE(self):
        """A band that can never be hit is a bug. This one is the middle
        ground: real reviewers, but a suspicious rating shape, thin bodies and
        a tight window."""
        half = organic_reviews(8)
        for i, r in enumerate(half):
            if i >= 4:
                r["body"] = GENERIC_BODY
                r["helpful"] = None
            r["date"] = "January %d, 2026" % (i + 2)
        f, s = score_amazon(amazon_page(hist=(90, 6, 2, 1, 1), reviews=half))
        self.assertEqual(s["trust_level"], MOD.T_SUSPICIOUS, s)
        self.assertGreaterEqual(s["overall"], 40)
        self.assertLess(s["overall"], 70)

    def test_all_three_bands_are_reachable_from_real_page_shapes(self):
        seen = set()
        seen.add(score_amazon(amazon_page(hist=(99, 1, 0, 0, 0),
                 reviews=bought_reviews(10)))[1]["trust_level"])
        seen.add(score_amazon(amazon_page(hist=(62, 19, 9, 4, 6),
                 reviews=organic_reviews(9), photos=True))[1]["trust_level"])
        mid = organic_reviews(8)
        for i, r in enumerate(mid):
            if i >= 4:
                r["body"] = GENERIC_BODY
                r["helpful"] = None
            r["date"] = "January %d, 2026" % (i + 2)
        seen.add(score_amazon(amazon_page(hist=(90, 6, 2, 1, 1),
                 reviews=mid))[1]["trust_level"])
        self.assertEqual(seen, {MOD.T_AUTHENTIC, MOD.T_SUSPICIOUS,
                                MOD.T_MANIPULATED})

    def test_a_date_burst_alone_moves_the_score(self):
        spread = organic_reviews(9)
        burst = organic_reviews(9)
        for r in burst:
            r["date"] = "March 3, 2026"
        _f1, s1 = score_amazon(amazon_page(reviews=spread))
        _f2, s2 = score_amazon(amazon_page(reviews=burst))
        self.assertGreater(s1["overall"], s2["overall"])
        self.assertEqual(s2["scores"]["timing_pattern"], 0)

    def test_identical_bodies_alone_move_the_score(self):
        varied = organic_reviews(9)
        same = organic_reviews(9)
        for r in same:
            r["body"] = GENERIC_BODY
        _f1, s1 = score_amazon(amazon_page(reviews=varied))
        _f2, s2 = score_amazon(amazon_page(reviews=same))
        self.assertGreater(s1["scores"]["review_quality"],
                           s2["scores"]["review_quality"])

    def test_dropping_verified_purchase_alone_moves_the_score(self):
        ver = organic_reviews(9)
        unver = organic_reviews(9)
        for r in unver:
            r["verified"] = False
        _f1, s1 = score_amazon(amazon_page(reviews=ver))
        _f2, s2 = score_amazon(amazon_page(reviews=unver))
        self.assertGreater(s1["scores"]["reviewer_credibility"],
                           s2["scores"]["reviewer_credibility"])

    def test_overall_is_quantised_to_step_five(self):
        for reviews in (bought_reviews(10), organic_reviews(9),
                        organic_reviews(5), organic_reviews(12)):
            _f, s = score_amazon(amazon_page(reviews=reviews))
            self.assertEqual(s["overall"] % 5, 0, s["overall"])

    def test_overall_is_always_in_range(self):
        for hist in ((100, 0, 0, 0, 0), (62, 19, 9, 4, 6), (0, 0, 0, 0, 100)):
            for reviews in (bought_reviews(10), organic_reviews(9)):
                _f, s = score_amazon(amazon_page(hist=hist, reviews=reviews))
                self.assertTrue(0 <= s["overall"] <= 100)

    def test_trust_level_matches_the_thresholds(self):
        for reviews in (bought_reviews(10), organic_reviews(9),
                        organic_reviews(4)):
            for hist in ((99, 1, 0, 0, 0), (70, 15, 7, 3, 5)):
                _f, s = score_amazon(amazon_page(hist=hist, reviews=reviews))
                if s["trust_level"] == MOD.T_INCONCLUSIVE:
                    continue
                if s["overall"] >= MOD.AUTHENTIC_MIN:
                    self.assertEqual(s["trust_level"], MOD.T_AUTHENTIC)
                elif s["overall"] >= MOD.SUSPICIOUS_MIN:
                    self.assertEqual(s["trust_level"], MOD.T_SUSPICIOUS)
                else:
                    self.assertEqual(s["trust_level"], MOD.T_MANIPULATED)


# ---------------------------------------------------------------------------
# 8. RULE 7 — evidence that is not there is UNAVAILABLE, never zero
# ---------------------------------------------------------------------------

class TestConservatismOnUnavailableData(Case):
    def test_platform_availability_matches_the_probe(self):
        """docs/PROBE.md §3.4. Every flag here was measured against a live
        render, and the contract must not claim more than the probe found."""
        self.assertEqual(MOD.PLATFORM_DIMS[P_AMAZON]["rating"], True)
        self.assertEqual(MOD.PLATFORM_DIMS[P_GPLAY]["rating"], False)
        self.assertEqual(MOD.PLATFORM_DIMS[P_APPSTORE]["rating"], False)
        self.assertEqual(MOD.PLATFORM_DIMS[P_APPSTORE]["engagement"], False)
        self.assertEqual(MOD.PLATFORM_DIMS[P_GPLAY]["engagement"], True)

    def test_available_weight_per_platform(self):
        want = {P_AMAZON: 100, P_GPLAY: 80, P_APPSTORE: 65}
        for plat in MOD.PLATFORMS:
            d = MOD.PLATFORM_DIMS[plat]
            total = sum(MOD.DIM_WEIGHTS[k] for k in MOD.DIM_KEYS
                        if d[MOD.DIM_FLAG[k]])
            self.assertEqual(total, want[plat], plat)

    def test_every_platform_clears_the_inconclusive_floor(self):
        """A platform whose available weight is below the floor could never
        produce a score at all, and shipping it would be dishonest."""
        for plat in MOD.PLATFORMS:
            d = MOD.PLATFORM_DIMS[plat]
            total = sum(MOD.DIM_WEIGHTS[k] for k in MOD.DIM_KEYS
                        if d[MOD.DIM_FLAG[k]])
            self.assertGreaterEqual(total, MOD.MIN_AVAILABLE_WEIGHT, plat)

    def test_AN_UNAVAILABLE_DIMENSION_IS_NOT_A_ZERO(self):
        """The whole of rule 7. Google Play publishes no histogram; a product
        there must score exactly as it would if the dimension did not exist,
        not as though it had scored the worst possible mark."""
        f = vec(pct_5=UNAVAIL, pct_4=UNAVAIL, pct_3=UNAVAIL, pct_2=UNAVAIL,
                pct_1=UNAVAIL, verified_pct=UNAVAIL)
        as_zero = dict(f)
        as_zero.update({"pct_5": 0, "pct_4": 0, "pct_3": 0, "pct_2": 0,
                        "pct_1": 0})
        s_unavail = MOD._score(f, P_GPLAY)
        self.assertIsNot(s_unavail["scores"]["rating_distribution"], 0)
        self.assertEqual(s_unavail["scores"]["rating_distribution"], UNAVAIL)
        self.assertEqual(s_unavail["available_weight"], 80)

    def test_an_unavailable_dimension_earns_no_points_either(self):
        """The other direction, and just as important. If unavailable counted
        as full marks, a platform that published nothing would look perfect."""
        all_seven = vec()
        gp = MOD._score(all_seven, P_GPLAY)
        amz = MOD._score(all_seven, P_AMAZON)
        self.assertEqual(gp["available_weight"], 80)
        self.assertEqual(amz["available_weight"], 100)
        self.assertLessEqual(gp["overall"], 100)

    def test_TOO_FEW_REVIEWS_IS_INCONCLUSIVE(self):
        for n in (0, 1, 2):
            f = vec(reviews_parsed=n, dated_reviews=n, distinct_days=n,
                    max_same_day=min(n, 1))
            s = MOD._score(f, P_AMAZON)
            self.assertEqual(s["trust_level"], MOD.T_INCONCLUSIVE, n)
            self.assertEqual(s["overall"], 0)
            self.assertIn("review", s["why"])

    def test_min_reviews_is_the_boundary(self):
        f = vec(reviews_parsed=MOD.MIN_REVIEWS, dated_reviews=MOD.MIN_REVIEWS,
                distinct_days=MOD.MIN_REVIEWS, max_same_day=1)
        self.assertNotEqual(MOD._score(f, P_AMAZON)["trust_level"],
                            MOD.T_INCONCLUSIVE)

    def test_too_little_weight_is_INCONCLUSIVE(self):
        """An App Store page whose dates would not parse loses timing on top of
        the two dimensions the platform never publishes — 40 of 100, below the
        floor. It reports INCONCLUSIVE rather than guessing from what is
        left."""
        f = vec(dated_reviews=0, pct_5=UNAVAIL, pct_4=UNAVAIL, pct_3=UNAVAIL,
                pct_2=UNAVAIL, pct_1=UNAVAIL, verified_pct=UNAVAIL,
                helpful_pct=UNAVAIL, helpful_total=UNAVAIL)
        s = MOD._score(f, P_APPSTORE)
        self.assertEqual(s["available_weight"], 40)
        self.assertEqual(s["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertIn("rubric points", s["why"])

    def test_INCONCLUSIVE_IS_NOT_A_LOW_SCORE(self):
        """It reports zero because there is nothing to report, and the trust
        level is the field that says which of the two it is. The consumer
        contract refuses INCONCLUSIVE by NAME rather than by score for exactly
        this reason."""
        s = MOD._score(vec(reviews_parsed=1), P_AMAZON)
        self.assertEqual(s["overall"], 0)
        self.assertEqual(s["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertNotEqual(s["trust_level"], MOD.T_MANIPULATED)

    def test_inconclusive_always_explains_itself(self):
        for f in (vec(reviews_parsed=0), vec(reviews_parsed=2),
                  vec(dated_reviews=0, pct_5=UNAVAIL, pct_4=UNAVAIL,
                      pct_3=UNAVAIL, pct_2=UNAVAIL, pct_1=UNAVAIL,
                      verified_pct=UNAVAIL, helpful_pct=UNAVAIL,
                      helpful_total=UNAVAIL)):
            s = MOD._score(f, P_APPSTORE)
            if s["trust_level"] == MOD.T_INCONCLUSIVE:
                self.assertNotEqual(s["why"], "")

    def test_a_scored_check_carries_no_why(self):
        _f, s = score_amazon(amazon_page(reviews=organic_reviews(9)))
        self.assertEqual(s["why"], "")

    def test_pack_is_the_only_writer_of_the_sentinel(self):
        self.assertEqual(MOD._pack(5, False, 1), UNAVAIL)
        self.assertEqual(MOD._pack(5, True, 1), 5)
        self.assertEqual(MOD._pack(7, True, 5), 5)

    def test_avail_is_the_only_reader_of_the_sentinel(self):
        self.assertFalse(MOD._avail(UNAVAIL))
        self.assertTrue(MOD._avail(0))
        self.assertTrue(MOD._avail(100))

    def test_nullable_fields_are_exactly_the_ones_platforms_may_omit(self):
        for key in MOD.NULLABLE:
            self.assertIn(key, MOD.FEATURE_RANGE, key)
        for plat in MOD.PLATFORMS:
            page = {"amazon_echo_dot": (MOD._parse_amazon, P_AMAZON),
                    "gplay_whatsapp": (MOD._parse_gplay, P_GPLAY),
                    "appstore_whatsapp": (MOD._parse_appstore, P_APPSTORE)}
            for name, (fn, p) in page.items():
                if p != plat:
                    continue
                f = MOD._features(fn(fixture(name), TODAY), plat)
                for key, val in f.items():
                    if val == UNAVAIL:
                        self.assertIn(key, MOD.NULLABLE,
                                      "%s emitted UNAVAIL for %s, which is "
                                      "not declared nullable" % (plat, key))


# ---------------------------------------------------------------------------
# 9. The feature vector and the content hash
# ---------------------------------------------------------------------------

class TestFeatureVector(Case):
    def test_every_declared_field_is_produced(self):
        for name, fn, plat in (("amazon_echo_dot", MOD._parse_amazon, P_AMAZON),
                               ("gplay_whatsapp", MOD._parse_gplay, P_GPLAY),
                               ("appstore_whatsapp", MOD._parse_appstore,
                                P_APPSTORE)):
            f = MOD._features(fn(fixture(name), TODAY), plat)
            self.assertEqual(set(f.keys()), set(MOD.FEATURE_RANGE.keys()),
                             plat)

    def test_every_value_is_an_int_and_never_a_bool(self):
        f = MOD._features(MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY),
                          P_AMAZON)
        for key, val in f.items():
            self.assertIsInstance(val, int, key)
            self.assertNotIsInstance(val, bool, key)

    def test_every_value_is_in_range_or_the_sentinel(self):
        for name, fn, plat in (("amazon_echo_dot", MOD._parse_amazon, P_AMAZON),
                               ("gplay_whatsapp", MOD._parse_gplay, P_GPLAY),
                               ("appstore_whatsapp", MOD._parse_appstore,
                                P_APPSTORE)):
            f = MOD._features(fn(fixture(name), TODAY), plat)
            for key, val in f.items():
                lo, hi = MOD.FEATURE_RANGE[key]
                if val == UNAVAIL:
                    self.assertIn(key, MOD.NULLABLE, key)
                else:
                    self.assertTrue(lo <= val <= hi, (plat, key, val))

    def test_percentages_are_quantised_to_five(self):
        f = MOD._features(MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY),
                          P_AMAZON)
        for key in ("short_pct", "dup_open_pct", "lexical_pct",
                    "distinct_names_pct", "weak_handle_pct"):
            self.assertEqual(f[key] % 5, 0, key)

    def test_counts_are_three_significant_figures(self):
        f = MOD._features(MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY),
                          P_AMAZON)
        self.assertEqual(f["total_ratings"], MOD._sig3(1037930))

    def test_features_of_an_empty_page_are_all_zero_or_unavailable(self):
        f = MOD._features({"reviews": [], "pct": [UNAVAIL] * 5,
                           "avg_rating_x10": UNAVAIL,
                           "total_ratings": UNAVAIL, "has_photos": False,
                           "has_response": False, "title": ""}, P_AMAZON)
        self.assertEqual(f["reviews_parsed"], 0)
        self.assertEqual(f["median_chars"], 0)

    def test_features_never_raise_on_a_malformed_parse(self):
        for bad in ({"reviews": []}, {}, {"reviews": [{}]},
                    {"reviews": [{"body": None, "name": None, "day": None,
                                  "helpful": None, "verified": None}]}):
            for plat in MOD.PLATFORMS:
                MOD._features(bad, plat)


class TestContentHash(Case):
    def setUp(self):
        super().setUp()
        self.ident = {"url_key": AMAZON_KEY, "platform": P_AMAZON,
                      "title": "Echo Dot"}
        self.f = vec()

    def test_deterministic(self):
        a = MOD._digest(self.ident, self.f)
        b = MOD._digest(dict(self.ident), dict(self.f))
        self.assertEqual(a, b)

    def test_key_order_does_not_matter(self):
        shuffled = {}
        for k in reversed(list(self.f.keys())):
            shuffled[k] = self.f[k]
        self.assertEqual(MOD._digest(self.ident, self.f),
                         MOD._digest(self.ident, shuffled))

    def test_every_vector_field_changes_the_hash(self):
        base = MOD._digest(self.ident, self.f)
        for key in MOD.FEATURE_RANGE:
            moved = dict(self.f)
            moved[key] = (moved[key] + 1) if moved[key] != UNAVAIL else 0
            self.assertNotEqual(MOD._digest(self.ident, moved), base, key)

    def test_EVERY_IDENTITY_FIELD_CHANGES_THE_HASH(self):
        """The identity strings are IN the hash, not beside it. A hash over the
        vector alone would be identical for two different products that scored
        the same, so it could not tell a check of one listing from a check of a
        clone wearing its numbers."""
        base = MOD._digest(self.ident, self.f)
        for key in MOD.IDENTITY_KEYS:
            moved = dict(self.ident)
            moved[key] = str(moved.get(key, "")) + "x"
            self.assertNotEqual(MOD._digest(moved, self.f), base, key)

    def test_the_sentinel_hashes_differently_from_zero(self):
        a = dict(self.f); a["verified_pct"] = UNAVAIL
        b = dict(self.f); b["verified_pct"] = 0
        self.assertNotEqual(MOD._digest(self.ident, a),
                            MOD._digest(self.ident, b))

    def test_canon_covers_exactly_the_declared_fields(self):
        blob = json.loads(MOD._canon(self.f))
        self.assertEqual(set(blob.keys()), set(MOD.FEATURE_RANGE.keys()))

    def test_fnv_is_length_prefixed(self):
        h = MOD._fnv("abc")
        self.assertTrue(h.startswith("3:"))
        self.assertEqual(len(h.split(":")[1]), 16)


# ---------------------------------------------------------------------------
# 10. The consensus gates — tested by BUILDING FORGERIES
# ---------------------------------------------------------------------------

def honest(name="amazon_echo_dot", plat=P_AMAZON):
    fn = {P_AMAZON: MOD._parse_amazon, P_GPLAY: MOD._parse_gplay,
          P_APPSTORE: MOD._parse_appstore}[plat]
    parsed = fn(fixture(name), TODAY)
    feats = MOD._features(parsed, plat)
    scored = MOD._score(feats, plat)
    out = {"ok": True, "url_key": AMAZON_KEY, "platform": plat,
           "title": parsed["title"][:MOD.MAX_TITLE], "features": feats,
           "scores": scored["scores"], "overall": scored["overall"],
           "trust_level": scored["trust_level"],
           "available_weight": scored["available_weight"],
           "credibility_basis": scored["credibility_basis"],
           "why": scored["why"]}
    out["content_hash"] = MOD._digest(out, feats)
    return out


def reseal(out):
    out["content_hash"] = MOD._digest(out, out["features"])
    return out


class TestCoherence(Case):
    def test_an_honest_result_is_coherent(self):
        self.assertTrue(MOD._coherent(honest()))

    def test_every_platform_produces_a_coherent_result(self):
        for name, plat in (("amazon_echo_dot", P_AMAZON),
                           ("gplay_whatsapp", P_GPLAY),
                           ("appstore_whatsapp", P_APPSTORE)):
            self.assertTrue(MOD._coherent(honest(name, plat)), plat)

    def test_A_FORGED_OVERALL_IS_REFUSED(self):
        """The headline attack. A leader that reports the honest vector and a
        better overall must be voted down by every validator BEFORE any of them
        re-fetches anything."""
        out = honest()
        out["overall"] = 100
        self.assertFalse(MOD._coherent(out))

    def test_a_forged_trust_level_is_refused(self):
        out = honest()
        out["trust_level"] = MOD.T_AUTHENTIC if \
            out["trust_level"] != MOD.T_AUTHENTIC else MOD.T_MANIPULATED
        self.assertFalse(MOD._coherent(out))

    def test_a_forged_dimension_is_refused(self):
        for key in MOD.DIM_KEYS:
            out = honest()
            cur = out["scores"][key]
            out["scores"][key] = 7 if cur != 7 else 0
            self.assertFalse(MOD._coherent(out), key)

    def test_a_forged_available_weight_is_refused(self):
        out = honest()
        out["available_weight"] = 100 if out["available_weight"] != 100 else 65
        self.assertFalse(MOD._coherent(out))

    def test_a_forged_credibility_basis_is_refused(self):
        out = honest()
        out["credibility_basis"] = "made-up"
        self.assertFalse(MOD._coherent(out))

    def test_a_forged_content_hash_is_refused(self):
        out = honest()
        out["content_hash"] = "0:" + "0" * 16
        self.assertFalse(MOD._coherent(out))

    def test_a_RESEALED_forgery_is_still_refused(self):
        """The sophisticated version: change a number AND recompute the hash so
        the two agree with each other. It still dies, because `_coherent` runs
        the rubric itself rather than trusting the pair."""
        out = honest()
        out["overall"] = 100
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_a_vector_field_out_of_range_is_refused(self):
        for key, (lo, hi) in MOD.FEATURE_RANGE.items():
            out = honest()
            out["features"][key] = hi + 1
            self.assertFalse(MOD._coherent(reseal(out)), key)
            out2 = honest()
            out2["features"][key] = -1
            self.assertFalse(MOD._coherent(reseal(out2)), key)

    def test_a_missing_vector_field_is_refused(self):
        for key in MOD.FEATURE_RANGE:
            out = honest()
            del out["features"][key]
            self.assertFalse(MOD._coherent(reseal(out)), key)

    def test_an_extra_vector_field_is_refused(self):
        out = honest()
        out["features"]["smuggled"] = 1
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_a_BOOL_in_a_vector_field_is_refused(self):
        """`bool` is an `int` in Python, so a `True` would otherwise score as 1
        rather than being caught as the wrong type."""
        out = honest()
        out["features"]["has_photos"] = True
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_a_string_in_a_vector_field_is_refused(self):
        out = honest()
        out["features"]["reviews_parsed"] = "8"
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_the_sentinel_is_refused_where_it_is_not_allowed(self):
        for key in MOD.FEATURE_RANGE:
            if key in MOD.NULLABLE:
                continue
            out = honest()
            out["features"][key] = UNAVAIL
            self.assertFalse(MOD._coherent(reseal(out)), key)

    def test_an_impossible_count_is_refused(self):
        for key in ("dated_reviews", "distinct_days", "max_same_day"):
            out = honest()
            out["features"][key] = out["features"]["reviews_parsed"] + 1
            self.assertFalse(MOD._coherent(reseal(out)), key)

    def test_more_distinct_days_than_dated_reviews_is_refused(self):
        out = honest()
        out["features"]["dated_reviews"] = 4
        out["features"]["distinct_days"] = 5
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_a_histogram_that_is_not_one_is_refused(self):
        out = honest()
        out["features"]["pct_5"] = 100
        out["features"]["pct_4"] = 100
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_a_partially_available_histogram_is_refused(self):
        out = honest()
        out["features"]["pct_3"] = UNAVAIL
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_an_unknown_platform_is_refused(self):
        out = honest()
        out["platform"] = "YELP"
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_a_missing_identity_string_is_refused(self):
        for key in MOD.IDENTITY_KEYS:
            out = honest()
            out[key] = 42
            self.assertFalse(MOD._coherent(reseal(out)), key)

    def test_an_empty_url_key_is_refused(self):
        out = honest()
        out["url_key"] = ""
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_an_over_long_title_is_refused(self):
        out = honest()
        out["title"] = "x" * (MOD.MAX_TITLE + 1)
        self.assertFalse(MOD._coherent(reseal(out)))

    def test_garbage_shapes_are_refused(self):
        for bad in (None, [], "x", 42, {}, {"features": None},
                    {"features": []}, {"features": {}}):
            self.assertFalse(MOD._coherent(bad), repr(bad))


class TestAgreement(Case):
    def test_two_identical_runs_agree(self):
        self.assertTrue(MOD._agrees(honest(), honest()))

    def test_EVERY_VECTOR_FIELD_IS_ON_THE_AXIS(self):
        """RULE 1. A field the validators do not compare is a field the leader
        can forge. This moves each one in turn and demands a disagreement."""
        for key in MOD.FEATURE_RANGE:
            a = honest()
            b = honest()
            b["features"][key] = (b["features"][key] + 1) \
                if b["features"][key] != UNAVAIL else 0
            reseal(b)
            self.assertFalse(MOD._agrees(a, b), key)

    def test_every_identity_string_is_on_the_axis(self):
        for key in MOD.IDENTITY_KEYS:
            a = honest()
            b = honest()
            b[key] = str(b.get(key, "")) + "-different"
            reseal(b)
            self.assertFalse(MOD._agrees(a, b), key)

    def test_the_content_hash_is_on_the_axis(self):
        a = honest()
        b = honest()
        b["content_hash"] = "9:" + "f" * 16
        self.assertFalse(MOD._agrees(a, b))

    def test_an_empty_hash_never_agrees(self):
        a = honest(); a["content_hash"] = ""
        b = honest(); b["content_hash"] = ""
        self.assertFalse(MOD._agrees(a, b))

    def test_THERE_IS_NO_TOLERANCE_IN_AGREES(self):
        """The tolerance lives in the quantisers and nowhere else. A comparison
        with slack in it would mean two different accepted outputs for one
        request — and then which one is the check?"""
        a = honest()
        b = honest()
        b["features"]["median_chars"] += 1
        reseal(b)
        self.assertFalse(MOD._agrees(a, b))

    def test_a_small_live_drift_still_agrees_after_quantisation(self):
        """The other half of the same property. A global-ratings figure that
        ticks by one between two renders must NOT break consensus."""
        p1 = MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY)
        p2 = MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY)
        p2["total_ratings"] = p2["total_ratings"] + 7
        f1 = MOD._features(p1, P_AMAZON)
        f2 = MOD._features(p2, P_AMAZON)
        self.assertEqual(f1["total_ratings"], f2["total_ratings"])

    def test_a_real_move_correctly_breaks_agreement(self):
        p1 = MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY)
        p2 = MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY)
        p2["pct"] = [99, 1, 0, 0, 0]
        f1 = MOD._features(p1, P_AMAZON)
        f2 = MOD._features(p2, P_AMAZON)
        self.assertNotEqual(f1["pct_5"], f2["pct_5"])

    def test_garbage_never_agrees(self):
        good = honest()
        for bad in (None, [], "x", 42, {}, {"features": None}):
            self.assertFalse(MOD._agrees(good, bad), repr(bad))
            self.assertFalse(MOD._agrees(bad, good), repr(bad))


class TestCollect(Case):
    def test_collect_produces_a_coherent_result(self):
        for url, plat, key in ((AMAZON_URL, P_AMAZON, AMAZON_KEY),
                               (GPLAY_FETCH, P_GPLAY, GPLAY_KEY),
                               (APPSTORE_FETCH, P_APPSTORE, APPSTORE_KEY)):
            out = MOD._collect(key, url, plat, TODAY)
            self.assertTrue(out["ok"], plat)
            self.assertTrue(MOD._coherent(out), plat)

    def test_collect_is_deterministic(self):
        a = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
        b = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
        self.assertTrue(MOD._agrees(a, b))
        self.assertEqual(a["content_hash"], b["content_hash"])

    def test_A_FETCH_FAILURE_IS_RETRY_NOT_A_LOW_SCORE(self):
        """Settling low on a fetch that never happened would let a competitor
        manufacture a MANIPULATED verdict by making a page briefly
        unreachable."""
        H.PAGE_MAP[AMAZON_URL] = RuntimeError("WEBPAGE_LOAD_FAILED")
        out = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
        self.assertFalse(out["ok"])
        self.assertTrue(out["retry"])
        self.assertNotIn("trust_level", out)

    def test_a_bot_wall_is_retry_not_a_verdict(self):
        for wall in ("Robot or human?\nActivate and hold the button" + "x" * 300,
                     "Are you a human?\nPlease don't take this personally" + "y" * 300,
                     "Verifying Connection" + "z" * 300):
            H.PAGE_MAP[AMAZON_URL] = wall
            out = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
            self.assertFalse(out["ok"], wall[:20])
            self.assertTrue(out["retry"], wall[:20])

    def test_an_almost_empty_page_is_retry(self):
        H.PAGE_MAP[AMAZON_URL] = "short"
        out = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
        self.assertFalse(out["ok"])
        self.assertTrue(out["retry"])

    def test_a_dead_asin_is_a_permanent_failure_not_a_retry(self):
        H.PAGE_MAP[AMAZON_URL] = ("Page Not Found\nWe're sorry. The Web "
                                  "address you entered is not a functioning "
                                  "page on our site." + " padding" * 40)
        out = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("fail"))
        self.assertFalse(out.get("retry"))

    def test_a_readable_page_with_no_reviews_is_INCONCLUSIVE_not_manipulated(self):
        H.PAGE_MAP[AMAZON_URL] = amazon_page(reviews=()) + "\npadding" * 60
        out = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
        self.assertTrue(out["ok"])
        self.assertEqual(out["trust_level"], MOD.T_INCONCLUSIVE)

    def test_collect_refuses_an_unknown_platform(self):
        out = MOD._collect("X:y", AMAZON_URL, "YELP", TODAY)
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("fail"))


# ---------------------------------------------------------------------------
# 11. The stateful contract, driven end to end with consensus wired up
# ---------------------------------------------------------------------------

class TestCheckHappyPath(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def test_amazon_check_writes_a_record(self):
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["check_id"], 1)
        self.assertEqual(r["url_key"], AMAZON_KEY)
        self.assertEqual(r["platform"], P_AMAZON)
        self.assertEqual(r["trust_level"], MOD.T_AUTHENTIC)
        self.assertEqual(r["available_weight"], 100)

    def test_THE_VALIDATOR_ACTUALLY_RE_FETCHED(self):
        """The stub runs the real validator closure against the leader's
        result. Two renders of the same URL in one check means the validator
        did its own fetch rather than trusting the leader's numbers."""
        H.RENDER_LOG.clear()
        self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(H.RENDER_LOG.count(AMAZON_URL), 2)
        self.assertTrue(H.LAST_CONSENSUS["agreed"])

    def test_all_three_platforms_check(self):
        self.assertEqual(self.c.check_reviews(AMAZON_URL, "")["status"], "OK")
        as_sender(BOB)
        self.assertEqual(self.c.check_reviews(GPLAY_URL, "")["status"], "OK")
        as_sender(CAROL)
        self.assertEqual(self.c.check_reviews(APPSTORE_URL, "")["status"], "OK")
        self.assertEqual(self.c.get_stats()["total_checked"], 3)

    def test_a_declared_platform_that_matches_is_accepted(self):
        r = self.c.check_reviews(AMAZON_URL, "AMAZON")
        self.assertEqual(r["status"], "OK")

    def test_A_DECLARED_PLATFORM_THAT_LIES_IS_REFUSED(self):
        """A caller who could declare a platform that disagreed with the host
        would choose which parser ran against somebody else's page."""
        r = self.c.check_reviews(AMAZON_URL, "GOOGLE_PLAY")
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("AMAZON", r["reason"])

    def test_the_record_reads_back_whole(self):
        self.c.check_reviews(AMAZON_URL, "")
        rec = self.c.get_check(1)
        self.assertTrue(rec["found"])
        self.assertEqual(rec["url_key"], AMAZON_KEY)
        self.assertEqual(rec["source_url"],
                         "https://www.amazon.com/dp/B07FZ8S74R")
        self.assertEqual(rec["evidence"]["reviews_parsed"], 8)
        self.assertEqual(rec["evidence"]["rating_histogram"]["5"], 83)
        self.assertEqual(rec["credibility_basis"], "verified-purchase")
        for key in MOD.DIM_KEYS:
            self.assertIn(key, rec["scores"])
            self.assertIn(key, rec["labels"])

    def test_UNAVAILABLE_CROSSES_THE_API_AS_NULL_NOT_255(self):
        """A reader who saw a bare 255 in `pct_5` would have to know this
        contract's sentinel to avoid rendering a product as 255% five-star."""
        as_sender(BOB)
        self.c.check_reviews(GPLAY_URL, "")
        rec = self.c.get_check_by_url(GPLAY_URL)
        self.assertIsNone(rec["evidence"]["rating_histogram"]["5"])
        self.assertIsNone(rec["evidence"]["verified_pct"])
        self.assertIsNone(rec["scores"]["rating_distribution"])
        blob = json.dumps(rec)
        self.assertNotIn("255", blob.split('"content_hash"')[0])

    def test_an_unavailable_dimension_is_labelled_as_such(self):
        as_sender(BOB)
        self.c.check_reviews(APPSTORE_URL, "")
        rec = self.c.get_check_by_url(APPSTORE_URL)
        self.assertEqual(rec["labels"]["rating_distribution"],
                         "not published by this platform")
        self.assertEqual(rec["labels"]["engagement_signals"],
                         "not published by this platform")

    def test_get_check_by_url_accepts_any_url_shape(self):
        self.c.check_reviews(AMAZON_URL, "")
        for shape in (AMAZON_URL, "amazon.com/dp/b07fz8s74r",
                      "https://www.amazon.com/Echo/dp/B07FZ8S74R/ref=x",
                      "https://smile.amazon.com/gp/product/B07FZ8S74R"):
            self.assertTrue(self.c.get_check_by_url(shape)["found"], shape)

    def test_verify_recomputes_clean(self):
        self.c.check_reviews(AMAZON_URL, "")
        v = self.c.verify_check(1)
        self.assertTrue(v["verified"])
        self.assertEqual(v["mismatches"], [])
        self.assertEqual(v["recomputed"]["overall"], self.c.get_check(1)["overall"])

    def test_verify_on_every_platform(self):
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(BOB)
        self.c.check_reviews(GPLAY_URL, "")
        as_sender(CAROL)
        self.c.check_reviews(APPSTORE_URL, "")
        for cid in (1, 2, 3):
            self.assertTrue(self.c.verify_check(cid)["verified"], cid)

    def test_verify_of_an_unknown_id(self):
        v = self.c.verify_check(999)
        self.assertFalse(v["verified"])
        self.assertIn("no check", v["reason"])

    def test_recent_and_platform_listings(self):
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(BOB)
        self.c.check_reviews(GPLAY_URL, "")
        rec = self.c.get_recent_checks(10)
        self.assertEqual(rec["count"], 2)
        self.assertEqual(rec["items"][0]["check_id"], 2)
        amz = self.c.get_checks_by_platform("AMAZON")
        self.assertEqual(amz["count"], 1)
        self.assertEqual(amz["items"][0]["url_key"], AMAZON_KEY)
        self.assertEqual(self.c.get_checks_by_platform("YELP")["count"], 0)

    def test_stats_track_the_bands(self):
        self.c.check_reviews(AMAZON_URL, "")
        s = self.c.get_stats()
        self.assertEqual(s["total_checked"], 1)
        self.assertEqual(s["authentic"], 1)
        self.assertEqual(s["pages_tracked"], 1)
        self.assertEqual(s["pages_by_platform"]["AMAZON"], 1)

    def test_MANIPULATION_RATE_EXCLUDES_INCONCLUSIVE(self):
        """Counting a page nobody could read as 'not manipulated' would make
        the headline number improve every time the oracle failed."""
        H.PAGE_MAP[AMAZON_URL] = amazon_page(
            hist=(99, 1, 0, 0, 0), reviews=bought_reviews(10))
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(BOB)
        H.PAGE_MAP[GPLAY_FETCH] = ("Ratings and reviews\n4.9\n" + "pad\n" * 100)
        self.c.check_reviews(GPLAY_URL, "")
        s = self.c.get_stats()
        self.assertEqual(s["manipulated"], 1)
        self.assertEqual(s["inconclusive"], 1)
        self.assertEqual(s["conclusive_checks"], 1)
        self.assertEqual(s["manipulation_rate_pct"], 100)

    def test_config_is_self_describing(self):
        cfg = self.c.get_config()
        self.assertEqual(cfg["rubric_version"], MOD.RUBRIC_VERSION)
        self.assertEqual(set(cfg["platforms"].keys()), set(MOD.PLATFORMS))
        self.assertEqual(cfg["platforms"][P_AMAZON]["available_weight"], 100)
        self.assertEqual(cfg["platforms"][P_GPLAY]["available_weight"], 80)
        self.assertEqual(cfg["platforms"][P_APPSTORE]["available_weight"], 65)
        self.assertIn("TRUSTPILOT", cfg["unsupported"])
        self.assertIn("YELP", cfg["unsupported"])
        self.assertIn("GOOGLE_MAPS", cfg["unsupported"])
        self.assertEqual(cfg["thresholds"]["authentic_min"], 70)
        self.assertEqual(cfg["thresholds"]["suspicious_min"], 40)

    def test_detect_platform_view_matches_the_write_path(self):
        d = self.c.detect_platform(
            "https://www.amazon.com/Echo/dp/B07FZ8S74R/ref=x")
        self.assertTrue(d["supported"])
        self.assertEqual(d["url_key"], AMAZON_KEY)
        self.assertFalse(d["already_checked"])
        self.c.check_reviews(AMAZON_URL, "")
        self.assertTrue(self.c.detect_platform(AMAZON_URL)["already_checked"])

    def test_detect_platform_names_the_blocked_sites(self):
        d = self.c.detect_platform("https://www.trustpilot.com/review/x.com")
        self.assertFalse(d["supported"])
        self.assertEqual(d["platform"], "")


class TestRefusalsRefundAndNeverRevert(Case):
    """RULE 2. A payable method that raises rolls back storage but NOT the
    incoming value, which then sits in the contract with no record saying whose
    it was."""

    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def _refused(self, *args, **kw):
        as_sender(ALICE, value=GEN)
        r = self.c.check_reviews(*args, **kw)
        self.assertEqual(r["status"], "REJECTED", r)
        self.assertEqual(r["refunded_wei"], str(GEN))
        self.assertEqual(int(self.c.get_refund_owed(ALICE)["owed_wei"]), GEN)
        return r

    def test_an_unsupported_host_refunds(self):
        r = self._refused("https://www.trustpilot.com/review/amazon.com", "")
        self.assertIn("not one ReviewGuard can read", r["reason"])

    def test_the_refusal_names_the_measured_blockers(self):
        r = self._refused("https://www.yelp.com/biz/x", "")
        self.assertIn("Trustpilot", r["reason"])
        self.assertIn("Yelp", r["reason"])

    def test_an_empty_url_refunds(self):
        self._refused("", "")

    def test_a_malformed_amazon_url_refunds(self):
        self._refused("https://www.amazon.com/s?k=echo", "")

    def test_a_mismatched_platform_refunds(self):
        self._refused(AMAZON_URL, "APP_STORE")

    def test_a_paused_contract_refunds(self):
        as_sender(OWNER)
        self.c.set_paused(True)
        self._refused(AMAZON_URL, "")

    def test_an_underpayment_refunds(self):
        as_sender(OWNER)
        self.c.set_fee(10 ** 15)
        as_sender(ALICE, value=1)
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(int(self.c.get_refund_owed(ALICE)["owed_wei"]), 1)

    def test_a_rate_limited_caller_refunds(self):
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(ALICE, value=GEN)
        r = self.c.check_reviews(GPLAY_URL, "")
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("rate limited", r["reason"])
        self.assertEqual(int(self.c.get_refund_owed(ALICE)["owed_wei"]), GEN)

    def test_a_cooled_down_url_refunds(self):
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(BOB, value=GEN)
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("checked", r["reason"])
        self.assertEqual(r["check_id"], 1)

    def test_a_transient_fetch_failure_refunds(self):
        H.PAGE_MAP[AMAZON_URL] = RuntimeError("WEBPAGE_LOAD_FAILED")
        r = self._refused(AMAZON_URL, "")
        self.assertTrue(r["transient"])
        self.assertIn("TRANSIENT", r["reason"])

    def test_a_dead_asin_refunds(self):
        H.PAGE_MAP[AMAZON_URL] = ("Page Not Found\nWe're sorry."
                                  + " padding" * 40)
        r = self._refused(AMAZON_URL, "")
        self.assertIn("EXTERNAL", r["reason"])

    def test_EVERY_REFUSAL_PATH_IS_CLAIMABLE(self):
        """The refund is worthless if it cannot be collected. This walks the
        whole cycle: refuse, credit, claim, and check the wei actually moved."""
        self._refused("https://www.yelp.com/biz/x", "")
        as_sender(ALICE, value=0)
        out = self.c.claim_refund()
        self.assertEqual(out["status"], "OK")
        self.assertEqual(out["paid_wei"], str(GEN))
        self.assertEqual(H.TRANSFERS, [(str(ALICE), GEN)])
        self.assertEqual(int(self.c.get_refund_owed(ALICE)["owed_wei"]), 0)

    def test_claiming_twice_pays_once(self):
        self._refused("", "")
        as_sender(ALICE, value=0)
        self.c.claim_refund()
        second = self.c.claim_refund()
        self.assertEqual(second["status"], "NOOP")
        self.assertEqual(len(H.TRANSFERS), 1)

    def test_overpayment_is_credited_not_kept(self):
        as_sender(OWNER)
        self.c.set_fee(1000)
        as_sender(ALICE, value=5000)
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["refunded_wei"], "4000")
        self.assertEqual(int(self.c.get_refund_owed(ALICE)["owed_wei"]), 4000)

    def test_CHECK_REVIEWS_NEVER_RAISES(self):
        """Swept across every refusal shape at once."""
        bad = ["", "   ", "nope", "https://evil.test/x",
               "https://www.amazon.com/", "https://www.amazon.com/dp/SHORT",
               "https://play.google.com/store/apps/details",
               "https://apps.apple.com/us/app/thing",
               "https://www.trustpilot.com/review/x", "x" * 400,
               "https://amazon.com.evil.test/dp/B07FZ8S74R"]
        for i, url in enumerate(bad):
            as_sender(H._Addr("0x" + format(i + 16, "040x")), value=7)
            try:
                r = self.c.check_reviews(url, "")
            except Exception as e:
                self.fail("check_reviews raised on %r: %s" % (url, e))
            self.assertEqual(r["status"], "REJECTED", url)
            self.assertEqual(r["refunded_wei"], "7", url)


# ---------------------------------------------------------------------------
# 12. RULE 3 — no counter moves before a path that can still refuse
# ---------------------------------------------------------------------------

class TestNoCounterMovesBeforeARefusal(Case):
    COUNTERS = ("total_requests", "total_checked", "total_fees_wei",
                "count_authentic", "count_suspicious", "count_manipulated",
                "count_inconclusive")

    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def _snap(self):
        s = {k: int(getattr(self.c, k)) for k in self.COUNTERS}
        s["next_id"] = int(self.c.next_id)
        s["pages"] = len(self.c.url_keys)
        return s

    def _expect_frozen(self, url, platform="", value=0, sender=ALICE,
                       allow=()):
        before = self._snap()
        as_sender(sender, value=value)
        r = self.c.check_reviews(url, platform)
        self.assertEqual(r["status"], "REJECTED", r)
        after = self._snap()
        for key in before:
            if key in allow:
                continue
            self.assertEqual(before[key], after[key],
                             "%s moved on a refusal (%s)" % (key, r["reason"]))

    def test_a_bad_host_moves_nothing(self):
        self._expect_frozen("https://www.yelp.com/biz/x")

    def test_an_empty_url_moves_nothing(self):
        self._expect_frozen("")

    def test_a_malformed_url_moves_nothing(self):
        self._expect_frozen("https://www.amazon.com/s?k=x")

    def test_a_platform_mismatch_moves_nothing(self):
        self._expect_frozen(AMAZON_URL, "GOOGLE_PLAY")

    def test_a_pause_moves_nothing(self):
        as_sender(OWNER)
        self.c.set_paused(True)
        self._expect_frozen(AMAZON_URL)

    def test_an_underpayment_moves_nothing(self):
        as_sender(OWNER)
        self.c.set_fee(10 ** 15)
        self._expect_frozen(AMAZON_URL, value=1)

    def test_a_rate_limit_moves_nothing(self):
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self._expect_frozen(GPLAY_URL, sender=ALICE)

    def test_a_cooldown_moves_nothing(self):
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self._expect_frozen(AMAZON_URL, sender=BOB)

    def test_A_TRANSIENT_FAILURE_MOVES_ONLY_TOTAL_REQUESTS(self):
        """The request DID happen and DID reach consensus, so `total_requests`
        is allowed to move. Nothing else may: no check was written, no fee was
        earned, and no id was consumed."""
        H.PAGE_MAP[AMAZON_URL] = RuntimeError("WEBPAGE_LOAD_FAILED")
        self._expect_frozen(AMAZON_URL, allow=("total_requests",))

    def test_a_dead_page_moves_only_total_requests(self):
        H.PAGE_MAP[AMAZON_URL] = "Page Not Found\nWe're sorry." + " pad" * 40
        self._expect_frozen(AMAZON_URL, allow=("total_requests",))

    def test_a_transient_failure_does_not_consume_an_id(self):
        H.PAGE_MAP[AMAZON_URL] = RuntimeError("WEBPAGE_LOAD_FAILED")
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(int(self.c.next_id), 1)
        reset_chain(sender=BOB)
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["check_id"], 1)

    def test_a_transient_failure_clears_the_in_flight_marker(self):
        H.PAGE_MAP[AMAZON_URL] = RuntimeError("WEBPAGE_LOAD_FAILED")
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(int(self.c.pending.get(AMAZON_KEY) or 0), 0)

    def test_a_successful_check_moves_them_all(self):
        before = self._snap()
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        after = self._snap()
        self.assertEqual(after["total_requests"], before["total_requests"] + 1)
        self.assertEqual(after["total_checked"], before["total_checked"] + 1)
        self.assertEqual(after["next_id"], before["next_id"] + 1)
        self.assertEqual(after["pages"], before["pages"] + 1)


# ---------------------------------------------------------------------------
# 13. RULE 4 — the fee is snapshotted
# ---------------------------------------------------------------------------

class TestFeeIsSnapshotted(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def test_the_record_keeps_the_price_of_its_own_work(self):
        as_sender(OWNER)
        self.c.set_fee(1000)
        as_sender(ALICE, value=1000)
        self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(self.c.get_check(1)["fee_paid_wei"], "1000")

        as_sender(OWNER)
        self.c.set_fee(50000)
        at("2026-09-14T13:00:00Z")
        as_sender(BOB, value=50000)
        self.c.check_reviews(GPLAY_URL, "")

        self.assertEqual(self.c.get_check(1)["fee_paid_wei"], "1000")
        self.assertEqual(self.c.get_check(2)["fee_paid_wei"], "50000")

    def test_AN_OWNER_CANNOT_RESTATE_THE_PRICE_OF_PAST_WORK(self):
        as_sender(OWNER)
        self.c.set_fee(1000)
        as_sender(ALICE, value=1000)
        self.c.check_reviews(AMAZON_URL, "")
        before = self.c.get_check(1)["fee_paid_wei"]
        for new in (0, 99999, MOD.MAX_FEE_WEI):
            as_sender(OWNER)
            self.c.set_fee(new)
            self.assertEqual(self.c.get_check(1)["fee_paid_wei"], before)

    def test_a_free_check_records_zero(self):
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(self.c.get_check(1)["fee_paid_wei"], "0")

    def test_the_fee_ceiling_is_enforced(self):
        as_sender(OWNER)
        with self.assertRaises(H._UserError):
            self.c.set_fee(MOD.MAX_FEE_WEI + 1)
        with self.assertRaises(H._UserError):
            self.c.set_fee(-1)

    def test_default_fee_is_zero(self):
        self.assertEqual(int(self.c.fee_wei), 0)
        self.assertEqual(self.c.get_config()["fee_wei"], "0")


# ---------------------------------------------------------------------------
# 14. RULE 5 — a written check is immutable
# ---------------------------------------------------------------------------

class TestImmutabilityAfterWrite(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self.before = json.dumps(self.c.get_check(1), sort_keys=True)

    def _unchanged(self):
        self.assertEqual(json.dumps(self.c.get_check(1), sort_keys=True),
                         self.before)

    def test_a_pause_does_not_touch_a_record(self):
        as_sender(OWNER)
        self.c.set_paused(True)
        self._unchanged()

    def test_a_fee_change_does_not_touch_a_record(self):
        as_sender(OWNER)
        self.c.set_fee(12345)
        self._unchanged()

    def test_an_ownership_transfer_does_not_touch_a_record(self):
        as_sender(OWNER)
        self.c.transfer_ownership(CAROL)
        self._unchanged()

    def test_a_RE_CHECK_APPENDS_RATHER_THAN_EDITS(self):
        at("2026-09-14T14:00:00Z")
        H.PAGE_MAP[AMAZON_URL] = amazon_page(hist=(99, 1, 0, 0, 0),
                                             reviews=bought_reviews(10))
        as_sender(BOB)
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["check_id"], 2)
        self.assertEqual(r["trust_level"], MOD.T_MANIPULATED)
        self._unchanged()
        self.assertEqual(self.c.get_check(2)["trust_level"],
                         MOD.T_MANIPULATED)

    def test_the_history_ring_keeps_both(self):
        at("2026-09-14T14:00:00Z")
        as_sender(BOB)
        H.PAGE_MAP[AMAZON_URL] = amazon_page(reviews=organic_reviews(9))
        self.c.check_reviews(AMAZON_URL, "")
        h = self.c.get_history(AMAZON_URL)
        self.assertTrue(h["found"])
        self.assertEqual(h["total_checks"], 2)
        self.assertEqual([i["check_id"] for i in h["items"]], [2, 1])

    def test_the_ring_rotates_and_says_so(self):
        page = fixture("amazon_echo_dot")
        for i in range(MOD.HISTORY_CAP + 1):
            at("2026-09-%02dT12:00:00Z" % (15 + i))
            as_sender(H._Addr("0x" + format(200 + i, "040x")))
            H.PAGE_MAP[AMAZON_URL] = page
            r = self.c.check_reviews(AMAZON_URL, "")
            self.assertEqual(r["status"], "OK", r)
        gone = self.c.get_check(1)
        self.assertFalse(gone["found"])
        self.assertIn("rotated out", gone["reason"])
        self.assertIn(str(MOD.HISTORY_CAP), gone["reason"])

    def test_ONLY_FOUR_WRITES_ARE_OWNER_GATED(self):
        """Enumerated from the class rather than listed by hand, so a new
        owner-gated write cannot be added without this failing."""
        gated = set()
        for name in dir(FULL.ReviewGuard):
            if name.startswith("_"):
                continue
            fn = getattr(FULL.ReviewGuard, name)
            if not callable(fn):
                continue
            src = ""
            try:
                import inspect
                src = inspect.getsource(fn)
            except (OSError, TypeError):
                continue
            if "_only_owner" in src or "!= self.owner" in src:
                gated.add(name)
        self.assertEqual(gated, {"set_fee", "set_paused",
                                 "transfer_ownership", "withdraw_fees"})


# ---------------------------------------------------------------------------
# 15. RULE 6 — the owner cannot freeze user money
# ---------------------------------------------------------------------------

class TestOwnerCannotFreezeFunds(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def test_CLAIM_REFUND_WORKS_WHILE_PAUSED(self):
        as_sender(ALICE, value=GEN)
        self.c.check_reviews("https://www.yelp.com/biz/x", "")
        as_sender(OWNER)
        self.c.set_paused(True)
        as_sender(ALICE, value=0)
        out = self.c.claim_refund()
        self.assertEqual(out["status"], "OK")
        self.assertEqual(H.TRANSFERS, [(str(ALICE), GEN)])

    def test_every_read_works_while_paused(self):
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(OWNER)
        self.c.set_paused(True)
        as_sender(ALICE)
        self.assertTrue(self.c.get_check(1)["found"])
        self.assertTrue(self.c.get_check_by_url(AMAZON_URL)["found"])
        self.assertTrue(self.c.is_authentic(AMAZON_URL))
        self.assertTrue(self.c.get_trust_summary(AMAZON_URL)["found"])
        self.assertTrue(self.c.verify_check(1)["verified"])
        self.assertEqual(self.c.get_recent_checks(5)["count"], 1)
        self.assertTrue(self.c.get_history(AMAZON_URL)["found"])
        self.assertTrue(self.c.get_config()["paused"])
        self.assertTrue(self.c.detect_platform(AMAZON_URL)["supported"])

    def test_SETTLE_STALLED_WORKS_WHILE_PAUSED_AND_IS_PERMISSIONLESS(self):
        """An owner who could keep a page locked by declining to unstick it
        could censor the oracle, which is the same power as forging a verdict
        by a slower route."""
        self.c.pending[AMAZON_KEY] = NOW - MOD.PENDING_TTL - 1
        as_sender(OWNER)
        self.c.set_paused(True)
        as_sender(CAROL)
        out = self.c.settle_stalled(AMAZON_URL)
        self.assertEqual(out["status"], "CLEARED")
        self.assertEqual(int(self.c.pending.get(AMAZON_KEY) or 0), 0)

    def test_settle_stalled_refuses_too_early(self):
        self.c.pending[AMAZON_KEY] = NOW - 10
        as_sender(CAROL)
        out = self.c.settle_stalled(AMAZON_URL)
        self.assertEqual(out["status"], "TOO_EARLY")
        self.assertGreater(out["retry_in_s"], 0)
        self.assertNotEqual(int(self.c.pending.get(AMAZON_KEY) or 0), 0)

    def test_settle_stalled_on_a_clean_page_is_a_noop(self):
        self.assertEqual(self.c.settle_stalled(AMAZON_URL)["status"], "NOOP")

    def test_settle_stalled_rejects_an_unsupported_url(self):
        with self.assertRaises(H._UserError):
            self.c.settle_stalled("https://www.yelp.com/biz/x")

    def test_A_STALLED_ROUND_UNBLOCKS_THE_PAGE(self):
        self.c.pending[AMAZON_KEY] = NOW
        as_sender(BOB, value=GEN)
        r = self.c.check_reviews(AMAZON_URL, "")
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("in flight", r["reason"])
        at("2026-09-14T13:00:00Z")
        as_sender(CAROL)
        self.c.settle_stalled(AMAZON_URL)
        as_sender(BOB)
        self.assertEqual(self.c.check_reviews(AMAZON_URL, "")["status"], "OK")

    def test_WITHDRAW_CANNOT_TOUCH_CREDITED_REFUNDS(self):
        as_sender(ALICE, value=5 * GEN)
        self.c.check_reviews("https://www.yelp.com/biz/x", "")
        as_sender(OWNER)
        out = self.c.withdraw_fees(5 * GEN)
        self.assertEqual(out["status"], "NOOP")
        self.assertEqual(out["reserved_for_refunds_wei"], str(5 * GEN))
        self.assertEqual(H.TRANSFERS, [])
        as_sender(ALICE)
        self.assertEqual(self.c.claim_refund()["paid_wei"], str(5 * GEN))

    def test_withdraw_pays_only_earned_fees(self):
        as_sender(OWNER)
        self.c.set_fee(1000)
        as_sender(ALICE, value=1000)
        self.c.check_reviews(AMAZON_URL, "")
        as_sender(BOB, value=7000)
        self.c.check_reviews("https://www.yelp.com/biz/x", "")
        as_sender(OWNER)
        out = self.c.withdraw_fees(0)
        self.assertEqual(out["status"], "OK")
        self.assertEqual(out["paid_wei"], "1000")
        self.assertEqual(H.TRANSFERS, [(str(OWNER), 1000)])

    def test_only_the_owner_may_use_the_owner_methods(self):
        as_sender(ALICE)
        for call in (lambda: self.c.set_fee(1),
                     lambda: self.c.set_paused(True),
                     lambda: self.c.transfer_ownership(ALICE),
                     lambda: self.c.withdraw_fees(1)):
            with self.assertRaises(H._UserError):
                call()

    def test_ownership_transfer_moves_the_power(self):
        as_sender(OWNER)
        self.c.transfer_ownership(CAROL)
        as_sender(OWNER)
        with self.assertRaises(H._UserError):
            self.c.set_paused(True)
        as_sender(CAROL)
        self.assertTrue(self.c.set_paused(True)["paused"])

    def test_the_ledger_never_goes_negative(self):
        for i, url in enumerate(["", "https://www.yelp.com/biz/x", "nope"]):
            as_sender(H._Addr("0x" + format(300 + i, "040x")), value=GEN)
            self.c.check_reviews(url, "")
            self.assertGreaterEqual(int(self.c.balance_wei), 0)
            self.assertGreaterEqual(int(self.c.refunds_owed), 0)
            self.assertLessEqual(int(self.c.refunds_owed),
                                 int(self.c.balance_wei))


class TestMoneyLeavesThroughOneHelper(Case):
    def test_MONEY_LEAVES_THROUGH_EXACTLY_ONE_HELPER(self):
        """`Proxy.emit()` posts NO MESSAGE on this runner — it returns a method
        getter, so a bare `emit(value=...)` constructs an object and drops it.
        Every refund looked successful and not one wei moved. `emit_transfer`
        is the spelling that works, and it must appear in exactly one place per
        contract."""
        import ast
        for path in (SOURCE, CONSUMER):
            tree = ast.parse(path.read_text(encoding="utf8"))
            sends = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and \
                        isinstance(node.func, ast.Attribute) and \
                        node.func.attr in ("emit_transfer", "emit"):
                    sends.append((node.func.attr, node.lineno))
            self.assertEqual(len(sends), 1, "%s: %r" % (path.name, sends))
            self.assertEqual(sends[0][0], "emit_transfer", path.name)

    def test_the_helper_refuses_a_zero_payout(self):
        H.TRANSFERS.clear()
        MOD._pay(ALICE, 0)
        MOD._pay(ALICE, -5)
        self.assertEqual(H.TRANSFERS, [])


# ---------------------------------------------------------------------------
# 16. The storage axis — every stored field is bound by consensus
# ---------------------------------------------------------------------------

class TestStorageAxis(Case):
    DERIVED = {"d_timing", "d_rating", "d_quality", "d_credibility",
               "d_engagement", "overall", "trust_level", "available_weight",
               "credibility_basis", "content_hash"}
    BOOKKEEPING = {"check_id", "seq", "checked_at", "checker", "fee_paid_wei",
                   "rubric_version"}

    def test_EVERY_STORED_FIELD_IS_ON_THE_AXIS(self):
        """RULE 1, made mechanical. Every field of `Check` must be one of three
        things: a vector integer or identity string the validators compared, a
        value recomputed from the agreed vector, or contract bookkeeping the
        leader never touches. A new storage field cannot be added without
        putting it in one of those sets."""
        vector = set(MOD.FEATURE_RANGE.keys())
        identity = set(MOD.IDENTITY_KEYS)
        for field in FULL.Check.__annotations__:
            self.assertTrue(
                field in vector or field in identity
                or field in self.DERIVED or field in self.BOOKKEEPING,
                "Check.%s is on no axis: it is neither compared by _agrees, "
                "nor derived from the agreed vector, nor contract "
                "bookkeeping" % field)

    def test_every_vector_field_has_a_storage_slot(self):
        for key in MOD.FEATURE_RANGE:
            self.assertIn(key, FULL.Check.__annotations__, key)

    def test_every_identity_field_has_a_storage_slot(self):
        for key in MOD.IDENTITY_KEYS:
            self.assertIn(key, FULL.Check.__annotations__, key)

    def test_stored_vector_round_trips(self):
        c = fresh_guard()
        as_sender(ALICE)
        c.check_reviews(AMAZON_URL, "")
        feed = c.feeds.get(AMAZON_KEY)
        rec = feed.history[0]
        back = MOD._stored_vector(rec)
        fresh = MOD._features(
            MOD._parse_amazon(fixture("amazon_echo_dot"), TODAY), P_AMAZON)
        self.assertEqual(back, fresh)

    def test_STORED_VECTOR_KEEPS_THE_SENTINEL(self):
        """A read-back that 'cleaned up' a 255 into a 0 would make every
        unavailable dimension verify as a real zero — and `verify_check` would
        then confirm a record it had just corrupted."""
        c = fresh_guard()
        as_sender(ALICE)
        c.check_reviews(GPLAY_URL, "")
        rec = c.feeds.get(GPLAY_KEY).history[0]
        back = MOD._stored_vector(rec)
        self.assertEqual(back["pct_5"], UNAVAIL)
        self.assertEqual(back["verified_pct"], UNAVAIL)
        self.assertTrue(c.verify_check(1)["verified"])

    def test_THE_WRITE_PATH_READS_ONLY_FROM_THE_AGREED_OBJECT(self):
        """A static check that `_write` never reads a closure variable the
        leader alone saw. Every assignment into `rec` must come from `out`,
        `feats`, `rescored`, or a contract-owned local."""
        import ast, inspect
        src = inspect.getsource(FULL.ReviewGuard._write)
        tree = ast.parse(src.lstrip() if not src.startswith("\t") else
                         "\n".join(l[1:] if l.startswith("\t") else l
                                   for l in src.split("\n")))
        allowed_roots = {"out", "feats", "rescored", "self", "url_key",
                         "platform", "sender", "now", "fee", "value", "title",
                         "check_id", "rec", "feed", "score", "level",
                         "MOD", "u32", "u64", "u256", "str", "bool", "int",
                         "_as_int", "_short", "_score", "RUBRIC_VERSION",
                         "HISTORY_CAP", "T_AUTHENTIC", "T_SUSPICIOUS",
                         "T_MANIPULATED", "len", "range",
                         # MODULE CONSTANTS ONLY. Each name added here must be
                         # something the leader cannot influence; UNAVAIL is
                         # the sentinel, fixed at compile time.
                         "UNAVAIL"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Attribute) and \
                            isinstance(tgt.value, ast.Name) and \
                            tgt.value.id == "rec":
                        for sub in ast.walk(node.value):
                            if isinstance(sub, ast.Name) and \
                                    isinstance(sub.ctx, ast.Load):
                                self.assertIn(sub.id, allowed_roots,
                                              "rec.%s reads %s, which is not "
                                              "on the agreed axis"
                                              % (tgt.attr, sub.id))

    def test_the_write_path_rescores_rather_than_storing_the_leaders_scores(self):
        import inspect
        src = inspect.getsource(FULL.ReviewGuard._write)
        self.assertIn("_score(feats, platform)", src)
        self.assertNotIn('out["scores"]', src)


class TestVerifyDetectsTampering(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")
        self.rec = self.c.feeds.get(AMAZON_KEY).history[0]

    def test_verify_catches_a_tampered_overall(self):
        self.rec.overall = 100
        v = self.c.verify_check(1)
        self.assertFalse(v["verified"])
        fields = [m["field"] for m in v["mismatches"]]
        self.assertIn("overall", fields)

    def test_verify_catches_a_tampered_dimension(self):
        self.rec.d_timing = 0
        v = self.c.verify_check(1)
        self.assertFalse(v["verified"])
        self.assertIn("timing_pattern", [m["field"] for m in v["mismatches"]])

    def test_verify_catches_a_tampered_trust_level(self):
        self.rec.trust_level = MOD.T_MANIPULATED
        v = self.c.verify_check(1)
        self.assertFalse(v["verified"])
        self.assertIn("trust_level", [m["field"] for m in v["mismatches"]])

    def test_verify_catches_a_tampered_EVIDENCE_figure(self):
        """The evidence is not decoration. Changing a stored vector field
        changes both the recomputed score and the hash."""
        self.rec.verified_pct = 0
        v = self.c.verify_check(1)
        self.assertFalse(v["verified"])
        fields = [m["field"] for m in v["mismatches"]]
        self.assertIn("content_hash", fields)
        self.assertIn("reviewer_credibility", fields)

    def test_verify_catches_a_tampered_title(self):
        self.rec.title = "Something Else Entirely"
        v = self.c.verify_check(1)
        self.assertFalse(v["verified"])
        self.assertIn("content_hash", [m["field"] for m in v["mismatches"]])

    def test_verify_catches_a_tampered_hash(self):
        self.rec.content_hash = "0:" + "0" * 16
        v = self.c.verify_check(1)
        self.assertFalse(v["verified"])
        self.assertIn("content_hash", [m["field"] for m in v["mismatches"]])

    def test_verify_reports_the_rubric_version(self):
        v = self.c.verify_check(1)
        self.assertEqual(v["rubric_version"], MOD.RUBRIC_VERSION)
        self.assertEqual(v["current_rubric_version"], MOD.RUBRIC_VERSION)


# ---------------------------------------------------------------------------
# 17. The guard methods
# ---------------------------------------------------------------------------

class TestGuards(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def _check(self, url, page=None, sender=ALICE, when=None):
        if page is not None:
            key = {AMAZON_URL: AMAZON_URL, GPLAY_URL: GPLAY_FETCH,
                   APPSTORE_URL: APPSTORE_FETCH}[url]
            H.PAGE_MAP[key] = page
        if when:
            at(when)
        as_sender(sender)
        return self.c.check_reviews(url, "")

    def test_is_authentic_on_an_authentic_page(self):
        self._check(AMAZON_URL)
        self.assertTrue(self.c.is_authentic(AMAZON_URL))

    def test_IS_AUTHENTIC_IS_FALSE_FOR_NEVER_CHECKED(self):
        """A contract asking this is about to list a product. 'We have never
        heard of it' must not read the same as 'we checked and it is real'."""
        self.assertFalse(self.c.is_authentic(AMAZON_URL))

    def test_is_authentic_is_false_for_manipulated(self):
        self._check(AMAZON_URL, amazon_page(hist=(99, 1, 0, 0, 0),
                                            reviews=bought_reviews(10)))
        self.assertFalse(self.c.is_authentic(AMAZON_URL))

    def test_is_authentic_is_false_for_inconclusive(self):
        self._check(AMAZON_URL, amazon_page(reviews=()) + "\npad" * 100)
        self.assertFalse(self.c.is_authentic(AMAZON_URL))

    def test_is_authentic_is_false_for_an_unsupported_host(self):
        self.assertFalse(self.c.is_authentic("https://www.yelp.com/biz/x"))
        self.assertFalse(self.c.is_authentic(""))

    def test_require_authentic_passes_only_authentic(self):
        self._check(AMAZON_URL)
        out = self.c.require_authentic(AMAZON_URL)
        self.assertTrue(out["ok"])
        self.assertEqual(out["trust_level"], MOD.T_AUTHENTIC)

    def test_REQUIRE_AUTHENTIC_REVERTS_ON_EVERYTHING_ELSE(self):
        """Stricter than the brief's 'reverts if MANIPULATED', deliberately. A
        guard named `require_authentic` that waved through SUSPICIOUS,
        INCONCLUSIVE and never-checked pages would be a rubber stamp for
        exactly the listings nobody has verified."""
        with self.assertRaises(H._UserError):
            self.c.require_authentic(AMAZON_URL)          # never checked
        self._check(AMAZON_URL, amazon_page(hist=(99, 1, 0, 0, 0),
                                            reviews=bought_reviews(10)))
        with self.assertRaises(H._UserError):
            self.c.require_authentic(AMAZON_URL)          # manipulated
        self._check(GPLAY_URL, "Ratings and reviews\n4.9\n" + "pad\n" * 100,
                    sender=BOB)
        with self.assertRaises(H._UserError):
            self.c.require_authentic(GPLAY_URL)           # inconclusive

    def test_require_authentic_reverts_on_an_unsupported_host(self):
        with self.assertRaises(H._UserError):
            self.c.require_authentic("https://www.yelp.com/biz/x")

    def test_require_not_manipulated_is_the_briefs_literal_guard(self):
        self._check(AMAZON_URL)
        self.assertTrue(self.c.require_not_manipulated(AMAZON_URL)["ok"])

    def test_require_not_manipulated_reverts_on_manipulated(self):
        self._check(AMAZON_URL, amazon_page(hist=(99, 1, 0, 0, 0),
                                            reviews=bought_reviews(10)))
        with self.assertRaises(H._UserError):
            self.c.require_not_manipulated(AMAZON_URL)

    def test_REQUIRE_NOT_MANIPULATED_ALSO_REVERTS_ON_INCONCLUSIVE(self):
        """An unreadable page is not evidence of authenticity — rule 7."""
        self._check(GPLAY_URL, "Ratings and reviews\n4.9\n" + "pad\n" * 100)
        with self.assertRaises(H._UserError):
            self.c.require_not_manipulated(GPLAY_URL)

    def test_require_not_manipulated_accepts_suspicious(self):
        half = organic_reviews(8)
        for i, r in enumerate(half):
            if i >= 4:
                r["body"] = GENERIC_BODY
                r["helpful"] = None
            r["date"] = "January %d, 2026" % (i + 2)
        self._check(AMAZON_URL, amazon_page(hist=(90, 6, 2, 1, 1),
                                            reviews=half))
        rec = self.c.get_check_by_url(AMAZON_URL)
        self.assertEqual(rec["trust_level"], MOD.T_SUSPICIOUS)
        self.assertTrue(self.c.require_not_manipulated(AMAZON_URL)["ok"])
        with self.assertRaises(H._UserError):
            self.c.require_authentic(AMAZON_URL)

    def test_GET_TRUST_SUMMARY_NEVER_RAISES(self):
        """The read surface a consumer contract should depend on.
        `require_authentic` would make every refusal a revert — which on a
        payable path means keeping the caller's deposit."""
        for url in ("", "  ", "nope", "https://www.yelp.com/biz/x",
                    AMAZON_URL, "https://www.amazon.com/s?k=x",
                    "x" * 500, "https://amazon.com.evil.test/dp/B07FZ8S74R"):
            out = self.c.get_trust_summary(url)
            self.assertIn("trust_level", out)
            self.assertIn("found", out)
            if not out["found"]:
                self.assertEqual(out["trust_level"], MOD.T_INCONCLUSIVE)
                self.assertNotEqual(out["reason"], "")

    def test_trust_summary_of_a_checked_page(self):
        self._check(AMAZON_URL)
        out = self.c.get_trust_summary(AMAZON_URL)
        self.assertTrue(out["found"])
        self.assertEqual(out["url_key"], AMAZON_KEY)
        self.assertEqual(out["trust_level"], MOD.T_AUTHENTIC)
        self.assertGreater(out["checked_at"], 0)
        self.assertNotEqual(out["content_hash"], "")


# ---------------------------------------------------------------------------
# 18. MarketplaceConsumer — composability across a REAL call boundary
#
# The consumer is driven against the REAL ReviewGuard instance rather than a
# hand-written fake that agrees with itself.
# ---------------------------------------------------------------------------

def wired_pair(min_score=70, max_age=30 * DAY):
    guard = fresh_guard()
    H.ORACLE["impl"] = guard
    as_sender(OWNER)
    market = CONS.MarketplaceConsumer(H._Addr("0x" + "e" * 40), min_score,
                                      max_age)
    as_sender(ALICE)
    return guard, market


class TestMarketplaceConsumer(Case):
    def setUp(self):
        super().setUp()
        self.guard, self.market = wired_pair()

    def _check(self, url, page=None, sender=ALICE):
        if page is not None:
            key = {AMAZON_URL: AMAZON_URL, GPLAY_URL: GPLAY_FETCH,
                   APPSTORE_URL: APPSTORE_FETCH}[url]
            H.PAGE_MAP[key] = page
        as_sender(sender)
        return self.guard.check_reviews(url, "")

    def test_an_authentic_product_lists(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["url_key"], AMAZON_KEY)
        self.assertEqual(r["admitted_on"]["trust_level"], MOD.T_AUTHENTIC)

    def test_THE_LISTING_PINS_WHAT_WAS_KNOWN(self):
        """A product whose reviews are later gamed does not rewrite history.
        An auditor can ask 'what did you know when you listed this'."""
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 1000)
        got = self.market.get_listing(AMAZON_KEY)
        self.assertEqual(got["admitted_on"]["check_id"], 1)
        self.assertNotEqual(got["admitted_on"]["content_hash"], "")

        at("2026-09-14T14:00:00Z")
        self._check(AMAZON_URL, amazon_page(hist=(99, 1, 0, 0, 0),
                                            reviews=bought_reviews(10)),
                    sender=BOB)
        self.assertEqual(self.guard.get_check_by_url(AMAZON_URL)["trust_level"],
                         MOD.T_MANIPULATED)
        after = self.market.get_listing(AMAZON_KEY)
        self.assertEqual(after["admitted_on"], got["admitted_on"])

    def test_a_manipulated_product_is_refused_and_refunded(self):
        self._check(AMAZON_URL, amazon_page(hist=(99, 1, 0, 0, 0),
                                            reviews=bought_reviews(10)))
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(r["trust_level"], MOD.T_MANIPULATED)
        self.assertEqual(r["refunded_wei"], str(GEN))
        self.assertEqual(int(self.market.get_refund_owed(ALICE)["owed_wei"]),
                         GEN)

    def test_A_NEVER_CHECKED_PRODUCT_IS_REFUSED(self):
        """The consumer that assumed `found` was true would treat 'never
        checked' as a score of zero — or worse, as a pass."""
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("never checked", r["reason"])
        self.assertEqual(r["refunded_wei"], str(GEN))

    def test_INCONCLUSIVE_IS_REFUSED_BY_NAME(self):
        """Its overall is 0, so the score test WOULD catch it — but only by
        accident. A future rubric reporting a nonzero score alongside
        INCONCLUSIVE would silently start admitting them."""
        self._check(GPLAY_URL, "Ratings and reviews\n4.9\n" + "pad\n" * 100)
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(GPLAY_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(r["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertIn("could not read", r["reason"])

    def test_a_suspicious_product_is_refused(self):
        half = organic_reviews(8)
        for i, r in enumerate(half):
            if i >= 4:
                r["body"] = GENERIC_BODY
                r["helpful"] = None
            r["date"] = "January %d, 2026" % (i + 2)
        self._check(AMAZON_URL, amazon_page(hist=(90, 6, 2, 1, 1),
                                            reviews=half))
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(r["trust_level"], MOD.T_SUSPICIOUS)

    def test_an_unsupported_host_is_refused_and_refunded(self):
        as_sender(ALICE, value=GEN)
        r = self.market.list_product("https://www.yelp.com/biz/x", 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(r["refunded_wei"], str(GEN))

    def test_A_STALE_CHECK_IS_REFUSED(self):
        """The staleness rule is the CONSUMER'S, not the oracle's. The oracle
        reports what it measured and when; each integrator decides how old is
        too old."""
        self._check(AMAZON_URL)
        at("2026-12-31T12:00:00Z")
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("days old", r["reason"])

    def test_a_stricter_min_score_refuses_a_passing_product(self):
        guard, market = wired_pair(min_score=99)
        H.ORACLE["impl"] = guard
        as_sender(ALICE)
        guard.check_reviews(AMAZON_URL, "")
        as_sender(ALICE, value=GEN)
        r = market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("below this marketplace's minimum", r["reason"])

    def test_THE_REFUSAL_LOG_IS_THE_POINT(self):
        """A guard whose refusals are invisible is a guard nobody can audit."""
        as_sender(ALICE, value=GEN)
        self.market.list_product(AMAZON_URL, 1000)
        as_sender(BOB, value=0)
        self.market.list_product("https://www.yelp.com/biz/x", 1)
        log = self.market.get_refusals(10)
        self.assertEqual(log["count"], 2)
        for item in log["items"]:
            self.assertNotEqual(item["reason"], "")
            self.assertIn("who", item)

    def test_listings_read_back(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 4200)
        out = self.market.get_listings(10)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["items"][0]["price_wei"], "4200")
        self.assertEqual(out["items"][0]["trust_level"], MOD.T_AUTHENTIC)

    def test_a_double_listing_is_refused(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 1000)
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 2000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("already listed", r["reason"])

    def test_a_seller_may_delist_their_own(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(self.market.delist(AMAZON_KEY)["status"], "OK")
        self.assertEqual(self.market.get_listings(10)["count"], 0)

    def test_a_stranger_may_not_delist(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 1000)
        as_sender(CAROL)
        with self.assertRaises(H._UserError):
            self.market.delist(AMAZON_KEY)

    def test_the_owner_may_delist_anything(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 1000)
        as_sender(OWNER)
        self.assertEqual(self.market.delist(AMAZON_KEY)["status"], "OK")

    def test_LIST_PRODUCT_NEVER_RAISES(self):
        for i, url in enumerate(["", "  ", "nope", AMAZON_URL, GPLAY_URL,
                                 "https://www.yelp.com/biz/x", "x" * 500,
                                 "https://www.amazon.com/s?k=x"]):
            as_sender(H._Addr("0x" + format(400 + i, "040x")), value=3)
            try:
                r = self.market.list_product(url, 1)
            except Exception as e:
                self.fail("list_product raised on %r: %s" % (url, e))
            self.assertIn(r["status"], ("OK", "REJECTED"))
            self.assertEqual(r["refunded_wei"], "3")

    def test_a_negative_price_is_refused_and_refunded(self):
        self._check(AMAZON_URL)
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, -1)
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(r["refunded_wei"], str(GEN))

    def test_refunds_are_claimable(self):
        as_sender(ALICE, value=GEN)
        self.market.list_product(AMAZON_URL, 1000)
        as_sender(ALICE, value=0)
        out = self.market.claim_refund()
        self.assertEqual(out["status"], "OK")
        self.assertEqual(H.TRANSFERS, [(str(ALICE), GEN)])

    def test_policy_change_does_not_rejudge_past_listings(self):
        self._check(AMAZON_URL)
        as_sender(ALICE)
        self.market.list_product(AMAZON_URL, 1000)
        before = self.market.get_listing(AMAZON_KEY)
        as_sender(OWNER)
        self.market.set_policy(100, 1)
        self.assertEqual(self.market.get_listing(AMAZON_KEY), before)

    def test_only_the_owner_sets_policy(self):
        as_sender(ALICE)
        with self.assertRaises(H._UserError):
            self.market.set_policy(50, DAY)

    def test_policy_bounds(self):
        as_sender(OWNER)
        with self.assertRaises(H._UserError):
            self.market.set_policy(101, DAY)
        with self.assertRaises(H._UserError):
            self.market.set_policy(50, 0)

    def test_the_policy_is_self_describing(self):
        p = self.market.get_policy()
        self.assertEqual(p["min_score"], 70)
        self.assertIn("AUTHENTIC only", p["policy_note"])
        self.assertIn("INCONCLUSIVE", p["policy_note"])

    def test_the_consumer_survives_a_broken_oracle(self):
        class Broken:
            def get_trust_summary(self, url):
                return "not a dict"
        H.ORACLE["impl"] = Broken()
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("unreadable", r["reason"])
        self.assertEqual(r["refunded_wei"], str(GEN))

    def test_the_consumer_survives_an_oracle_missing_fields(self):
        class Partial:
            def get_trust_summary(self, url):
                return {"found": True}
        H.ORACLE["impl"] = Partial()
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertEqual(r["refunded_wei"], str(GEN))

    def test_AN_ORACLE_CLAIMING_AUTHENTIC_WITH_NO_CHECK_TIME_IS_REFUSED(self):
        """Without a check time the staleness rule cannot be applied, and a
        guard that cannot apply its own rule must refuse rather than assume."""
        class NoClock:
            def get_trust_summary(self, url):
                return {"found": True, "trust_level": T_AUTH, "overall": 100,
                        "url_key": "X:y", "checked_at": 0}
        T_AUTH = MOD.T_AUTHENTIC
        H.ORACLE["impl"] = NoClock()
        as_sender(ALICE, value=GEN)
        r = self.market.list_product(AMAZON_URL, 1000)
        self.assertEqual(r["status"], "REJECTED")
        self.assertIn("no check time", r["reason"])


# ---------------------------------------------------------------------------
# 19. Static checks — the things that only fail after a deploy
# ---------------------------------------------------------------------------

class TestStaticSafety(Case):
    def test_no_undefined_names_anywhere(self):
        """A name error inside a `@gl.public.view` only fires when that view is
        called on chain — after a deploy, after a wait, on a network. This
        walks every scope, class bodies and comprehensions included."""
        for path in (SOURCE, CONSUMER):
            problems = undefined_names(path)
            self.assertEqual(problems, [], "%s: %r" % (path.name, problems))

    def test_THE_RUNNER_HEADER_IS_EXACTLY_TWO_LINES(self):
        """GenVM parses the contiguous leading `#` block as the runner header.
        A third comment line there makes the contract undeployable with NO
        error reported but `invalid_contract`."""
        for path in (SOURCE, CONSUMER):
            lines = path.read_text(encoding="utf8").split("\n")
            self.assertEqual(lines[0], "# v0.3.0", path.name)
            self.assertEqual(
                lines[1],
                '# { "Depends": "py-genlayer:'
                '5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }',
                path.name)
            self.assertEqual(lines[2], "import genlayer as gl", path.name)

    def test_the_v06_namespace_is_used_throughout(self):
        text = SOURCE.read_text(encoding="utf8")
        for needed in ("gl.contract.Contract", "gl.storage.TreeMap",
                       "gl.storage.DynArray", "@gl.storage.allow",
                       "gl.message.raw", "gl.contract.get_at",
                       "gl.vm.run_nondet", "gl.public.write.payable",
                       "gl.public.view"):
            self.assertIn(needed, text, needed)
        self.assertIn("@gl.contract.interface",
                      CONSUMER.read_text(encoding="utf8"))

    def test_no_pre_v06_spellings_survive(self):
        for path in (SOURCE, CONSUMER):
            text = path.read_text(encoding="utf8")
            for dead in ("allow_storage", "gl.message_raw",
                         "gl.get_contract_at", "gl.contract_interface",
                         "gl.eq_principle", "gl.Contract"):
                self.assertNotIn(dead, text, "%s: %s" % (path.name, dead))

    def test_no_float_literals_reach_the_consensus_path(self):
        """A `float` in a nondet return is NOT calldata encodable — a prior
        probe died with `not calldata encodable 17270822091.14536: float`."""
        import ast
        tree = ast.parse(SOURCE.read_text(encoding="utf8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                self.fail("float literal at line %d" % node.lineno)

    def test_no_true_division_anywhere(self):
        """`/` produces a float even on two ints. Every division in a contract
        that returns numbers through consensus must be `//`."""
        import ast
        for path in (SOURCE, CONSUMER):
            tree = ast.parse(path.read_text(encoding="utf8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                    self.fail("%s: true division at line %d"
                              % (path.name, node.lineno))

    def test_no_forbidden_imports(self):
        import ast
        allowed = {"genlayer", "dataclasses", "json", "typing"}
        for path in (SOURCE, CONSUMER):
            tree = ast.parse(path.read_text(encoding="utf8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for al in node.names:
                        self.assertIn(al.name.split(".")[0], allowed,
                                      path.name)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn((node.module or "").split(".")[0], allowed,
                                  path.name)

    def test_THE_FETCH_HOSTS_ARE_MODULE_CONSTANTS(self):
        """A submitter who could name the host could point five validators at a
        server they control. Every host in the table is a literal in the source
        and none is assembled from an argument."""
        text = SOURCE.read_text(encoding="utf8")
        self.assertIn('"amazon.com"', text)
        self.assertIn('"play.google.com"', text)
        self.assertIn('"apps.apple.com"', text)
        import ast, inspect
        src = inspect.getsource(MOD._canonical)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.startswith("https://"):
                    self.assertTrue(
                        node.value.startswith("https://www.")
                        or node.value.startswith("https://play.google.com")
                        or node.value.startswith("https://apps.apple.com"),
                        node.value)

    def test_every_public_method_the_brief_asked_for_exists(self):
        for name in ("check_reviews", "get_check", "get_check_by_url",
                     "get_checks_by_platform", "get_recent_checks",
                     "is_authentic", "require_authentic", "get_stats",
                     "get_config", "verify_check", "get_trust_summary",
                     "settle_stalled"):
            self.assertTrue(hasattr(FULL.ReviewGuard, name), name)

    def test_settle_stalled_exists_and_is_permissionless(self):
        import inspect
        src = inspect.getsource(FULL.ReviewGuard.settle_stalled)
        self.assertNotIn("_only_owner", src)
        self.assertNotIn("self.paused", src)

    def test_check_reviews_is_payable(self):
        src = SOURCE.read_text(encoding="utf8")
        i = src.find("def check_reviews")
        self.assertGreater(i, 0)
        self.assertIn("@gl.public.write.payable", src[max(0, i - 200):i])

    def test_the_two_payable_methods_are_the_two_that_take_money(self):
        import ast
        want = {SOURCE.name: {"check_reviews"},
                CONSUMER.name: {"list_product"}}
        for path in (SOURCE, CONSUMER):
            tree = ast.parse(path.read_text(encoding="utf8"))
            payable = set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Attribute) and \
                            dec.attr == "payable":
                        payable.add(node.name)
            self.assertEqual(payable, want[path.name], path.name)

    def test_the_rate_limit_matches_the_brief(self):
        self.assertEqual(MOD.RATE_LIMIT_SECONDS, 300)

    def test_the_thresholds_match_the_brief(self):
        self.assertEqual(MOD.AUTHENTIC_MIN, 70)
        self.assertEqual(MOD.SUSPICIOUS_MIN, 40)
        self.assertEqual(MOD.Q_STEP, 5)
        self.assertEqual(MOD.ORDINAL_MAX, 7)

    def test_the_default_fee_is_zero_as_the_brief_asks(self):
        self.assertEqual(MOD.DEFAULT_FEE_WEI, 0)

    def test_no_blocked_platform_is_in_the_host_table(self):
        blocked = ("trustpilot", "yelp", "google.com/maps", "walmart",
                   "bestbuy", "tripadvisor", "etsy", "g2.com", "imdb",
                   "newegg", "goodreads", "target.com", "steampowered")
        for plat in MOD.PLATFORMS:
            for host in MOD.PLATFORM_HOSTS[plat]:
                for bad in blocked:
                    self.assertNotIn(bad, host, "%s in %s" % (bad, host))

    def test_the_unsupported_table_names_the_brief_s_four(self):
        c = fresh_guard()
        un = c.get_config()["unsupported"]
        for name in ("TRUSTPILOT", "YELP", "GOOGLE_MAPS"):
            self.assertIn(name, un)
            self.assertNotEqual(un[name], "")


class TestViewsNeverRaiseOnGarbage(Case):
    """Every read except the two `require_*` guards must answer rather than
    revert. A view that raises on a bad argument is a view the front end has to
    wrap in a try, and one it will eventually forget to."""

    GARBAGE = ("", "   ", "nope", "https://evil.test/x", "x" * 900,
               "https://www.amazon.com/", "0", "://", "amazon.com",
               "https://amazon.com.evil.test/dp/B07FZ8S74R")

    def setUp(self):
        super().setUp()
        self.c = fresh_guard()
        as_sender(ALICE)
        self.c.check_reviews(AMAZON_URL, "")

    def test_url_views(self):
        for url in self.GARBAGE:
            for fn in (self.c.get_check_by_url, self.c.get_trust_summary,
                       self.c.detect_platform, self.c.get_history):
                try:
                    fn(url)
                except Exception as e:
                    self.fail("%s raised on %r: %s" % (fn.__name__, url, e))
            self.assertIsInstance(self.c.is_authentic(url), bool)

    def test_id_views(self):
        for cid in (-1, 0, 1, 2, 999999, 10 ** 12):
            self.c.get_check(cid)
            self.c.verify_check(cid)

    def test_count_views(self):
        for n in (-5, 0, 1, 20, 10 ** 6):
            self.c.get_recent_checks(n)
            self.c.get_checks_by_platform("AMAZON", n)
            self.c.get_history(AMAZON_URL, n)

    def test_platform_views(self):
        for p in ("", "amazon", "AMAZON", "YELP", "x" * 200, "google_play"):
            out = self.c.get_checks_by_platform(p)
            self.assertIn("items", out)

    def test_stats_and_config_on_an_empty_contract(self):
        empty = fresh_guard()
        self.assertEqual(empty.get_stats()["total_checked"], 0)
        self.assertEqual(empty.get_stats()["manipulation_rate_pct"], 0)
        self.assertEqual(empty.get_recent_checks(10)["count"], 0)
        self.assertIn("platforms", empty.get_config())


# ---------------------------------------------------------------------------
# 20. Why a check was inconclusive — the field that makes it actionable
#
# Measured on 2026-09-14: an amazon.com/dp page that had rendered 37,914
# characters with eight reviews an hour earlier began rendering 14,163 and
# stopping before its review section. Raising the wait from 6s to 12s changed
# the length by 47 characters, so it is not a timing problem — Amazon is simply
# serving less. The contract's job is to say so rather than to guess.
# ---------------------------------------------------------------------------

class TestInconclusiveExplainsItself(Case):
    def test_a_truncated_page_says_it_was_truncated(self):
        f = vec(reviews_parsed=0, dated_reviews=0, distinct_days=0,
                max_same_day=0, page_chars=14000, reviews_section=0)
        s = MOD._score(f, P_AMAZON)
        self.assertEqual(s["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertIn("stopped before its review list", s["why"])
        self.assertIn("14000", s["why"])

    def test_A_PAGE_WITH_FEW_REVIEWS_READS_DIFFERENTLY_FROM_A_CUT_OFF_ONE(self):
        """The distinction that matters. "0 reviews parsed" is ambiguous
        between a product nobody has reviewed and a page served without its
        review section, and those call for opposite responses — believe it,
        versus check again later."""
        cut = MOD._score(
            vec(reviews_parsed=0, dated_reviews=0, distinct_days=0,
                max_same_day=0, page_chars=14000, reviews_section=0),
            P_AMAZON)
        thin = MOD._score(
            vec(reviews_parsed=2, dated_reviews=2, distinct_days=2,
                max_same_day=1, page_chars=38000, reviews_section=1),
            P_AMAZON)
        self.assertNotEqual(cut["why"], thin["why"])
        self.assertIn("stopped before", cut["why"])
        self.assertIn("review list rendered", thin["why"])

    def test_a_weight_shortfall_reads_differently_again(self):
        f = vec(dated_reviews=0, pct_5=UNAVAIL, pct_4=UNAVAIL, pct_3=UNAVAIL,
                pct_2=UNAVAIL, pct_1=UNAVAIL, verified_pct=UNAVAIL,
                helpful_pct=UNAVAIL, helpful_total=UNAVAIL)
        s = MOD._score(f, P_APPSTORE)
        self.assertIn("rubric points", s["why"])
        self.assertNotIn("stopped before", s["why"])

    def test_page_chars_is_quantised(self):
        for name, fn, plat in (("amazon_echo_dot", MOD._parse_amazon, P_AMAZON),
                               ("gplay_whatsapp", MOD._parse_gplay, P_GPLAY),
                               ("appstore_whatsapp", MOD._parse_appstore,
                                P_APPSTORE)):
            f = MOD._features(fn(fixture(name), TODAY), plat)
            self.assertEqual(f["page_chars"] % 500, 0, plat)

    def test_A_FEW_BYTES_OF_MARKUP_DRIFT_STILL_AGREES(self):
        """Two renders of one page can differ by a handful of bytes of markup.
        Quantising to 500 absorbs that; `_agrees` would otherwise reject the
        pair over a difference no rubric reads."""
        base = fixture("amazon_echo_dot")
        a = MOD._features(MOD._parse_amazon(base, TODAY), P_AMAZON)
        b = MOD._features(MOD._parse_amazon(base + "x" * 40, TODAY), P_AMAZON)
        self.assertEqual(a["page_chars"], b["page_chars"])

    def test_a_real_truncation_does_not_agree(self):
        text = fixture("amazon_echo_dot")
        full = MOD._features(MOD._parse_amazon(text, TODAY), P_AMAZON)
        # Cut at the review-section anchor, which is where the live page
        # actually stopped — not at an arbitrary byte offset.
        cut = MOD._features(
            MOD._parse_amazon(text[: text.find("Top reviews from")], TODAY),
            P_AMAZON)
        self.assertNotEqual(full["page_chars"], cut["page_chars"])
        self.assertEqual(full["reviews_section"], 1)
        self.assertEqual(cut["reviews_section"], 0)

    def test_the_review_section_flag_is_true_on_every_real_fixture(self):
        for name, fn, plat in (("amazon_echo_dot", MOD._parse_amazon, P_AMAZON),
                               ("gplay_whatsapp", MOD._parse_gplay, P_GPLAY),
                               ("appstore_whatsapp", MOD._parse_appstore,
                                P_APPSTORE)):
            f = MOD._features(fn(fixture(name), TODAY), plat)
            self.assertEqual(f["reviews_section"], 1, plat)

    def test_THE_TRUNCATED_LIVE_AMAZON_PAGE_IS_INCONCLUSIVE_NOT_MANIPULATED(self):
        """The shape studio-dev actually returned on 2026-09-14: the rating
        summary present, the review list absent. A rubric that scored what it
        had would have called a million-rating product manipulated on the
        strength of one dimension."""
        cut = fixture("amazon_echo_dot")
        end = cut.find("Top reviews from")
        page = cut[:end]
        parsed = MOD._parse_amazon(page, TODAY)
        self.assertEqual(len(parsed["reviews"]), 0)
        self.assertFalse(parsed["has_review_section"])
        self.assertEqual(parsed["pct"], [83, 12, 4, 0, 1])
        f = MOD._features(parsed, P_AMAZON)
        s = MOD._score(f, P_AMAZON)
        self.assertEqual(s["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertNotEqual(s["trust_level"], MOD.T_MANIPULATED)
        self.assertEqual(s["overall"], 0)

    def test_both_new_fields_are_on_the_consensus_axis(self):
        for key in ("page_chars", "reviews_section"):
            self.assertIn(key, MOD.FEATURE_RANGE, key)
            a = honest()
            b = honest()
            b["features"][key] = 0 if b["features"][key] else 1
            if key == "page_chars":
                b["features"][key] = b["features"][key] + 500
            reseal(b)
            self.assertFalse(MOD._agrees(a, b), key)

    def test_neither_new_field_may_be_unavailable(self):
        for key in ("page_chars", "reviews_section"):
            self.assertNotIn(key, MOD.NULLABLE, key)
            out = honest()
            out["features"][key] = UNAVAIL
            self.assertFalse(MOD._coherent(reseal(out)), key)


# ---------------------------------------------------------------------------
# 21. Fuzz — the whole pipeline, against text nobody designed it for
#
# A parser only ever sees pages somebody else controls. These are deterministic
# (a fixed LCG, not `random`) so a failure reproduces exactly, and they assert
# the two properties that must hold for ANY input: nothing raises, and every
# value that reaches storage is inside its declared range.
# ---------------------------------------------------------------------------

def _lcg(seed):
    x = seed * 1103515245 + 12345
    while True:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        yield x


ALPHABET = (
    "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "\n\t.,!?'\"()[]{}<>/\\|@#$%^&*-_=+~`;: é中ا\U0001f600"
)

TOKENS = (
    "Customer reviews", "Top reviews from the United States",
    "5 out of 5 stars", "0 out of 5 stars", "9 out of 5 stars",
    "Reviewed in the United States on December 14, 2019",
    "Reviewed in the United States on",
    "Verified Purchase", "Helpful", "Report", "Read more",
    "One person found this helpful", "999999999 people found this helpful",
    "-1 people found this helpful", "more_vert", "Ratings & Reviews",
    "Ratings and reviews", "4.7", "out of 5", "19M Ratings",
    "239M reviews", "0 reviews", "5 star", "100%", "-5%", "999%",
    "Reviews with images", "What's New", "Jan 21", "13/45/2099",
    "google_logo Play", "iPhone", "TV", "", " ", "\n",
)


def fuzz_page(seed, n=120):
    g = _lcg(seed)
    out = []
    for _ in range(n):
        r = next(g) % 100
        if r < 55:
            out.append(TOKENS[next(g) % len(TOKENS)])
        else:
            length = next(g) % 90
            s = ""
            for _ in range(length):
                s += ALPHABET[next(g) % len(ALPHABET)]
            out.append(s)
    return "\n".join(out)


class TestFuzz(Case):
    SEEDS = list(range(1, 61))

    def test_NO_PARSER_EVER_RAISES(self):
        for seed in self.SEEDS:
            page = fuzz_page(seed)
            for fn in (MOD._parse_amazon, MOD._parse_gplay,
                       MOD._parse_appstore):
                try:
                    fn(page, TODAY)
                except Exception as e:
                    self.fail("%s raised on seed %d: %r" % (fn.__name__, seed, e))

    def test_NO_FEATURE_VECTOR_IS_EVER_OUT_OF_RANGE(self):
        """The property `_coherent` depends on. If `_features` could emit an
        out-of-range value on some page, an honest leader would be voted down
        by every validator and that URL could never be checked at all."""
        for seed in self.SEEDS:
            page = fuzz_page(seed)
            for fn, plat in ((MOD._parse_amazon, P_AMAZON),
                             (MOD._parse_gplay, P_GPLAY),
                             (MOD._parse_appstore, P_APPSTORE)):
                f = MOD._features(fn(page, TODAY), plat)
                self.assertEqual(set(f), set(MOD.FEATURE_RANGE), (seed, plat))
                for key, val in f.items():
                    self.assertIsInstance(val, int, (seed, plat, key))
                    self.assertNotIsInstance(val, bool, (seed, plat, key))
                    if val == UNAVAIL:
                        self.assertIn(key, MOD.NULLABLE, (seed, plat, key))
                        continue
                    lo, hi = MOD.FEATURE_RANGE[key]
                    self.assertTrue(lo <= val <= hi,
                                    "seed %d %s: %s = %d, range (%d, %d)"
                                    % (seed, plat, key, val, lo, hi))

    def test_EVERY_FUZZED_RESULT_IS_SELF_COHERENT(self):
        """A leader that read a strange page must still produce something its
        validators can accept. If `_coherent` rejected an honest reading, the
        oracle would simply stop working on pages it found confusing."""
        for seed in self.SEEDS:
            H.PAGE_MAP[AMAZON_URL] = fuzz_page(seed) + "\npadding" * 40
            out = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
            if not out.get("ok"):
                continue
            self.assertTrue(MOD._coherent(out), "seed %d" % seed)

    def test_two_readings_of_one_fuzzed_page_agree(self):
        for seed in self.SEEDS[:20]:
            H.PAGE_MAP[AMAZON_URL] = fuzz_page(seed) + "\npadding" * 40
            a = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
            b = MOD._collect(AMAZON_KEY, AMAZON_URL, P_AMAZON, TODAY)
            if a.get("ok") and b.get("ok"):
                self.assertTrue(MOD._agrees(a, b), "seed %d" % seed)

    def test_scores_are_always_in_band(self):
        for seed in self.SEEDS:
            page = fuzz_page(seed)
            for fn, plat in ((MOD._parse_amazon, P_AMAZON),
                             (MOD._parse_gplay, P_GPLAY),
                             (MOD._parse_appstore, P_APPSTORE)):
                s = MOD._score(MOD._features(fn(page, TODAY), plat), plat)
                self.assertIn(s["trust_level"], MOD.TRUST_LEVELS)
                self.assertTrue(0 <= s["overall"] <= 100)
                self.assertEqual(s["overall"] % 5, 0)
                for key in MOD.DIM_KEYS:
                    v = s["scores"][key]
                    self.assertTrue(v == UNAVAIL or 0 <= v <= 7,
                                    (seed, plat, key, v))

    def test_THE_CONTRACT_NEVER_RAISES_ON_A_FUZZED_PAGE(self):
        """End to end, through consensus and into storage."""
        c = fresh_guard()
        for i, seed in enumerate(self.SEEDS[:14]):
            at("2026-09-%02dT12:00:00Z" % (14 + (i % 15)))
            as_sender(H._Addr("0x" + format(1000 + i, "040x")), value=5)
            H.PAGE_MAP[AMAZON_URL] = fuzz_page(seed) + "\npadding" * 40
            try:
                r = c.check_reviews(AMAZON_URL, "")
            except AssertionError:
                continue      # the stub's UNDETERMINED, not a contract fault
            except Exception as e:
                self.fail("check_reviews raised on seed %d: %r" % (seed, e))
            self.assertIn(r["status"], ("OK", "REJECTED"), seed)

    def test_a_page_of_pure_binary_noise_is_survivable(self):
        noise = "".join(chr((i * 7919) % 1114 + 1) for i in range(4000))
        for fn in (MOD._parse_amazon, MOD._parse_gplay, MOD._parse_appstore):
            fn(noise, TODAY)

    def test_a_page_of_one_very_long_line(self):
        line = "x" * 60000
        for fn, plat in ((MOD._parse_amazon, P_AMAZON),
                         (MOD._parse_gplay, P_GPLAY),
                         (MOD._parse_appstore, P_APPSTORE)):
            f = MOD._features(fn(line, TODAY), plat)
            self.assertLessEqual(f["page_chars"], MOD.PAGE_CAP)

    def test_a_page_of_nothing_but_newlines(self):
        for fn in (MOD._parse_amazon, MOD._parse_gplay, MOD._parse_appstore):
            out = fn("\n" * 5000, TODAY)
            self.assertEqual(len(out["reviews"]), 0)

    def test_urls_of_every_shape_are_survivable(self):
        g = _lcg(99)
        for _ in range(200):
            length = next(g) % 120
            u = ""
            for _ in range(length):
                u += ALPHABET[next(g) % len(ALPHABET)]
            plat = MOD._detect_platform(u)
            MOD._canonical(u, plat if plat else P_AMAZON)
            MOD._amazon_asin(u)
            MOD._appstore_id(u)
            MOD._source_url(u)


# ---------------------------------------------------------------------------
# 22. An exhaustive sweep of the ladders' declared input space
#
# The ladder tests above check the interesting points. This walks the whole
# space each ladder can legally be handed and asserts the properties that must
# hold at EVERY point — because an ordinal of 8, at one combination nobody
# spot-checked, is a stored value outside its declared range, which is a
# check that no honest validator can ever agree to.
# ---------------------------------------------------------------------------

class TestExhaustiveSweep(Case):
    def test_timing_is_in_range_everywhere(self):
        for dated in range(3, 15):
            for distinct in range(1, dated + 1):
                for burst in range(1, dated + 1):
                    for span in (0, 7, 14, 15, 30, 31, 90, 364, 365, 4000):
                        v = MOD._dim_timing(
                            vec(reviews_parsed=dated, dated_reviews=dated,
                                distinct_days=distinct, max_same_day=burst,
                                span_days=span), AMZ)
                        self.assertTrue(v == UNAVAIL or 0 <= v <= 7,
                                        (dated, distinct, burst, span, v))

    def test_rating_is_in_range_for_every_histogram(self):
        for p5 in range(0, 101, 2):
            for p1 in range(0, 101 - p5, 5):
                rest = 100 - p5 - p1
                v = MOD._dim_rating(
                    vec(pct_5=p5, pct_4=rest, pct_3=0, pct_2=0, pct_1=p1), AMZ)
                self.assertTrue(v == UNAVAIL or 0 <= v <= 7, (p5, p1, v))

    def test_quality_is_in_range_everywhere(self):
        for med in (0, 50, 99, 100, 199, 200, 349, 350, 599, 600, 20000):
            for sp in range(0, 101, 10):
                for du in range(0, 101, 20):
                    for lx in range(0, 101, 20):
                        v = MOD._dim_quality(
                            vec(median_chars=med, short_pct=sp,
                                dup_open_pct=du, lexical_pct=lx), AMZ)
                        self.assertTrue(0 <= v <= 7, (med, sp, du, lx, v))

    def test_credibility_is_in_range_on_both_bases(self):
        for dims in (AMZ, GP):
            vers = list(range(0, 101, 5))
            if dims is GP:
                vers.append(UNAVAIL)
            for ver in vers:
                for weak in range(0, 101, 10):
                    for dist in range(0, 101, 20):
                        v = MOD._dim_credibility(
                            vec(verified_pct=ver, weak_handle_pct=weak,
                                distinct_names_pct=dist), dims)
                        self.assertTrue(v == UNAVAIL or 0 <= v <= 7,
                                        (ver, weak, dist, v))

    def test_THE_IDENTITY_BASIS_NEVER_REACHES_SEVEN_ANYWHERE(self):
        """Not at one spot-checked point — at every point in the space. The top
        of that ladder reads "established reviewers", and no page without a
        purchase signal can support the claim."""
        for ver in (UNAVAIL, 0, 50, 100):
            for weak in range(0, 101, 5):
                for dist in range(0, 101, 5):
                    for dims in (GP, AS_):
                        v = MOD._dim_credibility(
                            vec(verified_pct=ver, weak_handle_pct=weak,
                                distinct_names_pct=dist), dims)
                        if v != UNAVAIL:
                            self.assertLessEqual(v, 6, (ver, weak, dist, v))

    def test_engagement_is_in_range_everywhere(self):
        for dims in (AMZ, GP):
            for hp in range(0, 101, 5):
                for tot in (0, 49, 50, 10 ** 9):
                    for ph in (0, 1):
                        for rs in (0, 1):
                            v = MOD._dim_engagement(
                                vec(helpful_pct=hp, helpful_total=tot,
                                    has_photos=ph, has_response=rs), dims)
                            self.assertTrue(v == UNAVAIL or 0 <= v <= 7,
                                            (hp, tot, ph, rs, v))

    def test_the_overall_is_always_a_multiple_of_five_in_range(self):
        for plat in MOD.PLATFORMS:
            for p5 in range(0, 101, 10):
                for med in (0, 200, 600, 3000):
                    for weak in (0, 50, 100):
                        f = vec(pct_5=p5, pct_4=100 - p5, pct_3=0, pct_2=0,
                                pct_1=0, median_chars=med, weak_handle_pct=weak)
                        if plat != P_AMAZON:
                            for k in ("pct_5", "pct_4", "pct_3", "pct_2",
                                      "pct_1", "verified_pct"):
                                f[k] = UNAVAIL
                        if plat == P_APPSTORE:
                            f["helpful_pct"] = UNAVAIL
                            f["helpful_total"] = UNAVAIL
                        s = MOD._score(f, plat)
                        self.assertEqual(s["overall"] % 5, 0, (plat, s))
                        self.assertTrue(0 <= s["overall"] <= 100, (plat, s))
                        self.assertIn(s["trust_level"], MOD.TRUST_LEVELS)

    def test_every_scored_result_is_coherent_against_itself(self):
        """`_coherent` runs the rubric again on the leader's own vector. If the
        two could ever disagree, an honest leader would be voted down."""
        for plat in MOD.PLATFORMS:
            for p5 in range(0, 101, 20):
                f = vec(pct_5=p5, pct_4=100 - p5, pct_3=0, pct_2=0, pct_1=0)
                if plat != P_AMAZON:
                    for k in ("pct_5", "pct_4", "pct_3", "pct_2", "pct_1",
                              "verified_pct"):
                        f[k] = UNAVAIL
                if plat == P_APPSTORE:
                    f["helpful_pct"] = UNAVAIL
                    f["helpful_total"] = UNAVAIL
                scored = MOD._score(f, plat)
                out = {"ok": True, "url_key": "X:y:z", "platform": plat,
                       "title": "t", "features": f,
                       "scores": scored["scores"],
                       "overall": scored["overall"],
                       "trust_level": scored["trust_level"],
                       "available_weight": scored["available_weight"],
                       "credibility_basis": scored["credibility_basis"]}
                out["content_hash"] = MOD._digest(out, f)
                self.assertTrue(MOD._coherent(out), (plat, p5))


# ---------------------------------------------------------------------------
# 23. The two reasons a dimension can be unavailable are different claims
#
# Google Play genuinely does not publish a star histogram — a fact about the
# PLATFORM. An Amazon page that rendered without its review list publishes all
# five dimensions and did not serve them that time — a fact about ONE FETCH.
# Printing the first sentence about the second is a false statement about
# Amazon, on a page about somebody's product.
# ---------------------------------------------------------------------------

class TestUnavailabilityReason(Case):
    def setUp(self):
        super().setUp()
        self.c = fresh_guard()

    def _record_for(self, url, page=None, sender=ALICE):
        if page is not None:
            key = {AMAZON_URL: AMAZON_URL, GPLAY_URL: GPLAY_FETCH,
                   APPSTORE_URL: APPSTORE_FETCH}[url]
            H.PAGE_MAP[key] = page
        as_sender(sender)
        self.c.check_reviews(url, "")
        return self.c.get_check_by_url(url)

    def test_A_PLATFORM_THAT_DOES_NOT_PUBLISH_SAYS_SO(self):
        rec = self._record_for(GPLAY_URL)
        self.assertIsNone(rec["scores"]["rating_distribution"])
        self.assertEqual(rec["labels"]["rating_distribution"],
                         "not published by this platform")
        self.assertEqual(rec["unavailable_because"], "platform")

    def test_A_TRUNCATED_PAGE_DOES_NOT_BLAME_THE_PLATFORM(self):
        """The live shape: amazon.com/dp rendered 14,000 characters and stopped
        before its review list. Amazon publishes all five dimensions; it simply
        did not serve them. The record must not say otherwise."""
        text = fixture("amazon_echo_dot")
        cut = text[: text.find("Top reviews from")]
        rec = self._record_for(AMAZON_URL, cut)
        self.assertEqual(rec["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertEqual(rec["unavailable_because"], "page")
        for key in ("timing_pattern", "review_quality",
                    "reviewer_credibility", "engagement_signals"):
            self.assertIsNone(rec["scores"][key], key)
            self.assertEqual(rec["labels"][key],
                             "the page did not render its reviews", key)
            self.assertNotIn("platform", rec["labels"][key], key)

    def test_the_histogram_that_DID_render_still_reads_normally(self):
        """The same record: four dimensions unavailable for a page reason, and
        the one that rendered scored normally. The label must not be blanket."""
        text = fixture("amazon_echo_dot")
        cut = text[: text.find("Top reviews from")]
        rec = self._record_for(AMAZON_URL, cut)
        self.assertIsNotNone(rec["scores"]["rating_distribution"])
        self.assertIn(rec["labels"]["rating_distribution"],
                      MOD.BUCKETS["rating_distribution"])
        self.assertEqual(rec["evidence"]["rating_histogram"]["5"], 83)

    def test_a_full_page_labels_every_scored_dimension_with_its_bucket(self):
        rec = self._record_for(AMAZON_URL)
        self.assertEqual(rec["trust_level"], MOD.T_AUTHENTIC)
        self.assertEqual(rec["unavailable_because"], "platform")
        for key in MOD.DIM_KEYS:
            self.assertIsNotNone(rec["scores"][key], key)
            self.assertIn(rec["labels"][key], MOD.BUCKETS[key], key)

    def test_an_app_store_record_separates_its_two_kinds(self):
        """The App Store page is the interesting mixed case when it is short:
        rating_distribution and engagement are PLATFORM silences whatever
        happens, while timing, quality and credibility are page shortfalls."""
        text = fixture("appstore_whatsapp")
        cut = text[: text.find("Ratings & Reviews") + 40]
        rec = self._record_for(APPSTORE_URL, cut + "\npadding" * 60)
        self.assertEqual(rec["trust_level"], MOD.T_INCONCLUSIVE)
        self.assertEqual(rec["labels"]["rating_distribution"],
                         "not published by this platform")
        self.assertEqual(rec["labels"]["engagement_signals"],
                         "not published by this platform")
        for key in ("timing_pattern", "review_quality",
                    "reviewer_credibility"):
            self.assertEqual(rec["labels"][key],
                             "the page did not render its reviews", key)

    def test_the_label_never_claims_a_platform_is_silent_when_it_is_not(self):
        """Swept across every platform and both page shapes."""
        cases = [
            (AMAZON_URL, P_AMAZON, fixture("amazon_echo_dot")),
            (GPLAY_URL, P_GPLAY, fixture("gplay_whatsapp")),
            (APPSTORE_URL, P_APPSTORE, fixture("appstore_whatsapp")),
        ]
        for i, (url, plat, full) in enumerate(cases):
            for j, page in enumerate((full, full[: len(full) // 4])):
                c = fresh_guard()
                key = {AMAZON_URL: AMAZON_URL, GPLAY_URL: GPLAY_FETCH,
                       APPSTORE_URL: APPSTORE_FETCH}[url]
                H.PAGE_MAP[key] = page + "\npadding" * 60
                as_sender(H._Addr("0x" + format(700 + i * 4 + j, "040x")))
                try:
                    c.check_reviews(url, "")
                except AssertionError:
                    continue
                rec = c.get_check_by_url(url)
                if not rec.get("found"):
                    continue
                dims = MOD.PLATFORM_DIMS[plat]
                for dk in MOD.DIM_KEYS:
                    if rec["labels"][dk] != "not published by this platform":
                        continue
                    self.assertFalse(
                        dims[MOD.DIM_FLAG[dk]],
                        "%s: claimed %s does not publish %s, but it does"
                        % (url, plat, dk))

    def test_unavailable_because_is_always_one_of_two_words(self):
        for url, page in ((AMAZON_URL, None), (GPLAY_URL, None),
                          (APPSTORE_URL, None)):
            c = fresh_guard()
            as_sender(ALICE)
            c.check_reviews(url, "")
            rec = c.get_check_by_url(url)
            self.assertIn(rec["unavailable_because"], ("page", "platform"))

if __name__ == "__main__":
    unittest.main(verbosity=1, buffer=False)
