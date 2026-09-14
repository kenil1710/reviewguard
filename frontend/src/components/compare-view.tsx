"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import {
  Search, Loader2, Trophy, ArrowRight, AlertTriangle, Minus,
} from "lucide-react";
import type { CheckRecord, CheckResult, DimensionKey } from "@/lib/types";
import { DIMENSIONS, DIMENSION_LABELS } from "@/lib/types";
import { TrustGauge } from "./trust-gauge";
import { TrustBadge, PlatformBadge } from "./badges";
import { ordinalHex } from "@/lib/format";

type Side = "a" | "b";
type Slot = { url: string; rec: CheckRecord | null; error: string | null; busy: boolean };

const EMPTY: Slot = { url: "", rec: null, error: null, busy: false };

export function CompareView({ initialA = "" }: { initialA?: string }) {
  const reduce = useReducedMotion();
  const [a, setA] = useState<Slot>({ ...EMPTY, url: initialA });
  const [b, setB] = useState<Slot>({ ...EMPTY });

  const load = useCallback(
    async (side: Side, url: string) => {
      const set = side === "a" ? setA : setB;
      const trimmed = url.trim();
      if (!trimmed) return;
      set((s) => ({ ...s, busy: true, error: null }));
      try {
        const res = await fetch(
          `/api/lookup?url=${encodeURIComponent(trimmed)}`,
        );
        const json = (await res.json()) as CheckResult;
        if ("found" in json && json.found) {
          set({ url: trimmed, rec: json, error: null, busy: false });
        } else {
          set({
            url: trimmed,
            rec: null,
            busy: false,
            error:
              ("reason" in json && json.reason) ||
              "That page has not been checked yet.",
          });
        }
      } catch {
        set((s) => ({
          ...s,
          busy: false,
          error: "The network did not answer just now.",
        }));
      }
    },
    [],
  );

  const both = a.rec && b.rec;
  const comparable =
    both &&
    a.rec!.trust_level !== "INCONCLUSIVE" &&
    b.rec!.trust_level !== "INCONCLUSIVE";
  const winner = comparable
    ? a.rec!.overall === b.rec!.overall
      ? null
      : a.rec!.overall > b.rec!.overall
        ? "a"
        : "b"
    : null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        {(["a", "b"] as Side[]).map((side) => {
          const slot = side === "a" ? a : b;
          const set = side === "a" ? setA : setB;
          return (
            <div key={side} className="card p-5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Product {side.toUpperCase()}
              </label>
              <div className="mt-2 flex gap-2">
                <div className="relative flex-1">
                  <Search
                    size={15}
                    aria-hidden="true"
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    value={slot.url}
                    onChange={(e) =>
                      set((s) => ({ ...s, url: e.target.value }))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") load(side, slot.url);
                    }}
                    placeholder="Paste a checked product URL…"
                    className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500"
                  />
                </div>
                <button
                  onClick={() => load(side, slot.url)}
                  disabled={slot.busy || !slot.url.trim()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:bg-slate-300"
                >
                  {slot.busy ? (
                    <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <ArrowRight size={15} strokeWidth={2.3} aria-hidden="true" />
                  )}
                  Load
                </button>
              </div>

              {slot.error && (
                <p className="mt-3 flex items-start gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <span>
                    {slot.error}{" "}
                    <Link href="/check" className="font-semibold underline">
                      Check it first
                    </Link>
                    .
                  </span>
                </p>
              )}

              {slot.rec && (
                <div className="mt-4 flex items-start gap-4 border-t border-slate-100 pt-4">
                  <TrustGauge
                    score={slot.rec.overall}
                    level={slot.rec.trust_level}
                    size={96}
                    stroke={8}
                    label={false}
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">
                      {slot.rec.title || slot.rec.url_key}
                    </h3>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <PlatformBadge platform={slot.rec.platform} size="sm" />
                      <TrustBadge level={slot.rec.trust_level} size="sm" />
                    </div>
                    <p className="num mt-2 text-[11px] text-slate-400">
                      {slot.rec.evidence.reviews_parsed} reviews read ·{" "}
                      {slot.rec.available_weight}/100 measurable
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ────────────────────────────────── the verdict */}
      {both && (
        <div className="card p-6 sm:p-7">
          {!comparable ? (
            <div className="flex items-start gap-3 rounded-xl bg-slate-50 p-4">
              <Minus size={17} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  These two cannot be ranked
                </p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">
                  At least one came back inconclusive, which is the absence of a
                  score rather than a low one. Ranking an unread page against a
                  measured one would be inventing a comparison the evidence does
                  not support.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Trophy size={17} className="text-amber-500" strokeWidth={2.2} aria-hidden="true" />
                <h2 className="font-semibold text-slate-900">
                  {winner === null
                    ? "A dead heat"
                    : `Product ${winner.toUpperCase()} has the more authentic reviews`}
                </h2>
              </div>
              <p className="mt-1.5 text-sm text-slate-600">
                {winner === null
                  ? "Both scored identically on the dimensions their platforms publish."
                  : `${Math.abs(a.rec!.overall - b.rec!.overall)} points apart on the 0–100 scale.`}
              </p>
            </>
          )}

          {/* dimension-by-dimension */}
          <ul className="mt-6 space-y-5">
            {DIMENSIONS.map((key: DimensionKey, i) => {
              const av = a.rec!.scores[key];
              const bv = b.rec!.scores[key];
              const bothHave = av !== null && bv !== null;
              return (
                <li key={key}>
                  <div className="mb-2 flex items-center justify-between text-xs">
                    <span className="num font-bold text-slate-700">
                      {av === null ? "—" : av}
                    </span>
                    <span className="font-semibold text-slate-600">
                      {DIMENSION_LABELS[key]}
                      <span className="num ml-1.5 font-medium text-slate-400">
                        {a.rec!.weights[key]}%
                      </span>
                    </span>
                    <span className="num font-bold text-slate-700">
                      {bv === null ? "—" : bv}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex h-2.5 flex-1 justify-end overflow-hidden rounded-full bg-slate-100">
                      {av !== null && (
                        <motion.div
                          className="h-full rounded-full"
                          style={{ background: ordinalHex(av) }}
                          initial={reduce ? false : { width: 0 }}
                          animate={{ width: `${(av / 7) * 100}%` }}
                          transition={{ duration: 0.6, delay: reduce ? 0 : i * 0.06 }}
                        />
                      )}
                    </div>
                    <span
                      className={`w-16 shrink-0 text-center text-[10px] font-semibold uppercase tracking-wide ${
                        !bothHave
                          ? "text-slate-300"
                          : av! > bv!
                            ? "text-emerald-600"
                            : av! < bv!
                              ? "text-indigo-600"
                              : "text-slate-400"
                      }`}
                    >
                      {!bothHave ? "n/a" : av! > bv! ? "◀ A" : av! < bv! ? "B ▶" : "tie"}
                    </span>
                    <div className="flex h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      {bv !== null && (
                        <motion.div
                          className="h-full rounded-full"
                          style={{ background: ordinalHex(bv) }}
                          initial={reduce ? false : { width: 0 }}
                          animate={{ width: `${(bv / 7) * 100}%` }}
                          transition={{ duration: 0.6, delay: reduce ? 0 : i * 0.06 }}
                        />
                      )}
                    </div>
                  </div>
                  {!bothHave && (
                    <p className="mt-1.5 text-center text-[11px] text-slate-400">
                      One of these platforms does not publish this signal, so the
                      dimension is not compared.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>

          <div className="mt-6 flex flex-wrap gap-3 border-t border-slate-100 pt-5">
            <Link
              href={`/result/${a.rec!.check_id}`}
              className="text-sm font-semibold text-indigo-600 hover:underline"
            >
              Full breakdown for A →
            </Link>
            <Link
              href={`/result/${b.rec!.check_id}`}
              className="text-sm font-semibold text-indigo-600 hover:underline"
            >
              Full breakdown for B →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
