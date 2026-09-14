"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Star, ShieldCheck, ShieldX } from "lucide-react";

/**
 * The hero visual: a magnifier sweeping a stack of review cards, with the
 * suspicious ones lighting up as it passes.
 *
 * Built from the same trust colours the rest of the site uses, so a reader who
 * has seen the landing page already knows what rose means before they reach a
 * result. Purely decorative — `aria-hidden`, and every motion is gated on the
 * reader's reduced-motion preference.
 */
export function HeroVisual() {
  const reduce = useReducedMotion();

  const rows = [
    { stars: 5, w: "88%", fake: true, name: "Mike2847" },
    { stars: 5, w: "62%", fake: true, name: "Amazon Customer" },
    { stars: 4, w: "96%", fake: false, name: "Priya S." },
    { stars: 5, w: "70%", fake: true, name: "user91023" },
    { stars: 2, w: "92%", fake: false, name: "Marcus Webb" },
    { stars: 5, w: "58%", fake: true, name: "Jooooooe" },
  ];

  return (
    <div
      aria-hidden="true"
      className="relative mx-auto w-full max-w-[440px] select-none"
    >
      {/* soft brand glow behind the stack */}
      <div className="pointer-events-none absolute -inset-8 rounded-[3rem] bg-gradient-to-br from-indigo-200/50 via-indigo-100/30 to-transparent blur-2xl" />

      <div className="relative card overflow-hidden p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-slate-200 to-slate-300" />
            <div>
              <div className="h-2.5 w-28 rounded-full bg-slate-300" />
              <div className="mt-1.5 h-2 w-16 rounded-full bg-slate-200" />
            </div>
          </div>
          <div className="num rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-500">
            4.9 ★
          </div>
        </div>

        <ul className="space-y-3">
          {rows.map((r, i) => (
            <motion.li
              key={i}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reduce ? 0 : 0.15 + i * 0.09, duration: 0.4 }}
              className="relative rounded-xl border border-slate-100 bg-slate-50/60 p-3"
            >
              <div className="flex items-center gap-2">
                <div className="flex gap-0.5">
                  {Array.from({ length: 5 }).map((_, s) => (
                    <Star
                      key={s}
                      size={11}
                      strokeWidth={0}
                      fill={s < r.stars ? "#F59E0B" : "#E2E8F0"}
                    />
                  ))}
                </div>
                <span className="text-[10px] font-medium text-slate-400">
                  {r.name}
                </span>
                <motion.span
                  initial={reduce ? false : { opacity: 0, scale: 0.7 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{
                    delay: reduce ? 0 : 1.1 + i * 0.12,
                    duration: 0.35,
                  }}
                  className={`ml-auto inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
                    r.fake
                      ? "bg-rose-50 text-rose-600"
                      : "bg-emerald-50 text-emerald-600"
                  }`}
                >
                  {r.fake ? (
                    <ShieldX size={9} strokeWidth={2.6} />
                  ) : (
                    <ShieldCheck size={9} strokeWidth={2.6} />
                  )}
                  {r.fake ? "suspect" : "organic"}
                </motion.span>
              </div>
              <div className="mt-2 space-y-1">
                <div
                  className="h-1.5 rounded-full bg-slate-200"
                  style={{ width: r.w }}
                />
                <div
                  className="h-1.5 rounded-full bg-slate-200/70"
                  style={{ width: r.fake ? "34%" : "78%" }}
                />
              </div>
            </motion.li>
          ))}
        </ul>

        {/* the sweeping scan line */}
        {!reduce && (
          <motion.div
            className="pointer-events-none absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-indigo-400/12 to-transparent"
            initial={{ top: "-10%" }}
            animate={{ top: ["-10%", "100%"] }}
            transition={{
              duration: 3.4,
              repeat: Infinity,
              ease: "easeInOut",
              repeatDelay: 0.6,
            }}
          />
        )}
      </div>

      {/* the verdict chip, floating clear of the card */}
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 10, scale: 0.94 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ delay: reduce ? 0 : 1.9, duration: 0.45 }}
        className="absolute -bottom-6 -right-3 card flex items-center gap-3 px-4 py-3 shadow-lg"
      >
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-rose-50">
          <ShieldX size={20} className="text-rose-600" strokeWidth={2.3} />
        </span>
        <div>
          <div className="num text-xl font-bold leading-none text-rose-600">
            25
          </div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Manipulated
          </div>
        </div>
      </motion.div>
    </div>
  );
}
