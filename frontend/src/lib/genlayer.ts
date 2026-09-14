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
export const ORACLE_ADDRESS = (process.env.NEXT_PUBLIC_ORACLE_ADDRESS ??
  "0x37B5C64586d7d214D3aA45aA5a0Fdd5cc5f34c30") as `0x${string}`;

export const CONSUMER_ADDRESS = (process.env.NEXT_PUBLIC_CONSUMER_ADDRESS ??
  "0x0E4a16a697955d0001c64358B14C3AF156889822") as `0x${string}`;

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
