"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import {
  Search, SlidersHorizontal, ChevronLeft, ChevronRight, Star,
  MessagesSquare, Inbox,
} from "lucide-react";
import type { CheckSummary, Platform, TrustLevel } from "@/lib/types";
import { MiniGauge } from "./trust-gauge";
import { TrustBadge, PlatformBadge } from "./badges";
import { compact, stars, timeAgo, PLATFORM_LABEL } from "@/lib/format";

const PLATFORMS: Platform[] = ["AMAZON", "GOOGLE_PLAY", "APP_STORE"];
const LEVELS: TrustLevel[] = [
  "AUTHENTIC",
  "SUSPICIOUS",
  "MANIPULATED",
  "INCONCLUSIVE",
];
const PAGE = 12;

type Sort = "score" | "newest" | "reviews";

export function ResultCards({
  items,
  initialQuery = "",
}: {
  items: CheckSummary[];
  initialQuery?: string;
}) {
  const reduce = useReducedMotion();
  const [q, setQ] = useState(initialQuery);
  const [platform, setPlatform] = useState<Platform | "ALL">("ALL");
  const [level, setLevel] = useState<TrustLevel | "ALL">("ALL");
  const [sort, setSort] = useState<Sort>("newest");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const out = items.filter((it) => {
      if (platform !== "ALL" && it.platform !== platform) return false;
      if (level !== "ALL" && it.trust_level !== level) return false;
      if (
        needle &&
        !`${it.title} ${it.url_key}`.toLowerCase().includes(needle)
      )
        return false;
      return true;
    });
    out.sort((a, b) => {
      if (sort === "score") {
        // INCONCLUSIVE has no score, so it sorts LAST rather than as a zero —
        // a page nobody could read is not the worst page, it is an unknown one.
        const av = a.trust_level === "INCONCLUSIVE" ? -1 : a.overall;
        const bv = b.trust_level === "INCONCLUSIVE" ? -1 : b.overall;
        return bv - av;
      }
      if (sort === "reviews") return b.reviews_parsed - a.reviews_parsed;
      return b.check_id - a.check_id;
    });
    return out;
  }, [items, q, platform, level, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const current = Math.min(page, pages - 1);
  const slice = filtered.slice(current * PAGE, current * PAGE + PAGE);

  const reset = (fn: () => void) => {
    fn();
    setPage(0);
  };

  return (
    <div>
      {/* ─────────────────────────────────────────────── controls */}
      <div className="card mb-6 p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              value={q}
              onChange={(e) => reset(() => setQ(e.target.value))}
              placeholder="Search by product name or key…"
              className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <SlidersHorizontal
              size={15}
              className="shrink-0 text-slate-400"
              aria-hidden="true"
            />
            <select
              value={sort}
              onChange={(e) => reset(() => setSort(e.target.value as Sort))}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-indigo-500"
              aria-label="Sort results"
            >
              <option value="newest">Newest</option>
              <option value="score">Highest score</option>
              <option value="reviews">Most reviews read</option>
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-4">
          <Chips
            label="Platform"
            value={platform}
            onChange={(v) => reset(() => setPlatform(v as Platform | "ALL"))}
            options={[
              { key: "ALL", label: "All" },
              ...PLATFORMS.map((p) => ({ key: p, label: PLATFORM_LABEL[p] })),
            ]}
          />
          <Chips
            label="Trust level"
            value={level}
            onChange={(v) => reset(() => setLevel(v as TrustLevel | "ALL"))}
            options={[
              { key: "ALL", label: "All" },
              ...LEVELS.map((l) => ({
                key: l,
                label: l.charAt(0) + l.slice(1).toLowerCase(),
              })),
            ]}
          />
        </div>
      </div>

      <p className="mb-4 text-sm text-slate-500">
        <span className="num font-semibold text-slate-700">
          {filtered.length}
        </span>{" "}
        {filtered.length === 1 ? "result" : "results"}
        {filtered.length !== items.length && (
          <> of {items.length} checked</>
        )}
      </p>

      {/* ─────────────────────────────────────────────── the grid */}
      {slice.length === 0 ? (
        <EmptyState hasAny={items.length > 0} />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {slice.map((it, i) => (
            <motion.li
              key={it.check_id}
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: reduce ? 0 : i * 0.03 }}
            >
              <Link href={`/result/${it.check_id}`} className="block h-full">
                <article className="card card-hover flex h-full flex-col p-5">
                  <div className="flex items-start gap-3">
                    <MiniGauge
                      score={it.overall}
                      level={it.trust_level}
                      size={54}
                    />
                    <div className="min-w-0 flex-1">
                      <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">
                        {it.title || it.url_key}
                      </h3>
                      <div className="mt-1.5">
                        <PlatformBadge platform={it.platform} size="sm" />
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <TrustBadge level={it.trust_level} size="sm" />
                  </div>

                  <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-xs">
                    <div>
                      <dt className="flex items-center gap-1 text-slate-400">
                        <MessagesSquare size={11} aria-hidden="true" />
                        Reviews read
                      </dt>
                      <dd className="num mt-0.5 font-semibold text-slate-700">
                        {it.reviews_parsed}
                      </dd>
                    </div>
                    <div>
                      <dt className="flex items-center gap-1 text-slate-400">
                        <Star size={11} aria-hidden="true" />
                        Listed rating
                      </dt>
                      <dd className="num mt-0.5 font-semibold text-slate-700">
                        {stars(it.avg_rating_x10)}
                        {it.total_ratings ? (
                          <span className="ml-1 font-normal text-slate-400">
                            ({compact(it.total_ratings)})
                          </span>
                        ) : null}
                      </dd>
                    </div>
                  </dl>

                  <p className="mt-3 text-[11px] text-slate-400">
                    Checked {timeAgo(it.checked_at)} · measurable weight{" "}
                    <span className="num">{it.available_weight}/100</span>
                  </p>
                </article>
              </Link>
            </motion.li>
          ))}
        </ul>
      )}

      {/* ─────────────────────────────────────────────── pagination */}
      {pages > 1 && (
        <nav className="mt-8 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={current === 0}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-600 disabled:opacity-40"
          >
            <ChevronLeft size={15} aria-hidden="true" /> Previous
          </button>
          <span className="num px-3 text-sm text-slate-500">
            {current + 1} / {pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            disabled={current >= pages - 1}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-600 disabled:opacity-40"
          >
            Next <ChevronRight size={15} aria-hidden="true" />
          </button>
        </nav>
      )}
    </div>
  );
}

function Chips({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { key: string; label: string }[];
}) {
  return (
    <div>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </span>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button
            key={o.key}
            onClick={() => onChange(o.key)}
            className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
              value === o.key
                ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ hasAny }: { hasAny: boolean }) {
  return (
    <div className="card flex flex-col items-center px-6 py-16 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-slate-400">
        <Inbox size={22} strokeWidth={2} aria-hidden="true" />
      </span>
      <h3 className="mt-4 font-semibold text-slate-800">
        {hasAny ? "Nothing matches those filters" : "No checks yet"}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-slate-500">
        {hasAny
          ? "Try widening the platform or trust-level filter, or clearing the search."
          : "Be the first — paste a product URL and the validators will read it for you."}
      </p>
      <Link
        href="/check"
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
      >
        <Search size={15} strokeWidth={2.3} aria-hidden="true" />
        Check a product
      </Link>
    </div>
  );
}
