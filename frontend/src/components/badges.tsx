import {
  ShieldCheck, ShieldAlert, ShieldX, HelpCircle, ShoppingCart,
  Play, Apple, Globe,
} from "lucide-react";
import type { TrustLevel, Platform } from "@/lib/types";
import { TRUST_STYLE, PLATFORM_LABEL, PLATFORM_STYLE } from "@/lib/format";

const TRUST_ICON = {
  AUTHENTIC: ShieldCheck,
  SUSPICIOUS: ShieldAlert,
  MANIPULATED: ShieldX,
  INCONCLUSIVE: HelpCircle,
} as const;

export function TrustBadge({
  level,
  size = "md",
}: {
  level: TrustLevel;
  size?: "sm" | "md" | "lg";
}) {
  const s = TRUST_STYLE[level];
  const Icon = TRUST_ICON[level];
  const pad =
    size === "lg"
      ? "px-3.5 py-1.5 text-sm"
      : size === "sm"
        ? "px-2 py-0.5 text-[11px]"
        : "px-2.5 py-1 text-xs";
  const ic = size === "lg" ? 18 : size === "sm" ? 13 : 15;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${pad} ${s.bg} ${s.text} ${s.border}`}
    >
      <Icon size={ic} strokeWidth={2.2} aria-hidden="true" />
      {s.label}
    </span>
  );
}

const PLATFORM_ICON = {
  AMAZON: ShoppingCart,
  GOOGLE_PLAY: Play,
  APP_STORE: Apple,
} as const;

export function PlatformBadge({
  platform,
  size = "md",
}: {
  platform: Platform | string;
  size?: "sm" | "md";
}) {
  const key = (platform as Platform) in PLATFORM_LABEL
    ? (platform as Platform)
    : null;
  const Icon = key ? PLATFORM_ICON[key] : Globe;
  const label = key ? PLATFORM_LABEL[key] : String(platform || "Unknown");
  const cls = key ? PLATFORM_STYLE[key] : "bg-slate-100 text-slate-600 border-slate-200";
  const pad = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${pad} ${cls}`}
    >
      <Icon size={size === "sm" ? 12 : 14} strokeWidth={2} aria-hidden="true" />
      {label}
    </span>
  );
}

/** For the evidence panel: a figure the platform does not publish, said in
 *  words rather than shown as a zero. */
export function NotPublished({ what }: { what?: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-400">
      <HelpCircle size={13} strokeWidth={2} aria-hidden="true" />
      {what ?? "not published"}
    </span>
  );
}
