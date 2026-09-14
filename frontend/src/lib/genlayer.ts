import { createClient, createAccount } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

/**
 * One place that knows where ReviewGuard lives.
 *
 * The addresses are baked in as defaults rather than left as required env vars:
 * a deployed site whose only copy of the contract address is an environment
 * variable somebody forgot to set is a site that renders an error page, and the
 * address is public information anyway.
 */
/**
 * `??` is the wrong operator here and it cost a broken deploy.
 *
 * It falls back only on null or undefined, so an environment variable set to
 * the EMPTY STRING — which is what a failed `vercel env add` leaves behind —
 * sails straight through and becomes the contract address. Every read then
 * fails against `""` with an error that looks like an RPC outage. This checks
 * the value is actually an address before trusting it.
 */
const addr = (value: string | undefined, fallback: string): `0x${string}` =>
  /^0x[0-9a-fA-F]{40}$/.test(value ?? "")
    ? (value as `0x${string}`)
    : (fallback as `0x${string}`);

export const ORACLE_ADDRESS = addr(
  process.env.NEXT_PUBLIC_ORACLE_ADDRESS,
  "0xA548BfAcA16765E9910F3aE7537fAA2B3064C12B",
);

export const CONSUMER_ADDRESS = addr(
  process.env.NEXT_PUBLIC_CONSUMER_ADDRESS,
  "0x71131eBe691998BCBc8F572fAab07661299426ce",
);

export const EXPLORER = "https://explorer-studio-dev.genlayer.com";
export const CHAIN = studioDevnet;

export const readClient = () => createClient({ chain: studioDevnet });

/**
 * The relayer.
 *
 * Studio Dev is a faucet-funded testnet and a check is free, so the site can
 * submit on a visitor's behalf rather than demanding they install a wallet and
 * fund it to try a free read-only product. The key is server-side only and is
 * never sent to the browser; the UI says plainly that it is a testnet relayer,
 * and the wallet path is always offered alongside it.
 */
export function relayClient() {
  const key = process.env.RELAYER_PRIVATE_KEY;
  if (!key) return null;
  const account = createAccount(key as `0x${string}`);
  return { wallet: createClient({ chain: studioDevnet, account }), account };
}

/**
 * The fee preset every write must carry.
 *
 * studio-dev rejects a transaction whose fee DISTRIBUTION is absent with
 * `FeeValueMustBeNonZero(1)` — a `value` alone is not enough, the distribution
 * object has to travel with it. Measured: the first production `/api/check`
 * reverted with exactly that, and the CLI needed the same fix.
 *
 * Cached for a minute because the estimate is a network round trip and the
 * policy does not move between one visitor and the next.
 */
type FeePreset = { distribution: unknown; feeValue: bigint };
let feeCache: { at: number; value: FeePreset } | null = null;

export async function feePreset(
  client: ReturnType<typeof readClient>,
): Promise<FeePreset> {
  if (feeCache && Date.now() - feeCache.at < 60_000) return feeCache.value;
  const est = (await retry(() =>
    (client as unknown as {
      estimateTransactionFees: (a?: unknown) => Promise<{
        distribution: unknown;
        feeValue: string | bigint;
      }>;
    }).estimateTransactionFees(),
  )) as { distribution: unknown; feeValue: string | bigint };
  const value = {
    distribution: est.distribution,
    feeValue: BigInt(est.feeValue),
  };
  feeCache = { at: Date.now(), value };
  return value;
}

export const txUrl = (hash: string) => `${EXPLORER}/tx/${hash}`;
export const addressUrl = (address: string) => `${EXPLORER}/address/${address}`;

/**
 * Retry an RPC call.
 *
 * Studio meters requests per minute and intermittently answers with an HTML
 * error page rather than JSON, which surfaces as `Unexpected token '<'`. That
 * is a transient shape, not a bad request, and retrying it is the difference
 * between a page that loads and a page that shows an error for no reason.
 */
export async function retry<T>(fn: () => Promise<T>, attempts = 4): Promise<T> {
  let last: unknown;
  for (let i = 1; i <= attempts; i++) {
    try {
      return await fn();
    } catch (e) {
      last = e;
      const msg = String((e as Error)?.message ?? e);
      const transient =
        /Unexpected token '<'|not valid JSON|fetch failed|ECONNRESET|ETIMEDOUT|50\d|rate limit exceeded|-32029/i.test(
          msg,
        );
      if (!transient || i === attempts) throw e;
      await new Promise((r) =>
        setTimeout(r, /rate limit/i.test(msg) ? 4000 : 900 * i),
      );
    }
  }
  throw last;
}
