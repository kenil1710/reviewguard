# ReviewGuard

**A fake-review detector that any contract can read.**

Submit the URL of a product's review page. GenLayer validators each load that
page in a real browser, independently, and must agree on **every number** before
anything is written down. The result is a 0–100 trust score, five dimension
ordinals and the evidence behind them — none of which any single party can move.

| | |
|---|---|
| **Network** | GenLayer Studio Dev (chain `61997`) |
| **ReviewGuard** | [`0x37B5C64586d7d214D3aA45aA5a0Fdd5cc5f34c30`](https://explorer-studio-dev.genlayer.com/address/0x37B5C64586d7d214D3aA45aA5a0Fdd5cc5f34c30) |
| **MarketplaceConsumer** | [`0x0E4a16a697955d0001c64358B14C3AF156889822`](https://explorer-studio-dev.genlayer.com/address/0x0E4a16a697955d0001c64358B14C3AF156889822) |
| **Rubric** | `1.0.0` · fee `0` |
| **Offline tests** | 410, stdlib only |
| **Audit** | `bash tools/audit.sh` — 80 checks |

---

## The measurement came first

Before a line of scoring was written, a throwaway probe
(`contracts/_render_probe.py`) was deployed to studio-dev and pointed at
**fourteen** review sites to answer one question: *does a validator actually see
the reviews?*

**Eleven do not.**

| | |
|---|---|
| Trustpilot | `403` behind an AWS WAF interstitial; `render()` fails outright |
| Yelp | `403` with a captcha challenge |
| Google Maps | renders **234 characters** of map chrome and no reviews |
| Walmart, Newegg | bot walls (`Robot or human?`, CAPTCHA) |
| Best Buy, Etsy, TripAdvisor, G2, IMDb, Home Depot | `WEBPAGE_LOAD_FAILED` |
| Goodreads | `403 Forbidden` (13 characters) |
| Target | renders, but every product reads `Item not available` |
| Steam | renders aggregate counts only — no review bodies |

**Three do**, and only those three are offered:

| Platform | What it publishes | Measurable weight |
|---|---|---|
| **Amazon** `/dp/{ASIN}` | rating histogram, dates, verified-purchase flags, full bodies, helpful votes, photos | **100 / 100** |
| **Google Play** | dates, bodies, helpful counts, aggregate rating | **80 / 100** |
| **Apple App Store** | dates, bodies, aggregate rating | **65 / 100** |

Every figure above is a transaction hash away in **[`docs/PROBE.md`](docs/PROBE.md)**.
A platform that cannot be read is worse than one that is absent, because a
blocked page and an empty page look identical — and the contract would otherwise
report "no manipulation found" about a page it never saw.

---

## How the score is built

Five dimensions, weighted to 100, each an ordinal 0–7 where **0 is always the
worst outcome**.

| Dimension | Weight | What it reacts to |
|---|---|---|
| **Timing pattern** | 25 | Reviews clustered on a few dates versus spread over years |
| **Rating distribution** | 20 | A histogram with a real negative tail and a populated middle |
| **Review quality** | 20 | Median length, vocabulary variety, duplicate opening lines |
| **Reviewer credibility** | 20 | Verified-purchase share, or reviewer-identity shape |
| **Engagement signals** | 15 | Helpful votes, customer photos, seller responses |

Weighted, scaled to 0–100, quantised to the nearest 5:

**AUTHENTIC** ≥ 70 · **SUSPICIOUS** 40–69 · **MANIPULATED** < 40 ·
**INCONCLUSIVE** when the evidence will not support a call.

---

## The eight rules

Each one is a past rejection written down so it cannot happen again. They open
`contracts/ReviewGuard.py`; the reasoning is in
**[`contracts/NOTES.md`](contracts/NOTES.md)**.

1. **Consensus binds every stored value** — twenty-two vector integers, three
   identity strings and a content hash. `_write` reads only from the agreed
   object and re-runs the rubric rather than storing the leader's numbers.
2. **A payable method may never raise** — every refusal credits a refund and
   returns `{"status": "REJECTED", reason}`.
3. **No counter moves before a path that can still refuse.**
4. **The fee is snapshotted into the record at creation.**
5. **A written check is immutable** — a re-check appends, it never edits.
6. **The owner cannot freeze user money** — refunds and reads are ungated on
   pause; `settle_stalled` is permissionless.
7. **Evidence that is not there is UNAVAILABLE, never zero.**
8. **A leader cannot forge a value** — `_coherent` proves the arithmetic before
   any vote, `_agrees` compares every field.

### Rule 7 earned its keep, live

Three hours into the build, live Amazon pages began rendering **14,163
characters and stopping before the review list** — down from 37,914 with eight
reviews the same morning. Raising the wait from 6s to 20s changed the length by
81 characters, so it was not a timing problem (docs/PROBE.md §6).

ReviewGuard returned **INCONCLUSIVE**. A rubric that scored what it had would
have taken the one surviving dimension and called a product with 1,037,930
ratings *manipulated*, on a page that renders perfectly in a browser.

It was still not explicable enough — `0 reviews parsed` reads the same for *a
product nobody has reviewed* and *a page that was cut short* — so `page_chars`
and `reviews_section` joined the consensus axis and the contract now answers:

> *the page rendered 14000 characters and stopped before its review list, so
> there was nothing to read*

---

## Reading it from your own contract

```python
@gl.contract.interface
class IReviewGuard:
    class View:
        def get_trust_summary(self, url: str) -> typing.Any: ...
    class Write:
        pass  # a consumer must never spend the oracle's rate limit

summary = IReviewGuard(ORACLE).view().get_trust_summary(url)
if not summary.get("found"):
    return self._refuse("never checked")            # not "score 0"
if summary["trust_level"] != "AUTHENTIC":
    return self._refuse(summary["trust_level"])     # INCONCLUSIVE included
if now - summary["checked_at"] > MAX_AGE:
    return self._refuse("stale")                    # your policy, not the oracle's
```

`get_trust_summary` **never raises** — use it on any path that takes money.
`require_authentic` reverts unless the latest check says AUTHENTIC;
`require_not_manipulated` is the looser variant and still reverts on
INCONCLUSIVE.

`contracts/MarketplaceConsumer.py` is the worked example: it lists only
authentic products, pins the check id and content hash that admitted each one,
applies **its own** staleness rule, refunds every refusal, and logs them so the
guard can be audited.

---

## Layout

```
contracts/
  ReviewGuard.py            the oracle
  MarketplaceConsumer.py    the worked consumer
  NOTES.md                  why it is built this way, and the hazards
  _render_probe.py          throwaway: which platforms can be read
  _wait_probe.py            throwaway: does a longer wait help? (no)
test/
  test_logic.py             410 offline tests, stdlib only
  harness.py                the v0.6 runtime stub
  fixtures/*.txt            real rendered pages, pulled off studio-dev
docs/
  PROBE.md                  every platform measurement, with evidence
  evidence.json             live on-chain state
tools/
  gl.sh                     fee-aware deploy and write
  audit.sh                  80 mechanical checks
  seed.sh                   real checks against studio-dev
frontend/                   Next.js 16 + Tailwind 4
```

## Running it

```bash
python3 test/test_logic.py     # 410 tests, no network
bash tools/audit.sh            # 80 checks
./tools/gl.sh deploy contracts/ReviewGuard.py
cd frontend && npm install && npm run dev
```

---

## What this is not

ReviewGuard reports what a public review page shows — the shape of the dates,
the histogram, the writing, the reviewer identities, the engagement. Those
patterns correlate with manipulation; they do not prove it, and a legitimate
seller can land in the middle band for innocent reasons.

**It is evidence about a page, not an accusation against a person.**
