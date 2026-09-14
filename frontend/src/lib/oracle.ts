import "server-only";
import { ORACLE_ADDRESS, readClient, retry } from "./genlayer";
import type {
  CheckResult, CheckSummary, Config, Detection, Stats, VerifyResult,
} from "./types";

/**
 * Every read of ReviewGuard, in one place, on the server.
 *
 * Server-side because Studio Dev meters RPC requests per caller: a page that
 * read the contract from the browser would spend that budget once per visitor
 * and start failing for the second one. Here the reads are cached and shared.
 */

/**
 * A process-wide memo with a TTL, in front of every read.
 *
 * In-flight requests are shared too, not just completed ones — otherwise ten
 * concurrent renders of the same page fire ten identical calls before the first
 * one lands, which is exactly the burst the limiter is watching for.
 */
type Entry = { at: number; value: unknown };
const memo = new Map<string, Entry>();
const inflight = new Map<string, Promise<unknown>>();
const MEMO_MS = 30_000;

const call = async <T>(fn: string, args: unknown[] = []): Promise<T> => {
  const key = `${fn}:${JSON.stringify(args)}`;
  const hit = memo.get(key);
  if (hit && Date.now() - hit.at < MEMO_MS) return hit.value as T;

  const pending = inflight.get(key);
  if (pending) return (await pending) as T;

  const task = (async () => {
    const client = readClient();
    const value = await retry(() =>
      client.readContract({
        address: ORACLE_ADDRESS,
        functionName: fn,
        args: args as never,
      }),
    );
    memo.set(key, { at: Date.now(), value });
    if (memo.size > 400) {
      const oldest = [...memo.entries()].sort((a, b) => a[1].at - b[1].at);
      for (const [k] of oldest.slice(0, 100)) memo.delete(k);
    }
    return value;
  })();

  inflight.set(key, task);
  try {
    return (await task) as T;
  } finally {
    inflight.delete(key);
  }
};

/**
 * Drop one memoised read.
 *
 * The check route polls for a record that does not exist yet; without this the
 * memo would hand it the same "not found" for thirty seconds and the poll
 * would be watching a cached answer rather than the chain.
 */
export function forget(fn: string, args: unknown[] = []): void {
  memo.delete(`${fn}:${JSON.stringify(args)}`);
}

export const getConfig = () => call<Config>("get_config");
export const getStats = () => call<Stats>("get_stats");
export const getCheck = (id: number) => call<CheckResult>("get_check", [id]);
export const getCheckByUrl = (url: string) =>
  call<CheckResult>("get_check_by_url", [url]);
export const detectPlatform = (url: string) =>
  call<Detection>("detect_platform", [url]);
export const verifyCheck = (id: number) =>
  call<VerifyResult>("verify_check", [id]);
export const getHistory = (url: string, count = 6) =>
  call<{ found: boolean; items?: CheckSummary[]; total_checks?: number }>(
    "get_history",
    [url, count],
  );

export const getRecent = async (count = 60): Promise<CheckSummary[]> => {
  const out = await call<{ count: number; items: CheckSummary[] }>(
    "get_recent_checks",
    [count],
  );
  return out?.items ?? [];
};

export const getByPlatform = async (
  platform: string,
  count = 60,
): Promise<CheckSummary[]> => {
  const out = await call<{ count: number; items: CheckSummary[] }>(
    "get_checks_by_platform",
    [platform, count],
  );
  return out?.items ?? [];
};

/**
 * Safe wrappers for page render.
 *
 * A page must render even when the RPC is having a bad minute. These swallow
 * the failure and return an empty shape, and every caller is written to show a
 * plain "nothing here yet" rather than pretending zero is a measurement.
 */
export async function safeStats(): Promise<Stats | null> {
  try {
    return await getStats();
  } catch {
    return null;
  }
}

export async function safeRecent(count = 60): Promise<CheckSummary[]> {
  try {
    return await getRecent(count);
  } catch {
    return [];
  }
}

export async function safeConfig(): Promise<Config | null> {
  try {
    return await getConfig();
  } catch {
    return null;
  }
}

export async function safeCheck(id: number): Promise<CheckResult | null> {
  try {
    return await getCheck(id);
  } catch {
    return null;
  }
}
