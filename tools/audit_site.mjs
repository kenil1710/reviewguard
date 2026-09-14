/**
 * Drive the real UI, not just photograph it.
 *
 * A screenshot proves a page painted. It does not prove the compare form loads
 * a record, that the verify button actually asks the chain, or that a filter
 * filters. These click through the flows a visitor would and assert on what
 * comes back.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "https://reviewguard-gl.vercel.app";

let pass = 0;
let fail = 0;
const ok = (m) => {
  pass++;
  console.log(`  PASS ${m}`);
};
const bad = (m, d) => {
  fail++;
  console.log(`  FAIL ${m}${d ? "\n       " + String(d).slice(0, 200) : ""}`);
};
const head = (m) => console.log(`\n${m}`);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });

// A record to work with, straight from the contract the site is serving.
const api = await (
  await fetch(`${BASE}/api/lookup?url=${encodeURIComponent("https://play.google.com/store/apps/details?id=com.whatsapp")}`)
).json();

head("Landing");
{
  const page = await ctx.newPage();
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  (await page.locator("h1").innerText()).includes("Are those reviews")
    ? ok("the headline is the promise, not a product category")
    : bad("headline changed");
  (await page.locator("header").innerText()).includes("Connect")
    ? bad("the landing page asks for a wallet before saying what it does")
    : ok("no wallet prompt on the marketing page");
  (await page.getByRole("link", { name: /check a product/i }).count()) > 0
    ? ok("primary CTA present")
    : bad("no primary CTA");
  (await page.getByText(/inconclusive/i).count()) > 0
    ? ok("the landing page explains the fourth answer")
    : bad("INCONCLUSIVE is not explained on the landing page");
  await page.close();
}

head("Check");
{
  const page = await ctx.newPage();
  await page.goto(BASE + "/check", { waitUntil: "networkidle" });

  // Waiting for the CONDITION rather than for a guess. Detection is a debounce
  // plus a serverless round trip, and a cold function takes longer than a warm
  // one — a fixed sleep here made the audit pass or fail on how recently the
  // site had been visited.
  const awaitText = async (re, label) => {
    try {
      await page.waitForFunction(
        (src) => new RegExp(src, "i").test(document.body.innerText),
        re.source,
        { timeout: 30_000 },
      );
      return true;
    } catch {
      bad(label);
      return false;
    }
  };

  await page.fill("#url", "https://www.amazon.com/dp/B07FZ8S74R");
  (await awaitText(/Amazon detected/, "platform detection did not fire")) &&
    ok("a valid URL auto-detects its platform");
  (await page.getByText("verified-purchase").count()) > 0
    ? ok("the preview names the credibility basis")
    : bad("credibility basis missing from the preview");

  await page.fill("#url", "https://www.trustpilot.com/review/amazon.com");
  (await awaitText(/cannot read that page/, "Trustpilot was not refused in the UI")) &&
    ok("a blocked platform is refused in the UI, with a reason");
  const disabled = await page
    .getByRole("button", { name: /check reviews/i })
    .isDisabled();
  disabled
    ? ok("the submit button is disabled for an unsupported host")
    : bad("an unsupported host could be submitted");
  await page.close();
}

head("Results");
{
  const page = await ctx.newPage();
  await page.goto(BASE + "/results", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);

  const cards = await page.locator("article").count();
  cards > 0 ? ok(`${cards} result cards rendered`) : bad("no result cards");

  const before = cards;
  await page.getByRole("button", { name: "Amazon", exact: true }).click();
  await page.waitForTimeout(600);
  const after = await page.locator("article").count();
  after <= before
    ? ok(`the platform filter narrows the grid (${before} to ${after})`)
    : bad("the filter widened the grid");

  await page.getByRole("button", { name: "All", exact: true }).first().click();
  await page.waitForTimeout(500);
  await page.fill('input[placeholder*="Search"]', "zzzznothing");
  await page.waitForTimeout(600);
  (await page.getByText(/nothing matches those filters/i).count()) > 0
    ? ok("an empty search shows an empty state, not a blank page")
    : bad("no empty state");
  await page.close();
}

head("Result detail");
{
  const id = api?.check_id ?? 1;
  const page = await ctx.newPage();
  await page.goto(`${BASE}/result/${id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1600);

  const body = await page.locator("body").innerText();
  body.includes(api?.title ?? "WhatsApp")
    ? ok("the record's title is on the page")
    : bad("title missing");
  body.includes("The five signals")
    ? ok("the five dimensions are shown")
    : bad("dimension section missing");
  body.includes("What the validators found")
    ? ok("the evidence section is shown")
    : bad("evidence section missing");
  body.includes("not published")
    ? ok("a dimension the platform does not publish says so in words")
    : bad("an unpublished dimension is not labelled");

  // The button that matters: it must actually ask the chain.
  await page.getByRole("button", { name: /recompute from evidence/i }).click();
  await page.waitForTimeout(6000);
  const after = await page.locator("body").innerText();
  after.includes("Verified")
    ? ok("recompute-from-evidence verifies against the chain")
    : bad("verify did not report a result", after.slice(0, 200));
  await page.close();
}

head("Compare");
// Compare needs TWO checked records. On a freshly deployed contract that is
// not a failure, it is an empty chain — and an audit that cannot tell those
// apart teaches a reader to ignore its red.
const a = "https://play.google.com/store/apps/details?id=com.whatsapp";
const b = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997";
const both = await Promise.all(
  [a, b].map(async (u) =>
    (await (await fetch(`${BASE}/api/lookup?url=${encodeURIComponent(u)}`)).json())
      ?.found,
  ),
);
if (!both.every(Boolean)) {
  console.log("  SKIP compare: fewer than two checked records on chain yet");
} else {
  const page = await ctx.newPage();
  await page.goto(BASE + "/compare", { waitUntil: "networkidle" });

  const inputs = page.locator('input[placeholder*="checked product URL"]');

  // Wait for the CONDITION, not for a guess at how long the RPC takes. A fixed
  // sleep here passed on a fast minute and failed on a slow one, which makes
  // the audit a coin toss rather than a check.
  const settle = async (label) => {
    try {
      await page.waitForFunction(
        (want) => document.body.innerText.includes(want),
        "reviews read",
        { timeout: 45_000 },
      );
      return true;
    } catch {
      bad(`compare: ${label} never loaded`);
      return false;
    }
  };

  await inputs.nth(0).fill(a);
  await page.getByRole("button", { name: "Load" }).nth(0).click();
  await settle("product A");

  await inputs.nth(1).fill(b);
  await page.getByRole("button", { name: "Load" }).nth(1).click();
  try {
    await page.waitForFunction(
      () => /more authentic|same overall score|cannot be ranked/i.test(document.body.innerText),
      undefined,
      { timeout: 45_000 },
    );
  } catch {
    /* the assertion below reports it */
  }

  const body = await page.locator("body").innerText();
  /more authentic|same overall score|cannot be ranked/i.test(body)
    ? ok("two loaded records produce a verdict")
    : bad("compare produced no verdict", body.slice(0, 240));
  body.includes("Timing pattern")
    ? ok("the dimension-by-dimension diff renders")
    : bad("no dimension diff");
  await page.close();
}

head("Docs");
{
  const page = await ctx.newPage();
  await page.goto(BASE + "/docs", { waitUntil: "networkidle" });
  const body = await page.locator("body").innerText();
  for (const needle of [
    "Getting started",
    "Methodology",
    "Supported platforms",
    "scoring rubric",
    "Integration guide",
    "FAQ",
  ]) {
    body.toLowerCase().includes(needle.toLowerCase())
      ? ok(`docs section: ${needle}`)
      : bad(`docs section missing: ${needle}`);
  }
  body.includes("Trustpilot")
    ? ok("the docs name what was tried and does not work")
    : bad("blocked platforms are not named in the docs");
  body.includes("get_trust_summary")
    ? ok("the integration guide shows the never-raises read")
    : bad("integration guide missing the safe read");
  await page.close();
}

await ctx.close();
await browser.close();

console.log(`\nResult: ${pass} passed  ${fail} failed\n`);
process.exit(fail === 0 ? 0 : 1);
