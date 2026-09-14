/**
 * The check a visitor started, remembered across navigations.
 *
 * A round takes 30-90 seconds. Before this, a visitor who opened another tab,
 * hit back, or let their phone sleep came back to an empty form and no way to
 * find the check they had already paid the wait for — the transaction had
 * settled and the record existed, and the UI simply had no idea.
 *
 * So the submitted URL is written down BEFORE the request goes out, not after
 * it returns: the failure being fixed is precisely the one where the answer
 * arrives while nobody is listening. On the next visit the form asks the
 * contract whether that URL has a record yet, and either lands the visitor on
 * it or tells them it is still running.
 *
 * Everything here is wrapped in try/catch. `localStorage` throws in a private
 * window and in some embedded browsers, and a storage failure must never stop
 * somebody checking a product.
 */

const KEY = "reviewguard.pending-check.v1";

/** Older than this and we stop claiming it is "still running". A GenLayer
 *  round that has not settled in ten minutes is not going to. */
export const PENDING_TTL_MS = 10 * 60 * 1000;

export interface PendingCheck {
  url: string;
  startedAt: number;
}

export function rememberPending(url: string): void {
  try {
    const value: PendingCheck = { url, startedAt: Date.now() };
    window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    /* private window, or storage disabled — the check still works */
  }
}

export function readPending(): PendingCheck | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as PendingCheck;
    if (typeof value?.url !== "string" || typeof value?.startedAt !== "number") {
      return null;
    }
    if (Date.now() - value.startedAt > PENDING_TTL_MS) {
      forgetPending();
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

export function forgetPending(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing to clean up */
  }
}
