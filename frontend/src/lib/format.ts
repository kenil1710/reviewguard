import type { TrustLevel, Platform } from "./types";

/** The three trust levels plus the one that is not a level at all.
 *
 * INCONCLUSIVE is styled as SLATE, never as a shade of red. It is not a bad
 * score — it is the absence of one — and colouring it like a failure is how a
 * reader concludes that a page nobody could read is a page that failed. */
export const TRUST_STYLE: Record<
  TrustLevel,
  { text: string; bg: string; border: string; ring: string; hex: string; label: string }
> = {
  AUTHENTIC: {
    text: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    ring: "ring-emerald-500/20",
    hex: "#059669",
    label: "Authentic",
  },
  SUSPICIOUS: {
    text: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    ring: "ring-amber-500/20",
    hex: "#D97706",
    label: "Suspicious",
  },
  MANIPULATED: {
    text: "text-rose-700",
    bg: "bg-rose-50",
    border: "border-rose-200",
    ring: "ring-rose-500/20",
    hex: "#E11D48",
    label: "Manipulated",
  },
  INCONCLUSIVE: {
    text: "text-slate-600",
    bg: "bg-slate-100",
    border: "border-slate-200",
    ring: "ring-slate-500/20",
    hex: "#64748B",
    label: "Inconclusive",
  },
};

export const PLATFORM_LABEL: Record<Platform, string> = {
  AMAZON: "Amazon",
  GOOGLE_PLAY: "Google Play",
  APP_STORE: "App Store",
};

export const PLATFORM_STYLE: Record<Platform, string> = {
  AMAZON: "bg-orange-50 text-orange-700 border-orange-200",
  GOOGLE_PLAY: "bg-sky-50 text-sky-700 border-sky-200",
  APP_STORE: "bg-slate-100 text-slate-700 border-slate-300",
};

/** Colour for a 0-7 dimension ordinal, on the same scale the trust level uses,
 *  so a bar and a badge never disagree about what "good" looks like. */
export function ordinalHex(v: number | null): string {
  if (v === null || v === undefined) return "#CBD5E1";
  if (v >= 6) return "#059669";
  if (v >= 4) return "#65A30D";
  if (v >= 2) return "#D97706";
  return "#E11D48";
}

export function scoreHex(overall: number, level: TrustLevel): string {
  return TRUST_STYLE[level]?.hex ?? "#64748B";
}

/** Counts the way a tearsheet writes them, matching the three significant
 *  figures the contract actually agreed on. */
export function compact(n: number | string | null | undefined): string {
  const v = Number(n ?? 0);
  if (!Number.isFinite(v) || v <= 0) return "0";
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return `${Math.round(v)}`;
}

export function exact(n: number | string | null | undefined): string {
  const v = Number(n ?? 0);
  if (!Number.isFinite(v)) return "0";
  return Math.round(v).toLocaleString("en-US");
}

export function stars(avgX10: number | null): string {
  if (avgX10 === null || avgX10 === undefined) return "—";
  return (avgX10 / 10).toFixed(1);
}

export function timeAgo(unixSeconds: number): string {
  if (!unixSeconds) return "never";
  const secs = Math.max(0, Math.floor(Date.now() / 1000) - unixSeconds);
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

export function shortHash(h: string, n = 10): string {
  if (!h) return "";
  return h.length <= n * 2 ? h : `${h.slice(0, n)}…${h.slice(-6)}`;
}

export function shortAddress(a: string): string {
  if (!a || a.length < 12) return a || "";
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

export function daysOf(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  if (d >= 365) return `${(d / 365).toFixed(1)} years`;
  if (d >= 1) return `${d} days`;
  return `${Math.floor(seconds / 3600)} hours`;
}

export function spanLabel(days: number): string {
  if (days <= 0) return "a single day";
  if (days === 1) return "1 day";
  if (days < 31) return `${days} days`;
  if (days < 365) {
    const m = Math.round(days / 30);
    return m === 1 ? "about a month" : `${m} months`;
  }
  const y = days / 365;
  return y < 1.05 ? "about a year" : `${y.toFixed(1)} years`;
}
