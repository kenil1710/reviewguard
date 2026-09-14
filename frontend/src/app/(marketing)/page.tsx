import Link from "next/link";
import {
  Search, ScanLine, Gauge, ShieldCheck, ArrowRight, Layers, Plug,
  Lock, Star, ShieldX, CircleHelp, Droplets, Network, BookOpen,
} from "lucide-react";
import { HeroVisual } from "@/components/hero-visual";
import { TrustGauge } from "@/components/trust-gauge";
import { DimensionBars } from "@/components/dimension-bars";
import { safeStats } from "@/lib/oracle";
import { FAUCET } from "@/lib/chain";
import type { DimensionKey } from "@/lib/types";

export const revalidate = 60;

const STEPS = [
  {
    Icon: Search,
    title: "Submit",
    body: "Paste any Amazon, Google Play or App Store product URL. The platform is detected from the link itself.",
  },
  {
    Icon: ScanLine,
    title: "Analyse",
    body: "Every validator loads the page in a real browser — independently, at the same moment — and reads the reviews for itself.",
  },
  {
    Icon: Gauge,
    title: "Score",
    body: "Five manipulation signals become five ordinals. Validators must agree on all of them, not just on the verdict.",
  },
  {
    Icon: ShieldCheck,
    title: "Trust",
    body: "The agreed numbers are written on chain with a content hash. Any contract can read them; anyone can recompute them.",
  },
];

const WHY = [
  {
    Icon: Lock,
    title: "Trustless",
    body: "No API key, no scraper you have to believe, no admin who can nudge a score. Every stored number was independently reproduced by validators who each fetched the page themselves — and the contract re-derives the score from the agreed evidence rather than storing what the leader claimed.",
  },
  {
    Icon: Layers,
    title: "Multi-platform",
    body: "Amazon, Google Play and the App Store, with the exact evidence each one publishes declared up front. Where a platform prints nothing to measure, that dimension carries no weight — it is never quietly scored as a zero.",
  },
  {
    Icon: Plug,
    title: "Composable",
    body: "One view call and your marketplace refuses to list a product whose reviews are bought. require_authentic reverts, get_trust_summary never does, and the worked example ships in the repo.",
  },
];

const EXAMPLE_AUTHENTIC: Record<DimensionKey, number | null> = {
  timing_pattern: 7,
  rating_distribution: 6,
  review_quality: 6,
  reviewer_credibility: 7,
  engagement_signals: 5,
};
const EXAMPLE_MANIPULATED: Record<DimensionKey, number | null> = {
  timing_pattern: 0,
  rating_distribution: 0,
  review_quality: 1,
  reviewer_credibility: 0,
  engagement_signals: 0,
};

export default async function Landing() {
  const stats = await safeStats();
  const checked = stats?.total_checked ?? 0;
  const flagged = (stats?.manipulated ?? 0) + (stats?.suspicious ?? 0);
  const pages = stats?.pages_tracked ?? 0;

  return (
    <>
      {/* ───────────────────────────────────────────────────────── hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(75rem_40rem_at_65%_-10%,rgba(79,70,229,0.10),transparent)]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
              <ShieldCheck size={13} strokeWidth={2.4} aria-hidden="true" />
              Consensus-bound review oracle
            </span>

            <h1 className="mt-5 text-4xl font-bold leading-[1.08] tracking-tight text-slate-900 sm:text-5xl lg:text-[3.4rem]">
              Are those reviews
              <br />
              <span className="text-indigo-600">real?</span>
            </h1>

            <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-600">
              Paste a product page. A network of validators each loads it in a
              real browser, reads the reviews independently, and has to{" "}
              <strong className="font-semibold text-slate-800">
                agree on every number
              </strong>{" "}
              before anything is written down. The result is a trust score no
              single party can move.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/check"
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-indigo-700 hover:shadow-md"
              >
                <Search size={17} strokeWidth={2.3} aria-hidden="true" />
                Check a product
              </Link>
              <Link
                href="/results"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50"
              >
                Browse results
                <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
              </Link>
            </div>

            <p className="mt-6 text-sm leading-relaxed text-slate-500">
              {checked > 0 ? (
                <>
                  <strong className="num font-semibold text-slate-700">
                    {pages}
                  </strong>{" "}
                  {pages === 1 ? "product page has" : "product pages have"} been
                  checked so far
                  {flagged > 0 ? (
                    <>
                      , and{" "}
                      <strong className="num font-semibold text-rose-600">
                        {flagged}
                      </strong>{" "}
                      {flagged === 1 ? "check" : "checks"} came back short of
                      authentic.
                    </>
                  ) : (
                    "."
                  )}
                </>
              ) : (
                <>
                  Free on GenLayer Studio Dev. No wallet needed to try it — the
                  site relays the transaction for you.
                </>
              )}
            </p>
          </div>

          <div className="lg:pl-6">
            <HeroVisual />
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────── how it works */}
      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            How it works
          </h2>
          <p className="mt-2 max-w-2xl text-slate-600">
            Four steps, and the interesting one is the second: the validators do
            not trust each other&apos;s reading of the page.
          </p>

          <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ Icon, title, body }, i) => (
              <li key={title} className="relative">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
                    <Icon size={19} strokeWidth={2.2} aria-hidden="true" />
                  </span>
                  <span className="num text-xs font-bold text-slate-300">
                    0{i + 1}
                  </span>
                </div>
                <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                  {body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ───────────────────────────────────────────────── the example */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          What the difference looks like
        </h2>
        <p className="mt-2 max-w-2xl text-slate-600">
          Two illustrative pages, scored on the same five dimensions. The shapes
          are what the rubric actually reacts to.
        </p>

        <div className="mt-9 grid gap-6 lg:grid-cols-2">
          <article className="card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  <ShieldCheck size={14} strokeWidth={2.3} aria-hidden="true" />
                  Authentic
                </div>
                <h3 className="mt-3 font-semibold text-slate-900">
                  A page that grew on its own
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">
                  Reviews spread over six years, a negative tail nobody
                  scrubbed, long varied bodies, verified purchases, and votes
                  from people who found them useful.
                </p>
              </div>
              <TrustGauge score={85} level="AUTHENTIC" size={110} stroke={9} label={false} />
            </div>
            <div className="mt-6 border-t border-slate-100 pt-5">
              <DimensionBars scores={EXAMPLE_AUTHENTIC} compact />
            </div>
          </article>

          <article className="card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700">
                  <ShieldX size={14} strokeWidth={2.3} aria-hidden="true" />
                  Manipulated
                </div>
                <h3 className="mt-3 font-semibold text-slate-900">
                  A page that was bought
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">
                  Ten five-star reviews landing the same week, 99% five-star
                  with no negative tail, one template repeated, handles like
                  <span className="num"> Mike2847</span>, and nobody voting.
                </p>
              </div>
              <TrustGauge score={10} level="MANIPULATED" size={110} stroke={9} label={false} />
            </div>
            <div className="mt-6 border-t border-slate-100 pt-5">
              <DimensionBars scores={EXAMPLE_MANIPULATED} compact />
            </div>
          </article>
        </div>

        <div className="mt-6 flex items-start gap-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <CircleHelp size={16} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
          <p>
            There is a fourth answer:{" "}
            <strong className="font-semibold text-slate-700">
              inconclusive
            </strong>
            . When a page does not render enough reviews to judge, ReviewGuard
            says so rather than guessing — and{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-[12px]">
              is_authentic
            </code>{" "}
            returns false, because &ldquo;we could not tell&rdquo; must never
            read as &ldquo;it is fine&rdquo;.
          </p>
        </div>
      </section>

      {/* ────────────────────────────────────────────── why reviewguard */}
      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Why ReviewGuard
          </h2>
          <div className="mt-9 grid gap-6 md:grid-cols-3">
            {WHY.map(({ Icon, title, body }) => (
              <article key={title} className="card card-hover p-6">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
                  <Icon size={21} strokeWidth={2.1} aria-hidden="true" />
                </span>
                <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  {body}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────── onboarding */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="card overflow-hidden">
          <div className="grid gap-8 p-8 lg:grid-cols-[1.1fr_1fr] lg:p-10">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                First time here?
              </h2>
              <p className="mt-2 text-slate-600">
                You do not need anything to try it. Checking is free and the
                site submits the transaction on your behalf. Connect a wallet
                only if you want your own address on the record.
              </p>

              <ul className="mt-6 space-y-4">
                <li className="flex gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600">
                    <Network size={16} strokeWidth={2.2} aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Network: GenLayer Studio Dev
                    </p>
                    <p className="num mt-0.5 text-xs text-slate-500">
                      chain 61997 · studio-dev.genlayer.com/api
                    </p>
                  </div>
                </li>
                <li className="flex gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600">
                    <Droplets size={16} strokeWidth={2.2} aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Want to submit it yourself?
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Grab testnet GEN from the{" "}
                      <a
                        href={FAUCET}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-indigo-600 hover:underline"
                      >
                        faucet
                      </a>
                      , then connect. The check itself costs nothing.
                    </p>
                  </div>
                </li>
                <li className="flex gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600">
                    <BookOpen size={16} strokeWidth={2.2} aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Want to know how it scores?
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      The{" "}
                      <Link href="/docs" className="font-medium text-indigo-600 hover:underline">
                        methodology page
                      </Link>{" "}
                      has the full rubric, including what each platform does and
                      does not publish.
                    </p>
                  </div>
                </li>
              </ul>
            </div>

            <div className="flex flex-col justify-center gap-3 rounded-2xl bg-slate-50 p-7">
              <div className="flex items-center gap-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star key={i} size={18} strokeWidth={0} fill="#F59E0B" aria-hidden="true" />
                ))}
              </div>
              <p className="text-lg font-semibold leading-snug text-slate-900">
                Five stars is easy to buy.
              </p>
              <p className="text-sm leading-relaxed text-slate-600">
                What is hard to buy is six years of steady dates, a real
                negative tail, reviews long enough to say something, and
                strangers voting them useful. That is what ReviewGuard measures.
              </p>
              <Link
                href="/check"
                className="mt-3 inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
              >
                <Search size={16} strokeWidth={2.3} aria-hidden="true" />
                Check a product now
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
