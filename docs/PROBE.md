# Render probe — which platforms can a validator actually see?

Everything below was **measured** on studio-dev (chain 61997) with a throwaway
contract, `contracts/_render_probe.py`, deployed at
`0x183a0f7B71f83045aD25Bdb520FD10646c474b79`. No platform claim in this project
rests on anything but a transaction hash.

The probe measured every URL three ways, because four different failures hide
behind "it didn't work" and they call for opposite responses:

| what happened | what it means | response |
|---|---|---|
| `403` / `WEBPAGE_LOAD_FAILED` | egress or WAF block | platform is impossible |
| `200` + captcha text | bot wall | platform is impossible |
| `200`, real HTML, no review text | JS-only shell | `render()` may fix it |
| review text present and countable | works | ship it |

---

## 1. The verdict, first

Three platforms ship. Eleven do not.

| platform | plain GET | `web.render(mode="text")` | shipped |
|---|---|---|---|
| **Amazon** `/dp/{ASIN}` | 404 on a dead ASIN | **37,914 chars, full review bodies** | ✅ |
| **Google Play** | — | **5,722 chars, 3 review bodies + helpful counts** | ✅ |
| **Apple App Store** | — | **11,636 chars, ~10 review bodies** | ✅ |
| Trustpilot | `403` AWS WAF interstitial | `WEBPAGE_LOAD_FAILED` | ❌ |
| Yelp | `403` + `captcha` ×2 | `WEBPAGE_LOAD_FAILED` | ❌ |
| Google Maps | `200`, 219 KB, `enable javascript` | renders **234 chars of map chrome** | ❌ |
| Walmart | — | `Robot or human?` bot wall | ❌ |
| Best Buy | — | `WEBPAGE_LOAD_FAILED` | ❌ |
| Etsy | — | `WEBPAGE_LOAD_FAILED` | ❌ |
| TripAdvisor | — | `WEBPAGE_LOAD_FAILED` | ❌ |
| G2 | — | `WEBPAGE_LOAD_FAILED` | ❌ |
| IMDb | — | `WEBPAGE_LOAD_FAILED` | ❌ |
| Home Depot | — | `WEBPAGE_LOAD_FAILED` | ❌ |
| Newegg | — | `Are you a human?` + CAPTCHA | ❌ |
| Goodreads | — | `403 Forbidden` (13 chars) | ❌ |
| Target | — | renders, but every product is `Item not available` | ❌ |
| Steam | — | renders 5,114 chars — **aggregates only, no review bodies** | ❌ |
| Chrome Web Store | — | renders 2,413 chars — too thin to score | ❌ |

`https://example.com` was rendered as a control in the same transaction that
failed on Trustpilot and Yelp, and returned its 129 characters normally. The
failures are the platforms, not the runner.

---

## 2. The four URLs the brief named

### 2.1 Trustpilot — `https://www.trustpilot.com/review/amazon.com`

**Blocked.** Plain GET returns `403` and a 991-byte AWS WAF interstitial:

```
<!doctype html><html lang="en"><head><meta charset="UTF-8" />…
<title>Verifying Connection</title>
<link rel="stylesheet" href="/interstitial/interstitial.css" />
<script src="https://a7d575be72e8.edge.sdk.awswaf.com/…
```

`web.render(mode="text", wait_after_loaded="5s")` raises `WEBPAGE_LOAD_FAILED`.
Retried at `8s` against `https://www.trustpilot.com/review/www.amazon.com` —
same. The WAF challenge is never cleared, so **zero review data is visible**.

### 2.2 Yelp — `https://www.yelp.com/biz/starbucks-new-york`

**Blocked.** Plain GET returns `403` and a 776-byte challenge containing
`captcha` twice:

```
<html lang="en"><head><title>yelp.com</title>…
<p id="cmsg">Please enable JS and disable any ad blocker</p>
```

`render()` raises `WEBPAGE_LOAD_FAILED`. **Zero review data.**

### 2.3 Google Maps — `https://www.google.com/maps/place/Starbucks…`

**Unusable, though not blocked.** Plain GET returns `200` and 219,687 bytes —
but the body carries `enable javascript` and no structured review data, and the
`review`/`star` hits are navigation labels.

`render()` succeeds and returns **234 characters**, all of it map chrome:

```
Directions / Saved / Recents / Get app / Nearby / Send to phone / Share
About this data / Collapse side panel / Sign in / Layers
Map data ©2026 Google… / 50 mi
```

The place panel never populates for this client. A platform that renders the
frame and not the content is worse than one that 403s, because it looks like a
success. **Dropped.**

### 2.4 Amazon — `https://www.amazon.com/dp/{ASIN}`

**Works, and works best of the four.** Measured on `B07FZ8S74R`:

- plain GET on a *dead* ASIN (`B08N5WRWNW`) → `404`, a 2,296-byte "Page Not
  Found". Useful: the 404 path is distinguishable.
- `render(mode="text", wait_after_loaded="6s")` → **37,914 characters** of
  page text including every element the five dimensions need.

Two Amazon URL shapes were tested and they do **not** behave the same:

| URL | result |
|---|---|
| `amazon.com/dp/B07FZ8S74R` | 37,914 chars, reviews included ✅ |
| `amazon.com/product-reviews/B07FZ8S74R` | **607 chars — a sign-in wall** ❌ |

So ReviewGuard accepts `/dp/` and canonicalises everything to it. The dedicated
reviews page is behind auth and must never be fetched.

---

## 3. What the three shipped platforms actually carry

This is the table every extraction rule in `contracts/ReviewGuard.py` is written
against. Quoted strings are verbatim from the rendered text.

### 3.1 Amazon — complete

```
Customer reviews
4.7 out of 5 stars
4.7 out of 5
1,037,930 global ratings
5 star
83%
4 star
12%
3 star
4%
2 star
0%
1 star
1%
…
Reviews with images
See all photos
Top reviews from the United States
Tango's product reviews
5 out of 5 stars
The device that just keeps getting better and better with each revision
Reviewed in the United States on December 14, 2019
Verified Purchase

Okay so first off I'd like to say that I had a gen 1 echo…

Read more
Helpful
Report
```

Every dimension has a basis:

| dimension | evidence on the page |
|---|---|
| timing | `Reviewed in the United States on December 14, 2019` |
| rating distribution | the `5 star 83% … 1 star 1%` histogram |
| review quality | full review bodies, thousands of characters |
| reviewer credibility | `Verified Purchase`, distinct reviewer names |
| engagement | `Helpful`, `N people found this helpful`, `Reviews with images` |

### 3.2 Google Play — no rating histogram

```
4.6
239M reviews
5
4
3
2
1
Jonathan Spencer
more_vert
August 28, 2026
The most useless app I've encountered since apps were invented…
6 people found this review helpful
Did you find this helpful?
```

The histogram **labels** render (`5 4 3 2 1`) but the bar values do not — they
are drawn, not written. So `rating_distribution` is **UNAVAILABLE** on Google
Play, and the contract says so rather than inventing a number from the average.

Only **three** review bodies render. That is thin, and `reviews_parsed` is
carried in the evidence so a reader can see it.

### 3.3 Apple App Store — no per-review rating, no engagement

```
Ratings & Reviews
4.7
out of 5
19M Ratings
WhatsApp not bad
Jan 21
Ed Bradway "Dad Warrior"
WhatsApp's not bad at all—it's actually great for what it does…
more
Potential improvements
06/14/2023
Lol_hahahahahah
I love the app and it's my main communication method…
```

Two date formats appear on the same page — `Jan 21` for recent reviews and
`06/14/2023` for older ones. Both are parsed.

There is no per-review star rating, no helpful vote and no developer response in
the rendered text, so `rating_distribution` and `engagement_signals` are both
**UNAVAILABLE** on this platform.

### 3.4 The availability matrix, which is a contract constant

| dimension | weight | Amazon | Google Play | App Store |
|---|---|---|---|---|
| timing_pattern | 25 | ✅ | ✅ | ✅ |
| rating_distribution | 20 | ✅ | ❌ | ❌ |
| review_quality | 20 | ✅ | ✅ | ✅ |
| reviewer_credibility | 20 | ✅ *verified purchase* | ✅ *identity shape* | ✅ *identity shape* |
| engagement_signals | 15 | ✅ | ✅ | ❌ |
| **available weight** | | **100** | **80** | **65** |

A dimension that is unavailable carries **no weight** and is reported as
`UNAVAILABLE`, never as zero. Scoring an absent feed as zero would defame a
product for a gap in somebody else's page. Below 60 available weight the whole
check is `INCONCLUSIVE`.

---

## 4. Drift — the number the consensus design rests on

`_agrees` demands exact equality on every compared field, so the question is how
far two validators' fetches diverge. Measured by running the same extraction in
**three separate transactions** (different leaders) against the same URL:

| field | run 1 | run 2 | run 3 |
|---|---|---|---|
| `census.len` | 37914 | 37914 | 37914 |
| `census.digits` | 459 | 459 | 459 |
| `census.lines` | 756 | 756 | 756 |
| `anchor_top_reviews` | 11537 | 11537 | 11537 |
| `rate_5_star` | 18 | 18 | 18 |
| `sig_verified` | 8 | 8 | 8 |
| `sig_helpful` | 15 | 15 | 15 |
| body sample at ⅓ offset | identical | identical | identical |

**Byte-identical.** Google Play was measured twice and was likewise identical on
every field.

This is a happy finding and it is **not** a licence to compare raw values. The
stability is somebody else's cache, it will expire, and "Top reviews" rotates.
Every figure that crosses consensus is therefore still quantised — ordinals to
eight buckets, counts to three significant figures, percentages to the nearest
five — exactly as if the drift had been large. The tolerance lives in the
quantisation and never in the comparison, because a comparison with a tolerance
in it means two different accepted outputs for one request, and then which one
is the check?

---

## 5. Hazards measured here, not assumed

- **`str.replace()` is rejected by the runner.** The first probe carried
  `pat.replace(" ", "_")` and had to be rewritten around a character loop before
  it would deploy. `tools/audit.sh` walks the AST of both contracts for it.
- **A deploy without a fee *distribution* reverts.** `--fee-value` alone gives
  `FeeValueMustBeNonZero(1)` on studio-dev; the `distribution` object from
  `genlayer estimate-fees --json` must travel with it. Every deploy and write in
  this project goes through `tools/gl.sh` so that this is not something to
  remember.
- **`render()` has no status code.** It returns the body on success and *raises*
  on everything else, with the reason in the exception text. `WEBPAGE_LOAD_FAILED`
  is the only string a blocked platform ever produces, so a blocked platform and
  a timed-out one are indistinguishable — which is why a failed fetch settles
  nothing rather than settling low.
- **A `float` in a nondet return is not calldata encodable.** Every number that
  crosses the consensus boundary is an `int`, a `str` or a `bool` first.
- **The runner header is exactly two lines.** GenVM parses the contiguous leading
  `#` block as the header; a third comment line there makes the contract
  undeployable with no error but `invalid_contract`.

---

## 6. Follow-up: Amazon degraded mid-build, and what that proved

Three hours after §4 was written, a live `check_reviews` against
`amazon.com/dp/B07FZ8S74R` — the same URL the fixture was captured from —
returned `reviews_parsed: 0`. The title, the average, the total ratings and the
full `83/12/4/0/1` histogram all still parsed. Only the individual reviews were
gone.

A second ASIN (`B0BDHWDR12`, AirPods Pro) behaved identically, so it was not
per-product. A third dedicated probe (`contracts/_wait_probe.py`, deployed at
`0xe06c370eC2db04167afEE97234588112bDC433BF`) measured the one variable the
contract controls:

| `wait_after_loaded` | rendered length | `Top reviews from` found | `Verified Purchase` count |
|---|---|---|---|
| 6s | 14,163 | **no** (`-1`) | 0 |
| 12s | 14,210 | **no** (`-1`) | 0 |
| 20s | 14,129 | **no** (`-1`) | 0 |

Against 37,914 characters with eight reviews earlier the same day.

**More than tripling the wait changed the length by 81 characters.** It is not a
timing problem — the page Amazon serves this client simply ends before the
review section. Raising `RENDER_WAIT` would have cost every check an extra
fourteen seconds and fixed nothing.

### What this is evidence *for*

Three design decisions that looked cautious in the morning turned out to be the
only reason the afternoon was survivable:

1. **Rule 7 held.** ReviewGuard reported `INCONCLUSIVE` on all three checks. A
   rubric that scored what it had would have taken the one surviving dimension —
   a 20-weight histogram — and called a product with 1,037,930 ratings
   *manipulated*, on a page that renders fine in a browser.
2. **The failure was visible, not silent.** `is_authentic` answers false,
   `require_authentic` reverts, and `MarketplaceConsumer` refuses INCONCLUSIVE
   **by name** rather than by its zero score.
3. **The inconclusive verdict was still not explicable enough.** `0 reviews
   parsed` reads the same for a product nobody has reviewed and a page that was
   cut short, and those call for opposite responses — believe it, versus check
   again later. So two fields were added to the consensus axis, `page_chars`
   (quantised to 500) and `reviews_section`, and `_why_inconclusive` now
   answers:

   > *the page rendered 14000 characters and stopped before its review list, so
   > there was nothing to read*

`test_THE_TRUNCATED_LIVE_AMAZON_PAGE_IS_INCONCLUSIVE_NOT_MANIPULATED` pins the
exact shape studio-dev returned — summary present, review list absent — so this
cannot regress into a verdict.

### What it means for the platform table

Amazon stays supported. Its page shape, parser and evidence are unchanged and
correct, and the earlier fixtures prove the full read works when the platform
serves it; `test/fixtures/amazon_echo_dot.txt` is that page. What varies is
Amazon, not ReviewGuard — and when it serves a short page, the honest answer is
the one the contract gives.

---

## 7. What a failed round actually looks like

Recorded because it is the case the refund path exists for, and because it
happened on the live site rather than in a test.

The production `/api/check` submitted a check of an App Store listing. The
transaction settled and **no record appeared**. The receipt says why:

```
status:  'Finalized · Validators Timeout'
outcome: 'Validators Timeout'
leader result: { status: 'contract_error',
                 payload: 'GenVM internal error: GenVM internal error' }
validators:    { execution_result: 'ERROR',
                 stderr: 'Validator execution cancelled after quorum' }
```

The leader's execution died inside GenVM. Nothing about ReviewGuard's rubric
was involved, and **nothing was stored** — which is the whole point. A round
that does not settle applies no state, so:

- no `check_id` was consumed;
- no counter moved;
- the caller's deposit was never at risk;
- the in-flight marker was cleared by the same exit path, so the URL was
  immediately checkable again.

The very next submission of a different page, through the same route, returned
`{"ok": true, "check_id": 4, "trust_level": "AUTHENTIC", "overall": 80}` in
**69 seconds** end to end.

Two things were fixed on the back of it, both in the front end rather than the
contract:

1. **The fee distribution is not optional.** The first production submission
   reverted with `FeeValueMustBeNonZero(1)` before the contract ever ran —
   `genlayer-js` needs `fees: {distribution, feeValue}`, exactly as the CLI
   needs `--fees` alongside `--fee-value`.
2. **A settled round is not the same moment as a readable one.** The route read
   the record once, got "not found", and told the visitor their check had
   failed when it had in fact worked. It now polls for up to two minutes and
   drops its memo each time, so it is watching the chain rather than a cached
   answer from thirty seconds ago.

---

## 8. Amazon recovered, and the evidence field proved its worth

Roughly ninety minutes after §6, the seeding run reached the same Echo Dot URL
again. This is what came back:

```
title:            Echo Dot (3rd Gen, 2018 release) - Smart speaker with Alexa
page_chars:       38500          (was 14000)
reviews_section:  true           (was false)
reviews_parsed:   8              (was 0)
dated_reviews:    8
verified_pct:     100
has_photos:       true
available_weight: 100/100
overall:          80
trust_level:      AUTHENTIC
```

The degraded window was Amazon's and it was temporary. Three things are now
settled by measurement rather than by argument:

1. **The Amazon parser works on live data**, not only on the captured fixture.
   Eight reviews, every one with a date and a verified-purchase flag, customer
   photos detected, the full rubric measurable.
2. **The conservative path was right.** For ninety minutes ReviewGuard said
   INCONCLUSIVE about a product it now scores 80/100 AUTHENTIC. A rubric that
   had scored the partial page would have published a verdict it then had to
   contradict.
3. **`page_chars` is the field that makes the two distinguishable.** 14,000
   against 38,500, on the same URL, four hours apart. Without it the record
   would say "0 reviews parsed" in one case and "8 reviews parsed" in the other
   with nothing to explain the gap.

All three platforms have now produced live, verified AUTHENTIC checks on
studio-dev with the full evidence trail: Amazon at 100/100 measurable weight,
Google Play at 80, the App Store at 65.

---

## 9. A live INCONCLUSIVE, with the evidence that explains it

The tenth seeded check, `amazon.com/dp/B0BDHWDR12` (AirPods Pro 2nd Gen). This
is what the contract stored:

```
page_chars:        14000        the truncated shape from §6, again
reviews_section:   false        the review list was not on the page
reviews_parsed:    0
avg_rating_x10:    47           the summary block DID render
total_ratings:     57900
rating_histogram:  87 / 7 / 3 / 0 / 3
available_weight:  20 / 100     only rating_distribution was measurable
overall:           0
trust_level:       INCONCLUSIVE
```

An 87% five-star histogram on 57,900 ratings, and ReviewGuard declined to score
it. That is the whole design in one record:

- One dimension was measurable out of five — **20 of 100**, well under the
  `MIN_AVAILABLE_WEIGHT` floor of 60.
- A rubric willing to score what it had would have published a verdict from a
  single dimension on a page whose review list it never saw.
- `page_chars: 14000` against the 38,500 the Echo Dot returned an hour earlier
  is what lets a reader tell *this product has no reviews* from *we could not
  see this product's reviews*.
- `is_authentic` returns **false** for it, `require_authentic` reverts, and
  `MarketplaceConsumer` refuses it by name — so nothing downstream mistakes the
  absence of a score for a passing one.
- `get_stats().manipulation_rate_pct` excludes it from the denominator: nine
  conclusive checks, zero manipulated, **0%**. Had it been counted as "not
  manipulated" the headline would have improved because the oracle failed.

Ten checks across three platforms: **nine AUTHENTIC scoring 75-85, one
INCONCLUSIVE**, every one of them recomputing clean from its own stored
evidence.

---

## 10. Two rounds in six timed out, and that is the case the rules exist for

The re-seeding run against rubric 1.0.1 hit `VALIDATORS_TIMEOUT` twice in its
first six submissions:

```
Error: Write 0x99a63ded…5ff9 transaction was decided as VALIDATORS_TIMEOUT;
       leader execution result: FINISHED_WITH_RETURN.
```

The **leader finished with a return** and the validators did not answer in time.
This is the worst-shaped failure available: the leader had a complete, valid
result in hand and the round still did not settle.

What the contract did about it, verified on chain afterwards:

| | |
|---|---|
| `get_trust_summary(that URL)` | `{"found": false, "reason": "never checked"}` |
| record written | none |
| `check_id` consumed | none |
| counters moved | none |
| in-flight marker left set | no — the URL is immediately checkable again |

A round that does not settle applies **no state at all**, so the usual case
needs nothing: no partial record, no half-consumed id, no lock. `settle_stalled`
exists for the narrower case where a marker survives, and it is permissionless
precisely so that an owner cannot turn a transient network failure into
indefinite censorship of one page.

The rate at which this happens is a property of studio-dev, not of ReviewGuard —
but it is the reason a payable path may never raise. Had `check_reviews`
reverted on the way to consensus, the caller's deposit would have stayed in the
contract with no record saying whose it was. Instead the round simply did not
happen, and nothing was owed to anyone.
