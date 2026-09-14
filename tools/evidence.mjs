/**
 * Dump the live on-chain state to docs/evidence.json.
 *
 * Every claim the README and the site make about what ReviewGuard has actually
 * done is generated from this file, so a stale number is a diff rather than a
 * sentence somebody forgot to update.
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { writeFileSync, readFileSync } from "node:fs";

const deployments = JSON.parse(
  readFileSync(new URL("../deployments.json", import.meta.url), "utf8"),
).deployments.studiodev;

const ORACLE = deployments.ReviewGuard.address;
const CONSUMER = deployments.MarketplaceConsumer.address;
const client = createClient({ chain: studioDevnet });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function read(address, functionName, args = []) {
  for (let i = 1; i <= 5; i++) {
    try {
      return await client.readContract({ address, functionName, args });
    } catch (e) {
      const msg = String(e?.message ?? e);
      if (i === 5) return { _error: msg.slice(0, 200) };
      await sleep(/rate limit/i.test(msg) ? 4000 : 900 * i);
    }
  }
}

/** BigInt is not JSON; every count the contract returns as u256 arrives as one. */
const plain = (v) =>
  JSON.parse(JSON.stringify(v, (_k, x) => (typeof x === "bigint" ? String(x) : x)));

console.log("reading ReviewGuard…");
const config = await read(ORACLE, "get_config");
const stats = await read(ORACLE, "get_stats");
const recent = await read(ORACLE, "get_recent_checks", [100]);

const checks = [];
const verifications = [];
for (const item of recent?.items ?? []) {
  const full = await read(ORACLE, "get_check", [item.check_id]);
  checks.push(plain(full));
  const v = await read(ORACLE, "verify_check", [item.check_id]);
  verifications.push({
    check_id: item.check_id,
    verified: v?.verified ?? false,
    mismatches: v?.mismatches ?? [],
  });
  console.log(
    `  #${item.check_id} ${item.trust_level.padEnd(12)} ${String(item.overall).padStart(3)}  ` +
      `verified=${v?.verified}  ${item.title?.slice(0, 44) ?? ""}`,
  );
}

console.log("reading MarketplaceConsumer…");
const policy = await read(CONSUMER, "get_policy");
const listings = await read(CONSUMER, "get_listings", [50]);
const refusals = await read(CONSUMER, "get_refusals", [50]);

const guards = [];
for (const item of (recent?.items ?? []).slice(0, 12)) {
  const src = item.source_url;
  if (!src) continue;
  const authentic = await read(ORACLE, "is_authentic", [src]);
  const summary = await read(ORACLE, "get_trust_summary", [src]);
  guards.push({
    url: src,
    is_authentic: authentic,
    trust_level: summary?.trust_level,
    // The property that matters: is_authentic must be false for anything that
    // is not AUTHENTIC, including INCONCLUSIVE.
    consistent:
      Boolean(authentic) === (summary?.trust_level === "AUTHENTIC"),
  });
}

const out = {
  captured_at: new Date().toISOString(),
  network: { name: "GenLayer Studio Dev", chain_id: 61997 },
  addresses: { ReviewGuard: ORACLE, MarketplaceConsumer: CONSUMER },
  config: plain(config),
  stats: plain(stats),
  checks,
  verifications,
  all_verified: verifications.every((v) => v.verified),
  guards,
  guards_consistent: guards.every((g) => g.consistent),
  consumer: {
    policy: plain(policy),
    listings: plain(listings),
    refusals: plain(refusals),
  },
};

writeFileSync(
  new URL("../docs/evidence.json", import.meta.url),
  JSON.stringify(out, null, 2),
);

console.log("");
console.log(`checks:            ${checks.length}`);
console.log(`all verified:      ${out.all_verified}`);
console.log(`guards consistent: ${out.guards_consistent}`);
console.log(`listings:          ${listings?.count ?? 0}`);
console.log(`refusals:          ${refusals?.count ?? 0}`);
console.log("→ docs/evidence.json");
