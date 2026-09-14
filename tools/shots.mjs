/**
 * Screenshots of the live site, plus a console-error and horizontal-scroll
 * audit at both desktop and phone width.
 *
 * The 390px pass is not decoration: a page that scrolls sideways on a phone is
 * broken for most of the people who will ever open it, and it is invisible from
 * a laptop.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE ?? "https://reviewguard-gl.vercel.app";
const OUT = new URL("../screenshots/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const PAGES = [
  ["landing", "/"],
  ["check", "/check"],
  ["results", "/results"],
  ["result", "/result/1"],
  ["compare", "/compare"],
  ["docs", "/docs"],
];

const problems = [];

const browser = await chromium.launch();
for (const [width, height, tag] of [[1440, 900, "desktop"], [390, 844, "mobile"]]) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 2,
  });
  for (const [name, path] of PAGES) {
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 60_000 });
    await page.waitForTimeout(1400);          // let the gauges finish animating

    await page.screenshot({
      path: `${OUT}${tag}-${name}.png`,
      fullPage: tag === "desktop",
    });

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    if (overflow > 1) problems.push(`${tag} ${path}: scrolls ${overflow}px sideways`);

    // Ignore the noise a testnet RPC makes; anything else is ours.
    const real = errors.filter(
      (e) => !/favicon|ERR_INTERNET_DISCONNECTED|rate limit|429|Failed to load resource/i.test(e),
    );
    if (real.length) problems.push(`${tag} ${path}: ${real.slice(0, 3).join(" | ")}`);

    console.log(`  ${tag.padEnd(7)} ${path.padEnd(12)} overflow=${overflow}px errors=${real.length}`);
    await page.close();
  }
  await ctx.close();
}
await browser.close();

console.log("");
if (problems.length) {
  console.log("PROBLEMS:");
  for (const p of problems) console.log("  ✘ " + p);
  process.exit(1);
}
console.log("✔ no console errors and no horizontal scroll at 1440px or 390px");
