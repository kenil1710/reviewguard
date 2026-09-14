"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Search, Loader2, AlertTriangle, ExternalLink, CheckCircle2, Info,
  ShoppingCart, Play, Apple, Clock, PauseCircle, ArrowRight,
} from "lucide-react";
import type { Detection, Platform, CheckResult } from "@/lib/types";
import { PLATFORM_LABEL } from "@/lib/format";
import { rememberPending, readPending, forgetPending } from "@/lib/pending";

const SUPPORTED: { key: Platform; Icon: typeof ShoppingCart; hint: string }[] = [
  { key: "AMAZON", Icon: ShoppingCart, hint: "amazon.com/dp/B07FZ8S74R" },
  { key: "GOOGLE_PLAY", Icon: Play, hint: "play.google.com/store/apps/details?id=com.whatsapp" },
  { key: "APP_STORE", Icon: Apple, hint: "apps.apple.com/us/app/…/id310633997" },
];

const PLATFORM_ICON: Record<Platform, typeof ShoppingCart> = {
  AMAZON: ShoppingCart,
  GOOGLE_PLAY: Play,
  APP_STORE: Apple,
};

type Phase =
  | "idle"
  | "detecting"
  | "submitting"
  | "waiting"
  | "done"
  | "error"
  | "recovering";

export function CheckForm({ examples }: { examples: string[] }) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  // The detection is stored WITH the URL it describes, and only used when that
  // URL is still what is in the box. Clearing it in an effect would be both a
  // cascading render and a lie for one frame — the old platform badge would
  // still be on screen for a URL it was never about.
  const [detected, setDetected] = useState<{ url: string; result: Detection } | null>(
    null,
  );
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [resumed, setResumed] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * Recover a check the visitor started and then navigated away from.
   *
   * A round takes 30-90 seconds and people do not sit still for it. The URL
   * was written to storage before the request went out, so on the way back in
   * we ask the contract whether it has a record yet: if it does, the visitor
   * lands on their result; if it does not, they are told it is still running
   * rather than shown an empty form.
   */
  useEffect(() => {
    let alive = true;
    (async () => {
      const pending = readPending();
      if (!pending || !alive) return;
      setPhase("recovering");
      setResumed(pending.url);
      for (let i = 0; i < 40 && alive; i++) {
        try {
          const res = await fetch(
            `/api/lookup?url=${encodeURIComponent(pending.url)}`,
          );
          const rec = (await res.json()) as CheckResult;
          if (!alive) return;
          if (rec && "found" in rec && rec.found) {
            forgetPending();
            setPhase("done");
            router.push(`/result/${rec.check_id}`);
            return;
          }
        } catch {
          /* a bad minute on the RPC is not a finished check */
        }
        await new Promise((r) => setTimeout(r, 5000));
      }
      if (!alive) return;
      // It never arrived. Clear it rather than leaving a permanent banner.
      forgetPending();
      setPhase("idle");
      setResumed(null);
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  /** Detection is debounced and runs against the SAME contract view the write
   *  path uses. A preview that disagreed with the submission would be worse
   *  than no preview at all. */
  useEffect(() => {
    const trimmed = url.trim();
    if (!trimmed) return;
    let alive = true;
    const t = setTimeout(async () => {
      // Set inside the debounce rather than before it. A synchronous setState
      // in an effect body is a cascading render, and "detecting" is only true
      // once the request is actually going out.
      if (alive) {
        setPhase((p) => (p === "waiting" || p === "submitting" ? p : "detecting"));
      }
      try {
        const res = await fetch(
          `/api/detect?url=${encodeURIComponent(trimmed)}`,
        );
        const json = (await res.json()) as Detection;
        if (!alive) return;
        setDetected({ url: trimmed, result: json });
        setPhase((p) => (p === "detecting" ? "idle" : p));
      } catch {
        if (alive) setPhase((p) => (p === "detecting" ? "idle" : p));
      }
    }, 350);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [url]);

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    [],
  );

  const detection =
    detected && detected.url === url.trim() ? detected.result : null;

  const submit = useCallback(async () => {
    const trimmed = url.trim();
    if (!trimmed || !detected || detected.url !== trimmed) return;
    if (!detected.result.supported) return;
    setError(null);
    setPhase("submitting");
    setElapsed(0);
    // Written down BEFORE the request goes out. The failure being fixed is the
    // one where the answer arrives while nobody is listening.
    rememberPending(trimmed);
    timer.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    try {
      const res = await fetch("/api/check", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });
      setPhase("waiting");
      const json = (await res.json()) as {
        ok: boolean;
        check_id?: number;
        url_key?: string;
        reason?: string;
        status?: string;
      };
      if (timer.current) clearInterval(timer.current);
      if (!json.ok) {
        forgetPending();
        setError(json.reason ?? "The check could not be completed.");
        setPhase("error");
        return;
      }
      forgetPending();
      setPhase("done");
      // The "done" panel paints first, so the visitor is told what happened
      // rather than being teleported mid-spinner.
      setTimeout(() => router.push(`/result/${json.check_id}`), 700);
    } catch (e) {
      if (timer.current) clearInterval(timer.current);
      // The request died, but the transaction may well be settling. Leave the
      // pending marker so the next visit can still recover the result.
      setError(String((e as Error)?.message ?? e));
      setPhase("error");
    }
  }, [url, detected, router]);

  const busy =
    phase === "submitting" || phase === "waiting" || phase === "recovering";
  const Icon =
    detection?.supported && detection.platform
      ? PLATFORM_ICON[detection.platform as Platform]
      : null;

  return (
    <div className="space-y-6">
      <div className="card p-6 sm:p-7">
        <label
          htmlFor="url"
          className="block text-sm font-semibold text-slate-800"
        >
          Product review page URL
        </label>
        <p className="mt-1 text-sm text-slate-500">
          The platform is detected from the link — you do not need to pick one.
        </p>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search
              size={17}
              strokeWidth={2.1}
              aria-hidden="true"
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              id="url"
              type="url"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && detection?.supported && !busy) submit();
              }}
              disabled={busy}
              placeholder="https://www.amazon.com/dp/B07FZ8S74R"
              className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3 text-sm text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 disabled:bg-slate-50"
            />
          </div>
          <button
            onClick={submit}
            disabled={!detection?.supported || busy}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {busy ? (
              <Loader2 size={17} className="animate-spin" aria-hidden="true" />
            ) : (
              <Search size={17} strokeWidth={2.3} aria-hidden="true" />
            )}
            {busy ? "Analysing…" : "Check reviews"}
          </button>
        </div>

        {/* ─────────────────────────── the preview card */}
        {detection && url.trim() && !busy && (
          <div
            className={`mt-4 rounded-xl border p-4 ${
              detection.supported
                ? "border-indigo-200 bg-indigo-50/60"
                : "border-amber-200 bg-amber-50"
            }`}
          >
            {detection.supported ? (
              <div className="flex items-start gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white text-indigo-600 shadow-sm">
                  {Icon ? (
                    <Icon size={17} strokeWidth={2.2} aria-hidden="true" />
                  ) : (
                    <CheckCircle2 size={17} aria-hidden="true" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-900">
                    {PLATFORM_LABEL[detection.platform as Platform]} detected
                  </p>
                  <p className="num mt-0.5 truncate text-xs text-slate-500">
                    {detection.url_key}
                  </p>
                  <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-600">
                    <span>
                      Measurable weight:{" "}
                      <strong className="num font-semibold text-slate-800">
                        {detection.available_weight}/100
                      </strong>
                    </span>
                    <span>
                      Credibility basis:{" "}
                      <strong className="font-semibold text-slate-800">
                        {detection.credibility_basis}
                      </strong>
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Info size={12} aria-hidden="true" />
                      Fee: <strong className="font-semibold text-emerald-700">free</strong>
                    </span>
                  </div>
                  {detection.already_checked && (
                    <p className="mt-2.5 flex items-center gap-1.5 text-xs text-slate-600">
                      <Clock size={12} aria-hidden="true" />
                      This page has been checked before.{" "}
                      <Link
                        href={`/results?q=${encodeURIComponent(detection.url_key)}`}
                        className="font-medium text-indigo-600 hover:underline"
                      >
                        See the existing result
                      </Link>
                      .
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3">
                <AlertTriangle
                  size={17}
                  className="mt-0.5 shrink-0 text-amber-600"
                  strokeWidth={2.2}
                  aria-hidden="true"
                />
                <div>
                  <p className="text-sm font-semibold text-amber-900">
                    ReviewGuard cannot read that page
                  </p>
                  <p className="mt-0.5 text-sm text-amber-800">
                    {detection.reason}
                  </p>
                  <p className="mt-2 text-xs text-amber-700">
                    Trustpilot, Yelp and Google Maps were measured and block
                    validators outright —{" "}
                    <Link href="/docs#platforms" className="font-medium underline">
                      see what we tried
                    </Link>
                    .
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─────────────────────────── recovered from a previous visit */}
        {phase === "recovering" && resumed && (
          <div
            className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-5"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-start gap-3">
              <Loader2
                size={18}
                className="mt-0.5 shrink-0 animate-spin text-indigo-600"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-indigo-900">
                  Picking up the check you already started
                </p>
                <p className="num mt-1 truncate text-xs text-indigo-700">
                  {resumed}
                </p>
                <p className="mt-2 text-xs leading-relaxed text-indigo-800">
                  You left while the validators were working. Nothing was lost —
                  the transaction is on chain either way. As soon as the record
                  appears you will be taken straight to it.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ─────────────────────────── loading state */}
        {(phase === "submitting" || phase === "waiting") && (
          <div
            className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-5"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-center gap-3">
              <Loader2
                size={18}
                className="animate-spin text-indigo-600"
                aria-hidden="true"
              />
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-800">
                  {phase === "submitting"
                    ? "Submitting to the network…"
                    : "Validators are reading the page…"}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Each one loads the page in its own browser and must agree on
                  every number before anything is written down.
                </p>
              </div>
              <span className="num text-sm font-semibold text-slate-400">
                {elapsed}s
              </span>
            </div>

            <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5">
              <PauseCircle
                size={15}
                className="mt-0.5 shrink-0 text-amber-600"
                strokeWidth={2.2}
                aria-hidden="true"
              />
              <p className="text-xs leading-relaxed text-amber-900">
                <strong className="font-semibold">
                  Stay on this page — analysis takes 30–90 seconds.
                </strong>{" "}
                If you do navigate away, nothing is lost: come back here and the
                result will be waiting.
              </p>
            </div>

            <div className="mt-4 space-y-2.5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-2.5 rounded-full" style={{ width: `${90 - i * 18}%` }} />
              ))}
            </div>
          </div>
        )}

        {/* ─────────────────────────── success, before the redirect */}
        {phase === "done" && (
          <div
            className="mt-4 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5"
            role="status"
            aria-live="polite"
          >
            <CheckCircle2
              size={18}
              className="mt-0.5 shrink-0 text-emerald-600"
              strokeWidth={2.3}
              aria-hidden="true"
            />
            <div>
              <p className="text-sm font-semibold text-emerald-900">
                Analysis complete! Redirecting to results…
              </p>
              <p className="mt-1 flex items-center gap-1.5 text-xs text-emerald-800">
                <ArrowRight size={12} aria-hidden="true" />
                The result has a permanent URL — you can bookmark it or share it.
              </p>
            </div>
          </div>
        )}

        {/* ─────────────────────────── error state */}
        {phase === "error" && error && (
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4">
            <AlertTriangle
              size={17}
              className="mt-0.5 shrink-0 text-rose-600"
              strokeWidth={2.2}
              aria-hidden="true"
            />
            <div>
              <p className="text-sm font-semibold text-rose-900">
                That check did not complete
              </p>
              <p className="mt-0.5 text-sm text-rose-800">{error}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-rose-700">
                If the transaction reached the network it may still be settling.
                Nothing was charged either way — a refused check refunds its
                deposit. Check{" "}
                <Link href="/results" className="font-semibold underline">
                  Browse results
                </Link>{" "}
                in a minute before resubmitting.
              </p>
              <button
                onClick={() => {
                  setPhase("idle");
                  setError(null);
                }}
                className="mt-2 text-xs font-semibold text-rose-700 underline"
              >
                Try again
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ─────────────────────────── supported platforms */}
      <div className="card p-6">
        <h2 className="text-sm font-semibold text-slate-800">
          Supported platforms
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          These three were measured to render their reviews to a validator.
          Eleven others were tried and block it — the methodology page lists
          every one.
        </p>
        <ul className="mt-4 grid gap-3 sm:grid-cols-3">
          {SUPPORTED.map(({ key, Icon: I, hint }) => (
            <li
              key={key}
              className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5"
            >
              <div className="flex items-center gap-2 font-semibold text-slate-800">
                <I size={16} strokeWidth={2.2} aria-hidden="true" />
                <span className="text-sm">{PLATFORM_LABEL[key]}</span>
              </div>
              <p className="num mt-1.5 break-all text-[11px] leading-relaxed text-slate-500">
                {hint}
              </p>
            </li>
          ))}
        </ul>
      </div>

      {/* ─────────────────────────── try one */}
      {examples.length > 0 && (
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-slate-800">
            Or try one of these
          </h2>
          <ul className="mt-3 space-y-2">
            {examples.map((ex) => (
              <li key={ex}>
                <button
                  onClick={() => setUrl(ex)}
                  className="num w-full truncate rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-600 transition-colors hover:border-indigo-300 hover:text-indigo-700"
                >
                  {ex}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-400">
            <ExternalLink size={12} aria-hidden="true" />
            Public product pages, used here as examples of the URL shape.
          </p>
        </div>
      )}
    </div>
  );
}
