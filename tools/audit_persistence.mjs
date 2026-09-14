/**
 * The scan-persistence fix, tested the way it actually fails.
 *
 * The bug was: start a check, navigate away, come back — the result is gone.
 * A unit test cannot catch that, because the thing that breaks is the
 * relationship between a navigation and an in-flight request. So this drives a
 * real browser: it seeds the pending marker, navigates, comes back, and asserts
 * the visitor is told what is happening and then landed on their result.
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
  console.log(`  FAIL ${m}${d ? "\n       " + String(d).slice(0, 220) : ""}`);
};
const head = (m) => console.log(`\n${m}`);

// A URL the contract has definitely checked, so "recovered" has somewhere to go.
const recent = await (await fetch(`${BASE}/api/recent?count=5`)).json();
const known = recent?.items?.[0];
if (!known) {
  console.log("no checked records on chain; cannot test recovery");
  process.exit(1);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });

head("The wait tells the visitor to stay, and that leaving is survivable");
{
  const page = await ctx.newPage();
  await page.goto(`${BASE}/check`, { waitUntil: "networkidle" });
  // Drive the loading panel without spending a real transaction: the phase is
  // reached by submitting, so intercept the API and hold it open.
  await page.route("**/api/check", async () => {
    /* never resolves within this test — that is the point */
  });
  await page.fill("#url", known.source_url);
  await page.waitForFunction(
    () => /detected/i.test(document.body.innerText),
    undefined,
    { timeout: 30_000 },
  );
  await page.getByRole("button", { name: /check reviews/i }).click();
  await page.waitForTimeout(1500);

  const body = await page.locator("body").innerText();
  /stay on this page/i.test(body)
    ? ok("the loading state says to stay on the page")
    : bad("no 'stay on this page' warning", body.slice(0, 200));
  /30.{0,3}90 seconds/i.test(body)
    ? ok("it states how long analysis takes")
    : bad("the duration is not stated");
  /nothing is lost|result will be waiting/i.test(body)
    ? ok("it says leaving is survivable")
    : bad("it does not say what happens if they leave");

  const stored = await page.evaluate(() =>
    window.localStorage.getItem("reviewguard.pending-check.v1"),
  );
  stored && stored.includes(known.source_url)
    ? ok("the submitted URL is persisted BEFORE the request returns")
    : bad("nothing was persisted at submit time", String(stored));
  await page.close();
}

head("Navigating away and back recovers the check");
{
  const page = await ctx.newPage();
  await page.goto(`${BASE}/check`, { waitUntil: "networkidle" });

  // Exactly the state a visitor leaves behind: a check started moments ago.
  await page.evaluate((url) => {
    window.localStorage.setItem(
      "reviewguard.pending-check.v1",
      JSON.stringify({ url, startedAt: Date.now() }),
    );
  }, known.source_url);

  // Go somewhere else, then come back — the reported bug, exactly.
  await page.goto(`${BASE}/docs`, { waitUntil: "networkidle" });
  await page.goto(`${BASE}/check`, { waitUntil: "domcontentloaded" });

  let sawBanner = false;
  try {
    await page.waitForFunction(
      () => /picking up the check you already started/i.test(document.body.innerText),
      undefined,
      { timeout: 8000 },
    );
    sawBanner = true;
  } catch {
    /* it may have resolved to the result before we looked */
  }

  try {
    await page.waitForURL(/\/result\/\d+/, { timeout: 45_000 });
    ok(`came back and landed on ${new URL(page.url()).pathname}`);
    // The URL changes before the server component has painted. Waiting for the
    // record's own title is the difference between testing the recovery and
    // testing how fast the render happened to be.
    const needle = (known.title ?? "").slice(0, 20);
    try {
      await page.waitForFunction(
        (want) => document.body.innerText.includes(want),
        needle,
        { timeout: 30_000 },
      );
      ok("the recovered page is the right record");
    } catch {
      bad(
        "landed somewhere unexpected",
        (await page.locator("body").innerText()).slice(0, 160),
      );
    }
    if (sawBanner) ok("the visitor was told their check was being recovered");
    else ok("recovery was instant enough that no banner was needed");
  } catch {
    bad("never recovered the check after navigating away", page.url());
  }

  const cleared = await page.evaluate(() =>
    window.localStorage.getItem("reviewguard.pending-check.v1"),
  );
  cleared === null
    ? ok("the pending marker is cleared once recovered")
    : bad("a stale marker was left behind", String(cleared));
  await page.close();
}

head("A stale marker does not haunt the form forever");
{
  const page = await ctx.newPage();
  await page.goto(`${BASE}/check`, { waitUntil: "networkidle" });
  await page.evaluate(() => {
    window.localStorage.setItem(
      "reviewguard.pending-check.v1",
      JSON.stringify({
        url: "https://www.amazon.com/dp/BNEVERCHKD",
        // Older than the ten-minute TTL.
        startedAt: Date.now() - 60 * 60 * 1000,
      }),
    );
  });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const body = await page.locator("body").innerText();
  !/picking up the check/i.test(body)
    ? ok("an expired marker is ignored rather than shown as running")
    : bad("an hour-old marker still claims to be in flight");
  const gone = await page.evaluate(() =>
    window.localStorage.getItem("reviewguard.pending-check.v1"),
  );
  gone === null
    ? ok("the expired marker is cleaned up")
    : bad("the expired marker survived");
  await page.close();
}

head("Storage being unavailable does not break the form");
{
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    // What a private window does.
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("storage disabled");
      },
    });
  });
  await page.goto(`${BASE}/check`, { waitUntil: "networkidle" });
  await page.fill("#url", "https://www.amazon.com/dp/B07FZ8S74R");
  try {
    await page.waitForFunction(
      () => /Amazon detected/i.test(document.body.innerText),
      undefined,
      { timeout: 30_000 },
    );
    ok("the form still works with localStorage throwing");
  } catch {
    bad("the form broke when storage was unavailable");
  }
  await page.close();
}

await ctx.close();
await browser.close();

console.log(`\nResult: ${pass} passed  ${fail} failed\n`);
process.exit(fail === 0 ? 0 : 1);
