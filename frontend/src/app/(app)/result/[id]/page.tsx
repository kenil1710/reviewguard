import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ExternalLink, ArrowLeft, Clock, Wallet, Scale, Info, GitCompare,
  AlertTriangle,
} from "lucide-react";
import { TrustGauge } from "@/components/trust-gauge";
import { DimensionBars } from "@/components/dimension-bars";
import { TrustBadge, PlatformBadge } from "@/components/badges";
import { EvidencePanel } from "@/components/evidence-panel";
import { VerifyPanel } from "@/components/verify-panel";
import { safeCheck } from "@/lib/oracle";
import { timeAgo, shortAddress } from "@/lib/format";
import { txUrl } from "@/lib/genlayer";

export const revalidate = 30;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const rec = await safeCheck(Number(id));
  if (!rec || !("found" in rec) || !rec.found) return { title: "Check" };
  return {
    title: `${rec.title || rec.url_key} — ${rec.trust_level}`,
    description: `ReviewGuard scored this page ${rec.overall}/100 across five manipulation signals.`,
  };
}

export default async function ResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const n = Number(id);
  if (!Number.isFinite(n) || n <= 0) notFound();

  const rec = await safeCheck(n);
  if (!rec) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 text-center sm:px-6">
        <h1 className="text-2xl font-bold text-slate-900">
          The network did not answer
        </h1>
        <p className="mt-2 text-slate-600">
          This page reads the contract live. Refresh in a moment.
        </p>
      </div>
    );
  }
  if (!("found" in rec) || !rec.found) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 sm:px-6">
        <div className="card p-8 text-center">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-slate-400">
            <AlertTriangle size={22} strokeWidth={2} aria-hidden="true" />
          </span>
          <h1 className="mt-4 text-xl font-bold text-slate-900">
            No check with that id
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            {("reason" in rec && rec.reason) ||
              "It may have rotated out of the history window this page keeps."}
          </p>
          <Link
            href="/results"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            <ArrowLeft size={15} aria-hidden="true" /> Browse results
          </Link>
        </div>
      </div>
    );
  }

  const inconclusive = rec.trust_level === "INCONCLUSIVE";

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <Link
        href="/results"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-indigo-600"
      >
        <ArrowLeft size={15} aria-hidden="true" /> All results
      </Link>

      <div className="mt-5 grid gap-6 lg:grid-cols-[1.45fr_1fr]">
        {/* ────────────────────────────────── left: identity */}
        <div className="card p-6 sm:p-7">
          <div className="flex flex-wrap items-center gap-2">
            <PlatformBadge platform={rec.platform} />
            <TrustBadge level={rec.trust_level} size="lg" />
          </div>

          <h1 className="mt-4 text-2xl font-bold leading-tight tracking-tight text-slate-900">
            {rec.title || rec.url_key}
          </h1>
          <p className="num mt-2 break-all text-xs text-slate-400">
            {rec.url_key}
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            {rec.source_url && (
              <a
                href={rec.source_url}
                target="_blank"
                rel="noreferrer nofollow"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50"
              >
                <ExternalLink size={14} strokeWidth={2.1} aria-hidden="true" />
                Open the original page
              </a>
            )}
            <Link
              href={`/compare?a=${encodeURIComponent(rec.source_url)}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50"
            >
              <GitCompare size={14} strokeWidth={2.1} aria-hidden="true" />
              Compare with another
            </Link>
          </div>

          <dl className="mt-6 grid gap-4 border-t border-slate-100 pt-5 text-sm sm:grid-cols-3">
            <div>
              <dt className="flex items-center gap-1 text-xs text-slate-400">
                <Clock size={12} aria-hidden="true" /> Checked
              </dt>
              <dd className="mt-0.5 font-semibold text-slate-800">
                {timeAgo(rec.checked_at)}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1 text-xs text-slate-400">
                <Wallet size={12} aria-hidden="true" /> Submitted by
              </dt>
              <dd className="num mt-0.5 font-semibold text-slate-800">
                {shortAddress(rec.checker)}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1 text-xs text-slate-400">
                <Scale size={12} aria-hidden="true" /> Rubric
              </dt>
              <dd className="num mt-0.5 font-semibold text-slate-800">
                v{rec.rubric_version}
              </dd>
            </div>
          </dl>
        </div>

        {/* ────────────────────────────────── right: score */}
        <div className="card flex flex-col items-center justify-center p-6 sm:p-7">
          <TrustGauge score={rec.overall} level={rec.trust_level} size={210} />

          {inconclusive ? (
            <div className="mt-5 rounded-xl bg-slate-50 px-4 py-3 text-center">
              <p className="text-sm font-semibold text-slate-700">
                Not enough evidence to judge
              </p>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">
                Only{" "}
                <span className="num font-semibold">
                  {rec.evidence.reviews_parsed}
                </span>{" "}
                individual{" "}
                {rec.evidence.reviews_parsed === 1 ? "review" : "reviews"}{" "}
                rendered, and{" "}
                <span className="num font-semibold">
                  {rec.available_weight}/100
                </span>{" "}
                of the rubric could be measured. ReviewGuard says so rather than
                guessing — this is <strong>not</strong> a low score.
              </p>
            </div>
          ) : (
            <p className="mt-5 text-center text-xs leading-relaxed text-slate-500">
              Weighted across{" "}
              <span className="num font-semibold text-slate-700">
                {rec.available_weight}/100
              </span>{" "}
              of the rubric that this platform publishes, quantised to the
              nearest 5.
            </p>
          )}
        </div>
      </div>

      {/* ────────────────────────────────── dimensions */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.45fr_1fr]">
        <div className="card p-6 sm:p-7">
          <h2 className="font-semibold text-slate-900">
            The five signals
          </h2>
          <p className="mt-1.5 text-sm text-slate-600">
            Each is an ordinal from 0 to 7, where 0 is the worst outcome. Every
            validator had to arrive at the same number.
          </p>
          <div className="mt-6">
            <DimensionBars
              scores={rec.scores}
              labels={rec.labels}
              weights={rec.weights}
            />
          </div>

          <p className="mt-6 flex items-start gap-2 rounded-xl bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-500">
            <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>
              Reviewer credibility on this platform is judged on{" "}
              <strong className="font-semibold text-slate-700">
                {rec.credibility_basis}
              </strong>
              .{" "}
              {rec.credibility_basis === "verified-purchase"
                ? "The platform states outright whether a reviewer bought the item, which is the strongest basis available."
                : "This platform publishes no purchase signal, so all that can be read is whether the reviewer identities look chosen or generated — a weaker basis, and the reason this dimension starts from neutral rather than from zero."}
            </span>
          </p>
        </div>

        <VerifyPanel checkId={rec.check_id} contentHash={rec.content_hash} />
      </div>

      {/* ────────────────────────────────── evidence */}
      <div className="mt-6">
        <EvidencePanel evidence={rec.evidence} platform={rec.platform} />
      </div>
    </div>
  );
}
