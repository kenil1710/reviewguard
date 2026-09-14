"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import type { TrustLevel } from "@/lib/types";
import { TRUST_STYLE } from "@/lib/format";

/**
 * A 270° arc showing the overall score.
 *
 * 270° rather than a full circle because a full ring has no beginning and the
 * eye cannot tell 5% from 95% at a glance. The gap at the bottom is the zero
 * point, and the arc fills clockwise from it.
 *
 * An INCONCLUSIVE check renders the track and NO fill, with a dash where the
 * number goes. Drawing a zero-length arc would be indistinguishable from a
 * score of zero, and those are not the same claim.
 */
export function TrustGauge({
  score,
  level,
  size = 220,
  stroke = 16,
  label = true,
}: {
  score: number;
  level: TrustLevel;
  size?: number;
  stroke?: number;
  label?: boolean;
}) {
  const reduce = useReducedMotion();
  const inconclusive = level === "INCONCLUSIVE";
  const style = TRUST_STYLE[level];
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const sweep = 0.75; // 270 of 360
  const track = c * sweep;
  const filled = track * Math.max(0, Math.min(100, score)) / 100;

  const [shown, setShown] = useState(reduce ? score : 0);
  useEffect(() => {
    if (reduce || inconclusive) {
      setShown(score);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const dur = 900;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      // ease-out cubic: fast to roughly the right answer, then settles
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.round(score * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [score, reduce, inconclusive]);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={
        inconclusive
          ? "Trust score unavailable: inconclusive"
          : `Trust score ${score} out of 100, ${style.label}`
      }
    >
      <svg width={size} height={size} className="-rotate-[225deg]">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${track} ${c}`}
        />
        {!inconclusive && (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={style.hex}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${c}`}
            initial={reduce ? false : { strokeDasharray: `0 ${c}` }}
            animate={{ strokeDasharray: `${filled} ${c}` }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {inconclusive ? (
          <>
            <span className="num text-4xl font-bold text-slate-400">—</span>
            <span className="mt-1 text-[11px] font-medium uppercase tracking-wider text-slate-400">
              No score
            </span>
          </>
        ) : (
          <>
            <span
              className="num font-bold leading-none"
              style={{ fontSize: size / 4.2, color: style.hex }}
            >
              {shown}
            </span>
            {label && (
              <span className="mt-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {style.label}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** A compact ring for cards, where 220px is far too much. */
export function MiniGauge({
  score,
  level,
  size = 56,
}: {
  score: number;
  level: TrustLevel;
  size?: number;
}) {
  const reduce = useReducedMotion();
  const inconclusive = level === "INCONCLUSIVE";
  const style = TRUST_STYLE[level];
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const filled = (c * 0.75 * Math.max(0, Math.min(100, score))) / 100;

  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg width={size} height={size} className="-rotate-[225deg]">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${c * 0.75} ${c}`}
        />
        {!inconclusive && (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={style.hex}
            strokeWidth={stroke}
            strokeLinecap="round"
            initial={reduce ? false : { strokeDasharray: `0 ${c}` }}
            animate={{ strokeDasharray: `${filled} ${c}` }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          />
        )}
      </svg>
      <span
        className="num absolute inset-0 flex items-center justify-center text-sm font-bold"
        style={{ color: inconclusive ? "#94A3B8" : style.hex }}
      >
        {inconclusive ? "—" : score}
      </span>
    </div>
  );
}
