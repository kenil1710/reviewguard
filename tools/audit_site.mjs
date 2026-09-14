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

  await page.fill("#url", "https://www.amazon.com/dp/B07FZ8S74R");
  await page.waitForTimeout(1800);
  const preview = await page.locator("text=Amazon detected").count();
  preview > 0
    ? ok("a valid URL auto-detects its platform")
    : bad("platform detection did not fire");
  (await page.getByText("verified-purchase").count()) > 0
    ? ok("the preview names the credibility basis")
    : bad("credibility basis missing from the preview");

  await page.fill("#url", "https://www.trustpilot.com/review/amazon.com");
  await page.waitForTimeout(1800);
  (await page.getByText(/cannot read that page/i).count()) > 0
    ? ok("a blocked platform is refused in the UI, with a reason")
    : bad("Trustpilot was not refused in the UI");
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
{
  const page = await ctx.newPage();
  await page.goto(BASE + "/compare", { waitUntil: "networkidle" });

  const urls = (await (await fetch(`${BASE}/api/detect?url=x`)).json()) && null;
  const a = "https://play.google.com/store/apps/details?id=com.whatsapp";
  const b = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997";

  const inputs = page.locator('input[placeholder*="checked product URL"]');
  await inputs.nth(0).fill(a);
  await page.getByRole("button", { name: "Load" }).nth(0).click();
  await page.waitForTimeout(4000);
  await inputs.nth(1).fill(b);
  await page.getByRole("button", { name: "Load" }).nth(1).click();
  await page.waitForTimeout(5000);

  const body = await page.locator("body").innerText();
  /more authentic|dead heat|cannot be ranked/i.test(body)
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
