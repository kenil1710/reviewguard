"use client";

import { motion, useReducedMotion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import type { DimensionKey } from "@/lib/types";
import { DIMENSIONS, DIMENSION_LABELS, DIMENSION_BLURBS } from "@/lib/types";
import { ordinalHex } from "@/lib/format";

/**
 * The five dimension bars.
 *
 * A dimension the platform does not publish renders as an EMPTY track with the
 * words "not published by this platform" where the bar would be — never as a
 * bar of length zero. Those are different claims, and the whole conservatism
 * rule in the contract exists so that a reader can tell them apart.
 */
export function DimensionBars({
  scores,
  labels,
  weights,
  compact = false,
}: {
  scores: Record<DimensionKey, number | null>;
  labels?: Record<DimensionKey, string>;
  weights?: Record<DimensionKey, number>;
  compact?: boolean;
}) {
  /** The contract distinguishes the two reasons; this renders the distinction.
   *  Saying "this platform publishes nothing to measure here" about an Amazon
   *  page that simply arrived truncated is a false statement about Amazon. */
  const explain = (key: DimensionKey) => {
    const label = labels?.[key] ?? "";
    if (label.startsWith("the page did not render")) {
      return (
        <>
          The page arrived without its review list, so there was nothing to
          measure. This platform <strong>does</strong> publish this signal — the
          dimension carries <strong>no weight</strong> here rather than counting
          as zero, and a later check often reads it fine.
        </>
      );
    }
    if (label.startsWith("not enough evidence")) {
      return (
        <>
          Too few reviews rendered to measure this. The dimension carries{" "}
          <strong>no weight</strong> rather than counting as zero.
        </>
      );
    }
    return (
      <>
        This platform publishes nothing to measure here, so the dimension
        carries <strong>no weight</strong> in the score rather than counting as
        zero.
      </>
    );
  };

  const reduce = useReducedMotion();
  return (
    <ul className="space-y-4">
      {DIMENSIONS.map((key, i) => {
        const v = scores?.[key] ?? null;
        const missing = v === null || v === undefined;
        const pct = missing ? 0 : (v / 7) * 100;
        return (
          <li key={key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-semibold text-slate-800">
                {DIMENSION_LABELS[key]}
                {weights ? (
                  <span className="num ml-1.5 text-[11px] font-medium text-slate-400">
                    {weights[key]}%
                  </span>
                ) : null}
              </span>
              {missing ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
                  <HelpCircle size={12} strokeWidth={2} aria-hidden="true" />
                  {labels?.[key]?.startsWith("the page did not render")
                    ? "page was short"
                    : "not published"}
                </span>
              ) : (
                <span className="num text-sm font-bold text-slate-700">
                  {v}
                  <span className="text-slate-400">/7</span>
                </span>
              )}
            </div>

            <div
              className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100"
              role="img"
              aria-label={
                missing
                  ? `${DIMENSION_LABELS[key]}: ${labels?.[key] ?? "unavailable"}`
                  : `${DIMENSION_LABELS[key]}: ${v} of 7`
              }
            >
              {missing ? (
                <div className="h-full w-full bg-[repeating-linear-gradient(45deg,#F1F5F9_0_6px,#E2E8F0_6px_12px)]" />
              ) : (
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: ordinalHex(v) }}
                  initial={reduce ? false : { width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{
                    duration: 0.7,
                    delay: reduce ? 0 : i * 0.07,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                />
              )}
            </div>

            {!compact && (
              <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
                {missing ? (
                  explain(key)
                ) : (
                  <>
                    <span className="font-medium text-slate-600">
                      {labels?.[key] ?? ""}
                    </span>
                    {labels?.[key] ? " — " : ""}
                    {DIMENSION_BLURBS[key]}
                  </>
                )}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
