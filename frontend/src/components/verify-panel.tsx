"use client";

import { useState } from "react";
import { ShieldCheck, Loader2, XCircle, CheckCircle2, RefreshCw } from "lucide-react";
import type { VerifyResult } from "@/lib/types";

/**
 * Recompute a stored check from its own stored evidence.
 *
 * This is the button that makes the record auditable without trusting anybody:
 * the contract reads the vector back out of storage, runs the rubric on it
 * again, and compares every derived field to what was written. A reader does
 * not have to take the score on faith — they can make the chain redo it.
 */
export function VerifyPanel({
  checkId,
  contentHash,
}: {
  checkId: number;
  contentHash: string;
}) {
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [result, setResult] = useState<VerifyResult | null>(null);

  const run = async () => {
    setState("busy");
    try {
      const res = await fetch(`/api/verify?id=${checkId}`);
      const json = (await res.json()) as VerifyResult;
      setResult(json);
      setState("done");
    } catch {
      setState("error");
    }
  };

  return (
    <div className="card p-6">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
          <ShieldCheck size={19} strokeWidth={2.2} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-slate-900">Verify this check</h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            Ask the contract to recompute the score from the evidence it stored,
            and compare every derived field to what was written. Nothing here is
            taken on trust — not even by us.
          </p>

          <p className="num mt-3 break-all rounded-lg bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
            {contentHash}
          </p>

          <button
            onClick={run}
            disabled={state === "busy"}
            className="mt-4 inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 disabled:opacity-60"
          >
            {state === "busy" ? (
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
            ) : state === "done" ? (
              <RefreshCw size={15} strokeWidth={2.2} aria-hidden="true" />
            ) : (
              <ShieldCheck size={15} strokeWidth={2.2} aria-hidden="true" />
            )}
            {state === "busy"
              ? "Recomputing…"
              : state === "done"
                ? "Verify again"
                : "Recompute from evidence"}
          </button>

          {state === "error" && (
            <p className="mt-3 text-sm text-rose-700">
              The network did not answer just now. Try again in a moment.
            </p>
          )}

          {state === "done" && result && (
            <div
              className={`mt-4 rounded-xl border p-4 ${
                result.verified
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-rose-200 bg-rose-50"
              }`}
            >
              <div className="flex items-center gap-2">
                {result.verified ? (
                  <CheckCircle2
                    size={17}
                    className="text-emerald-600"
                    strokeWidth={2.3}
                    aria-hidden="true"
                  />
                ) : (
                  <XCircle
                    size={17}
                    className="text-rose-600"
                    strokeWidth={2.3}
                    aria-hidden="true"
                  />
                )}
                <p
                  className={`text-sm font-semibold ${
                    result.verified ? "text-emerald-900" : "text-rose-900"
                  }`}
                >
                  {result.verified
                    ? "Verified — every stored field matches the rubric"
                    : "Mismatch — this record was not produced by the rubric it claims"}
                </p>
              </div>

              {result.verified && result.recomputed && (
                <dl className="mt-3 grid gap-2 text-xs text-emerald-900 sm:grid-cols-2">
                  <div className="flex justify-between gap-3">
                    <dt>Recomputed score</dt>
                    <dd className="num font-semibold">
                      {result.recomputed.overall}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Trust level</dt>
                    <dd className="font-semibold">
                      {result.recomputed.trust_level}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Measurable weight</dt>
                    <dd className="num font-semibold">
                      {result.recomputed.available_weight}/100
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Rubric</dt>
                    <dd className="num font-semibold">
                      {result.rubric_version}
                    </dd>
                  </div>
                </dl>
              )}

              {!result.verified && result.mismatches?.length ? (
                <ul className="mt-3 space-y-1 text-xs text-rose-900">
                  {result.mismatches.map((m) => (
                    <li key={m.field} className="num">
                      <strong>{m.field}</strong>: stored {String(m.stored)},
                      recomputed {String(m.recomputed)}
                    </li>
                  ))}
                </ul>
              ) : null}

              {!result.verified && result.reason && (
                <p className="mt-2 text-xs text-rose-900">{result.reason}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
