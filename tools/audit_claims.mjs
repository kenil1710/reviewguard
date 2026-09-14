/**
 * Every claim this project makes, checked against the chain.
 *
 * The README, the docs page and the landing copy all assert things about what
 * ReviewGuard does. This reads the deployed contract and fails if any of them
 * has drifted — so a sentence nobody updated becomes a build failure rather
 * than a lie somebody finds later.
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { readFileSync } from "node:fs";

const D = JSON.parse(
  readFileSync(new URL("../deployments.json", import.meta.url), "utf8"),
).deployments.studiodev;
const ORACLE = D.ReviewGuard.address;
const CONSUMER = D.MarketplaceConsumer.address;
const SITE = process.env.SITE ?? "https://reviewguard-gl.vercel.app";
const client = createClient({ chain: studioDevnet });

const GREEN = "[32m";
const RED = "[31m";
const BOLD = "[1m";
const OFF = "[0m";

let pass = 0;
let fail = 0;
const ok = (m) => {
  pass++;
  console.log(`  ${GREEN}PASS${OFF} ${m}`);
};
const bad = (m, d) => {
  fail++;
  console.log(`  ${RED}FAIL${OFF} ${m}${d ? "\n       " + d : ""}`);
};
const head = (m) => console.log(`\n${BOLD}${m}${OFF}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Studio meters thirty reads a minute per caller. This audit makes several per
// check, so it paces itself rather than spending the budget and then reporting
// the rate limiter's refusals as audit failures.
let lastRead = 0;
const MIN_GAP_MS = 2100;

async function read(address, fn, args = []) {
  for (let i = 1; i <= 6; i++) {
    const since = Date.now() - lastRead;
    if (since < MIN_GAP_MS) await sleep(MIN_GAP_MS - since);
    lastRead = Date.now();
    try {
      return await client.readContract({ address, functionName: fn, args });
    } catch (e) {
      if (i === 6) throw e;
      await sleep(/rate limit/i.test(String(e?.message)) ? 8000 : 1000 * i);
    }
  }
}

console.log(`\n${BOLD}ReviewGuard claims audit${OFF}`);

const cfg = await read(ORACLE, "get_config");
const stats = await read(ORACLE, "get_stats");

head("1. The rubric matches what the docs say");
const W = cfg.weights;
const wantW = {
  timing_pattern: 25,
  rating_distribution: 20,
  review_quality: 20,
  reviewer_credibility: 20,
  engagement_signals: 15,
};
for (const [k, v] of Object.entries(wantW)) {
  Number(W[k]) === v
    ? ok(`${k} = ${v}%`)
    : bad(`${k} is ${W[k]}, the docs say ${v}`);
}
Object.values(W).reduce((a, b) => a + Number(b), 0) === 100
  ? ok("weights sum to 100")
  : bad("weights do not sum to 100");
Number(cfg.thresholds.authentic_min) === 70
  ? ok("AUTHENTIC at 70+")
  : bad("wrong AUTHENTIC threshold");
Number(cfg.thresholds.suspicious_min) === 40
  ? ok("SUSPICIOUS at 40-69")
  : bad("wrong SUSPICIOUS threshold");
Number(cfg.quantisation_step) === 5
  ? ok("quantised to step 5")
  : bad("wrong quantisation step");
Number(cfg.rate_limit_seconds) === 300
  ? ok("rate limit is 300s per wallet")
  : bad("wrong rate limit");
String(cfg.fee_wei) === "0" ? ok("the fee is zero") : bad(`fee is ${cfg.fee_wei}`);

head("2. The platform table matches the measured probe");
const wantAvail = { AMAZON: 100, GOOGLE_PLAY: 80, APP_STORE: 65 };
for (const [p, w] of Object.entries(wantAvail)) {
  const got = Number(cfg.platforms?.[p]?.available_weight);
  got === w
    ? ok(`${p} measurable weight ${w}/100`)
    : bad(`${p} is ${got}, the docs say ${w}`);
}
cfg.platforms?.AMAZON?.credibility_basis === "verified-purchase"
  ? ok("Amazon credibility is verified-purchase")
  : bad("Amazon credibility basis changed");
cfg.platforms?.GOOGLE_PLAY?.credibility_basis === "identity-shape"
  ? ok("Google Play credibility is identity-shape")
  : bad("Google Play credibility basis changed");
cfg.platforms?.GOOGLE_PLAY?.dimensions?.rating_distribution === false
  ? ok("Google Play publishes no rating histogram")
  : bad("the Google Play histogram claim is stale");
cfg.platforms?.APP_STORE?.dimensions?.engagement_signals === false
  ? ok("the App Store publishes no engagement signal")
  : bad("the App Store engagement claim is stale");
for (const p of ["TRUSTPILOT", "YELP", "GOOGLE_MAPS"]) {
  cfg.unsupported?.[p]
    ? ok(`${p} is named unsupported, with a reason`)
    : bad(`${p} is not named in the unsupported table`);
}
Object.keys(cfg.platforms ?? {}).length === 3
  ? ok("exactly three platforms are offered")
  : bad("the platform count changed");

head("3. Every stored check recomputes from its own evidence");
const recent = await read(ORACLE, "get_recent_checks", [100]);
const items = recent?.items ?? [];
if (items.length === 0) {
  bad("no checks on chain yet");
} else {
  let verified = 0;
  for (const it of items) {
    const v = await read(ORACLE, "verify_check", [it.check_id]);
    if (v?.verified) verified++;
    else
      bad(
        `check ${it.check_id} does not verify`,
        JSON.stringify(v?.mismatches ?? []),
      );
  }
  if (verified === items.length) ok(`all ${items.length} checks verify clean`);
}

head("4. The guards agree with the stored levels");
for (const it of items.slice(0, 12)) {
  if (!it.source_url) continue;
  const authentic = await read(ORACLE, "is_authentic", [it.source_url]);
  const want = it.trust_level === "AUTHENTIC";
  Boolean(authentic) === want
    ? ok(`is_authentic is ${authentic} for a ${it.trust_level} page`)
    : bad(`is_authentic disagrees with ${it.trust_level} on ${it.url_key}`);
}
(await read(ORACLE, "is_authentic", ["https://www.amazon.com/dp/BZZZZZZZZZ"])) ===
false
  ? ok("is_authentic is false for a never-checked page")
  : bad("is_authentic passed a never-checked page");
(await read(ORACLE, "is_authentic", [
  "https://www.trustpilot.com/review/x.com",
])) === false
  ? ok("is_authentic is false for an unsupported host")
  : bad("is_authentic passed an unsupported host");

head("5. Inconclusive is excluded from the manipulation rate");
{
  const a = Number(stats.authentic);
  const s = Number(stats.suspicious);
  const m = Number(stats.manipulated);
  const i = Number(stats.inconclusive);
  Number(stats.conclusive_checks) === a + s + m
    ? ok(`conclusive_checks excludes the ${i} inconclusive`)
    : bad("conclusive_checks includes inconclusive checks");
  const expect = a + s + m === 0 ? 0 : Math.floor((m * 100) / (a + s + m));
  Number(stats.manipulation_rate_pct) === expect
    ? ok(
        `manipulation rate is ${stats.manipulation_rate_pct}%, over conclusive checks only`,
      )
    : bad(`rate is ${stats.manipulation_rate_pct}, expected ${expect}`);
  Number(stats.total_checked) === a + s + m + i
    ? ok("the four levels account for every check")
    : bad("the level counts do not sum to total_checked");
}

head("6. The consumer refuses what it says it refuses");
{
  const policy = await read(CONSUMER, "get_policy");
  String(policy.oracle).toLowerCase() === ORACLE.toLowerCase()
    ? ok("the consumer points at this oracle")
    : bad("the consumer points somewhere else");
  Number(policy.min_score) >= Number(cfg.thresholds.authentic_min)
    ? ok(`consumer min_score ${policy.min_score} is at or above AUTHENTIC`)
    : bad("the consumer would admit a below-authentic product");
  String(policy.policy_note).includes("INCONCLUSIVE")
    ? ok("the policy names INCONCLUSIVE as refused")
    : bad("the policy note is stale");

  const listings = await read(CONSUMER, "get_listings", [50]);
  const wrong = (listings?.items ?? []).filter(
    (l) => l.trust_level !== "AUTHENTIC",
  );
  wrong.length === 0
    ? ok(`every one of the ${listings?.count ?? 0} listings is AUTHENTIC`)
    : bad(`listed a ${wrong[0].trust_level} product`);

  const refusals = await read(CONSUMER, "get_refusals", [50]);
  const rows = refusals?.items ?? [];
  rows.every((r) => String(r.reason ?? "").length > 0)
    ? ok(`all ${rows.length} refusals carry a reason`)
    : bad("a refusal was logged with no reason");
}

head("7. The live site is serving this same contract");
try {
  const res = await fetch(
    `${SITE}/api/detect?url=${encodeURIComponent("https://www.amazon.com/dp/B07FZ8S74R")}`,
  );
  const j = await res.json();
  j?.url_key === "AMAZON:amazon.com:B07FZ8S74R"
    ? ok("the site canonicalises through the deployed contract")
    : bad("the site's detect route disagrees", JSON.stringify(j).slice(0, 160));
  Number(j?.available_weight) === 100
    ? ok("the site reports Amazon's measurable weight as 100")
    : bad(`the site says ${j?.available_weight}`);
} catch (e) {
  bad("the site did not answer", String(e?.message).slice(0, 120));
}

console.log(
  `\n${BOLD}Result:${OFF} ${GREEN}${pass} passed${OFF}  ${RED}${fail} failed${OFF}\n`,
);
process.exit(fail === 0 ? 0 : 1);
