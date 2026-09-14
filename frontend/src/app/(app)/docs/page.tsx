import type { Metadata } from "next";
import Link from "next/link";
import {
  BookOpen, Droplets, Network, Wallet, Layers, Scale, Code2, HelpCircle,
  CheckCircle2, XCircle, AlertTriangle, ExternalLink,
} from "lucide-react";
import { safeConfig } from "@/lib/oracle";
import { FAUCET, CHAIN, GITHUB } from "@/lib/chain";
import { ORACLE_ADDRESS, addressUrl } from "@/lib/genlayer";
import { DIMENSIONS, DIMENSION_LABELS, DIMENSION_BLURBS } from "@/lib/types";
import { PLATFORM_LABEL } from "@/lib/format";
import type { Platform } from "@/lib/types";

export const metadata: Metadata = { title: "Methodology" };
export const revalidate = 300;

const TOC = [
  { id: "start", label: "Getting started", Icon: Droplets },
  { id: "method", label: "Methodology", Icon: Scale },
  { id: "platforms", label: "Supported platforms", Icon: Layers },
  { id: "rubric", label: "Scoring rubric", Icon: BookOpen },
  { id: "integrate", label: "Integration guide", Icon: Code2 },
  { id: "faq", label: "FAQ", Icon: HelpCircle },
];

export default async function DocsPage() {
  const cfg = await safeConfig();
  const platforms = (cfg?.platforms ?? {}) as Record<Platform, {
    hosts: string[];
    available_weight: number;
    credibility_basis: string;
    dimensions: Record<string, boolean>;
  }>;
  const unsupported = cfg?.unsupported ?? {};

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          How ReviewGuard works
        </h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          The full rubric, what each platform publishes, and how to read the
          oracle from your own contract.
        </p>
      </header>

      <nav className="card mb-10 p-4">
        <ul className="flex flex-wrap gap-2">
          {TOC.map(({ id, label, Icon }) => (
            <li key={id}>
              <a
                href={`#${id}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-indigo-300 hover:text-indigo-700"
              >
                <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* ───────────────────────────────────────── getting started */}
      <Section id="start" Icon={Droplets} title="Getting started">
        <p>
          You do not need a wallet to try ReviewGuard. Checking is free and the
          site relays the transaction for you. Connect one only if you want your
          own address recorded as the submitter.
        </p>
        <ol className="mt-5 space-y-4">
          <Step n={1} Icon={Network} title="The network">
            <p>
              ReviewGuard lives on <strong>{CHAIN.name}</strong>, chain id{" "}
              <span className="num">{CHAIN.id}</span>. If you connect a wallet on
              the wrong network, the badge in the header switches it for you —
              and adds it first if your wallet has never seen it.
            </p>
            <p className="num mt-1.5 text-xs text-slate-500">{CHAIN.rpc}</p>
          </Step>
          <Step n={2} Icon={Droplets} title="Testnet GEN">
            <p>
              Submitting your own transaction needs a little testnet GEN for the
              fee deposit. Take some from the{" "}
              <a href={FAUCET} target="_blank" rel="noreferrer" className="font-medium text-indigo-600 hover:underline">
                faucet
              </a>
              . The check itself costs{" "}
              <strong>{cfg?.fee_wei === "0" ? "nothing" : `${cfg?.fee_wei} wei`}</strong>.
            </p>
          </Step>
          <Step n={3} Icon={Wallet} title="Submit a check">
            <p>
              Paste a product URL on the{" "}
              <Link href="/check" className="font-medium text-indigo-600 hover:underline">
                check page
              </Link>
              . A round takes 30–90 seconds, because every validator loads the
              page in a real browser before voting.
            </p>
          </Step>
        </ol>
      </Section>

      {/* ───────────────────────────────────────── methodology */}
      <Section id="method" Icon={Scale} title="Methodology">
        <p>
          A leader validator loads the product page, reduces it to a vector of
          twenty integers, and proposes a score. Every other validator then{" "}
          <strong>loads the same page itself</strong> and recomputes the whole
          vector. If any one of the twenty numbers differs, the round does not
          settle and nothing is written.
        </p>
        <p className="mt-4">
          That is the part worth dwelling on: consensus binds{" "}
          <strong>every stored value</strong>, not just the verdict. A field the
          validators did not compare would be a field the leader could invent,
          and an invented review count on a review oracle is the whole attack.
          After agreement the contract runs the scoring rubric{" "}
          <em>again</em> on the agreed vector rather than storing the numbers
          the leader sent.
        </p>

        <h3 className="mt-8 text-base font-semibold text-slate-900">
          Why quantisation, not tolerance
        </h3>
        <p className="mt-2">
          Two validators load the page seconds apart, and a live review count
          can tick between them. Rather than allowing a fuzzy comparison — which
          would mean two different accepted answers for one question — every
          figure is rounded <em>before</em> it is compared: counts to three
          significant figures, percentages to the nearest{" "}
          <span className="num">{cfg?.quantisation_step ?? 5}</span>, and each
          dimension to one of eight ordinals. The tolerance lives in the
          rounding and nowhere else.
        </p>

        <h3 className="mt-8 text-base font-semibold text-slate-900">
          Why some checks say &ldquo;inconclusive&rdquo;
        </h3>
        <p className="mt-2">
          Platforms differ in what they publish, and pages sometimes render
          without their reviews at all. When a page yields fewer than{" "}
          <span className="num">{cfg?.min_reviews ?? 3}</span> individual
          reviews, or when less than{" "}
          <span className="num">{cfg?.min_available_weight ?? 60}</span> of the
          100 rubric points can be measured, ReviewGuard returns{" "}
          <strong>INCONCLUSIVE</strong>.
        </p>
        <Callout tone="info">
          Inconclusive is <strong>not</strong> a low score, and it is{" "}
          <strong>not</strong> a pass. <code>is_authentic</code> returns false
          for it and <code>require_authentic</code> reverts on it, because
          &ldquo;we could not read the page&rdquo; must never be mistaken for
          &ldquo;we checked and the reviews are real&rdquo;. It is also excluded
          from the manipulation rate, so the headline number cannot improve by
          the oracle failing more often.
        </Callout>
      </Section>

      {/* ───────────────────────────────────────── platforms */}
      <Section id="platforms" Icon={Layers} title="Supported platforms">
        <p>
          Fourteen review sites were tried with a throwaway probe deployed to
          this same network. Three of them render their reviews to a validator.
          Eleven do not, and they are not offered — a platform that cannot be
          read honestly is worse than one that is absent, because a blocked page
          looks like an empty one.
        </p>

        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="pb-2 font-semibold">Platform</th>
                <th className="pb-2 font-semibold">URL shape</th>
                <th className="pb-2 font-semibold">Measurable</th>
                <th className="pb-2 font-semibold">Credibility basis</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(Object.keys(platforms) as Platform[]).map((p) => (
                <tr key={p}>
                  <td className="py-3">
                    <span className="inline-flex items-center gap-1.5 font-semibold text-slate-800">
                      <CheckCircle2 size={14} className="text-emerald-600" aria-hidden="true" />
                      {PLATFORM_LABEL[p]}
                    </span>
                  </td>
                  <td className="num py-3 text-xs text-slate-500">
                    {platforms[p].hosts[0]}
                  </td>
                  <td className="num py-3 font-semibold text-slate-700">
                    {platforms[p].available_weight}/100
                  </td>
                  <td className="py-3 text-xs text-slate-600">
                    {platforms[p].credibility_basis}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 className="mt-8 text-base font-semibold text-slate-900">
          What each platform publishes
        </h3>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="pb-2 font-semibold">Dimension</th>
                {(Object.keys(platforms) as Platform[]).map((p) => (
                  <th key={p} className="pb-2 text-center font-semibold">
                    {PLATFORM_LABEL[p]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {DIMENSIONS.map((d) => (
                <tr key={d}>
                  <td className="py-2.5 text-slate-700">
                    {DIMENSION_LABELS[d]}
                    <span className="num ml-1.5 text-xs text-slate-400">
                      {cfg?.weights?.[d]}%
                    </span>
                  </td>
                  {(Object.keys(platforms) as Platform[]).map((p) => (
                    <td key={p} className="py-2.5 text-center">
                      {platforms[p].dimensions?.[d] ? (
                        <CheckCircle2 size={15} className="mx-auto text-emerald-600" aria-hidden="true" />
                      ) : (
                        <span className="text-xs text-slate-300">not published</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 className="mt-8 text-base font-semibold text-slate-900">
          What was tried and does not work
        </h3>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {Object.entries(unsupported).map(([name, why]) => (
            <li
              key={name}
              className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs"
            >
              <XCircle size={14} className="mt-0.5 shrink-0 text-rose-400" aria-hidden="true" />
              <span>
                <strong className="text-slate-700">
                  {name.charAt(0) + name.slice(1).toLowerCase().split("_").join(" ")}
                </strong>{" "}
                <span className="text-slate-500">— {String(why)}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      {/* ───────────────────────────────────────── rubric */}
      <Section id="rubric" Icon={BookOpen} title="The scoring rubric">
        <p>
          Five dimensions, weighted to 100. Each is an ordinal from 0 to 7 where{" "}
          <strong>0 is always the worst outcome</strong>, so a reader never has
          to remember which way a bar points.
        </p>

        <div className="mt-6 space-y-6">
          {DIMENSIONS.map((d) => (
            <div key={d} className="card p-5">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-semibold text-slate-900">
                  {DIMENSION_LABELS[d]}
                </h3>
                <span className="num text-sm font-bold text-indigo-600">
                  {cfg?.weights?.[d]}%
                </span>
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                {DIMENSION_BLURBS[d]}
              </p>
              {cfg?.buckets?.[d] && (
                <ol className="mt-3 flex flex-wrap gap-1.5">
                  {cfg.buckets[d].map((label, i) => (
                    <li
                      key={label}
                      className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600"
                    >
                      <span className="num font-semibold text-slate-400">{i}</span>{" "}
                      {label}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>

        <h3 className="mt-8 text-base font-semibold text-slate-900">
          From ordinals to a trust level
        </h3>
        <p className="mt-2">
          The ordinals are averaged by weight over the dimensions the platform
          actually publishes, scaled to 0–100 and rounded to the nearest{" "}
          <span className="num">{cfg?.quantisation_step ?? 5}</span>.
        </p>
        <ul className="mt-4 space-y-2">
          <Band tone="emerald" range={`${cfg?.thresholds?.authentic_min ?? 70}–100`} name="Authentic" body="The evidence looks like a page that grew on its own." />
          <Band tone="amber" range={`${cfg?.thresholds?.suspicious_min ?? 40}–${(cfg?.thresholds?.authentic_min ?? 70) - 1}`} name="Suspicious" body="Some signals are off. Worth reading the breakdown before trusting the stars." />
          <Band tone="rose" range={`0–${(cfg?.thresholds?.suspicious_min ?? 40) - 1}`} name="Manipulated" body="Multiple independent signals point the same way." />
          <Band tone="slate" range="—" name="Inconclusive" body="Too little of the page could be read to judge it. Not a score." />
        </ul>
      </Section>

      {/* ───────────────────────────────────────── integrate */}
      <Section id="integrate" Icon={Code2} title="Integration guide">
        <p>
          ReviewGuard is a read surface for other contracts. The whole
          composability story is two calls, and the choice between them matters.
        </p>

        <h3 className="mt-6 text-base font-semibold text-slate-900">
          The safe one: <code>get_trust_summary</code>
        </h3>
        <p className="mt-2">
          It <strong>never raises</strong>. Use it on any path that takes money,
          because a revert rolls back your storage but not the caller&apos;s
          deposit — leaving funds in your contract with no record of whose they
          were.
        </p>
        <Pre>{`@gl.contract.interface
class IReviewGuard:
    class View:
        def get_trust_summary(self, url: str) -> typing.Any: ...
    class Write:
        pass  # a consumer must never be able to spend the oracle's rate limit

summary = IReviewGuard(ORACLE).view().get_trust_summary(url)
if not summary.get("found"):
    return self._refuse("never checked")           # not "score 0"
if summary["trust_level"] != "AUTHENTIC":
    return self._refuse(summary["trust_level"])    # INCONCLUSIVE included
if now - summary["checked_at"] > MAX_AGE:
    return self._refuse("that check is stale")     # your policy, not the oracle's`}</Pre>

        <h3 className="mt-8 text-base font-semibold text-slate-900">
          The strict one: <code>require_authentic</code>
        </h3>
        <p className="mt-2">
          Reverts unless the latest check says AUTHENTIC — including on
          SUSPICIOUS, on INCONCLUSIVE, and on never-checked. Use it on a
          non-payable path where a revert costs nobody anything.{" "}
          <code>require_not_manipulated</code> is the looser variant, and still
          reverts on inconclusive.
        </p>

        <Callout tone="warn">
          Three things a consumer should never do: treat{" "}
          <code>found: false</code> as a score of zero; treat INCONCLUSIVE as a
          pass because its score happens to be 0; or apply the oracle&apos;s
          freshness opinion instead of its own. The worked example in{" "}
          <code>contracts/MarketplaceConsumer.py</code> does all three the right
          way and logs every refusal so they can be audited.
        </Callout>

        <p className="mt-6">
          <a
            href={GITHUB}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 font-semibold text-indigo-600 hover:underline"
          >
            Full source and tests <ExternalLink size={14} aria-hidden="true" />
          </a>
          {" · "}
          <a
            href={addressUrl(ORACLE_ADDRESS)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 font-semibold text-indigo-600 hover:underline"
          >
            Contract on the explorer <ExternalLink size={14} aria-hidden="true" />
          </a>
        </p>
      </Section>

      {/* ───────────────────────────────────────── faq */}
      <Section id="faq" Icon={HelpCircle} title="FAQ">
        <dl className="space-y-6">
          <Faq q="Does a low score mean the seller bought reviews?">
            No. ReviewGuard reports what a public review page shows — the shape
            of the dates, the histogram, the writing, the reviewer identities
            and the engagement. Those patterns correlate with manipulation; they
            do not prove it, and a legitimate seller can land in the middle band
            for innocent reasons. It is evidence about a page, not an accusation
            against a person.
          </Faq>
          <Faq q="Why not Trustpilot or Yelp?">
            Both were tried. Trustpilot answers a validator with a 403 and an AWS
            WAF interstitial; Yelp answers with a 403 and a captcha. Neither
            renders in a headless browser either. A platform we cannot read is
            one we will not pretend to score.
          </Faq>
          <Faq q="Why did my Amazon check come back inconclusive?">
            Amazon loads its individual reviews after the page itself, below the
            fold, and they do not always arrive inside the validator&apos;s
            window. When they do not, ReviewGuard has the rating histogram but
            no individual reviews — which is not enough to judge timing, writing
            or reviewer credibility. It says inconclusive rather than scoring
            what it has. Re-checking later often gets a full read.
          </Faq>
          <Faq q="Can the owner change a score?">
            No. The owner can set the fee, pause new checks, transfer ownership
            and withdraw earned fees. That is the entire surface, and a test
            enumerates every public write to keep it that way. Written records
            are never mutated — a re-check appends a new one. Pause does not
            touch reads or refunds, and clearing a stuck round is permissionless
            so an owner cannot censor a page by refusing to unstick it.
          </Faq>
          <Faq q="What if the page changes after the check?">
            The old record stands and a new check appends alongside it. Each
            record carries its own content hash and timestamp, so an integrator
            can see exactly what was known when they acted — and apply their own
            staleness rule.
          </Faq>
          <Faq q="How do I know the score was not made up?">
            Press <strong>Recompute from evidence</strong> on any result. The
            contract reads the stored vector back, runs the rubric on it again,
            and compares every derived field to what was written. You do not
            have to trust the number; you can make the chain redo it.
          </Faq>
        </dl>
      </Section>
    </div>
  );
}

/* ── small presentational helpers ─────────────────────────────────────── */

function Section({
  id, Icon, title, children,
}: {
  id: string;
  Icon: typeof BookOpen;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mb-14 scroll-mt-24">
      <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-900">
        <Icon size={22} className="text-indigo-600" strokeWidth={2.2} aria-hidden="true" />
        {title}
      </h2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed text-slate-600">
        {children}
      </div>
    </section>
  );
}

function Step({
  n, Icon, title, children,
}: {
  n: number;
  Icon: typeof Network;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-4">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
        <Icon size={17} strokeWidth={2.2} aria-hidden="true" />
      </span>
      <div>
        <h3 className="font-semibold text-slate-900">
          <span className="num mr-1.5 text-xs text-slate-400">{n}</span>
          {title}
        </h3>
        <div className="mt-1 text-sm text-slate-600">{children}</div>
      </div>
    </li>
  );
}

function Callout({
  tone, children,
}: {
  tone: "info" | "warn";
  children: React.ReactNode;
}) {
  const cls =
    tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : "border-indigo-200 bg-indigo-50 text-indigo-900";
  const Icon = tone === "warn" ? AlertTriangle : HelpCircle;
  return (
    <div className={`mt-5 flex items-start gap-2.5 rounded-xl border p-4 text-sm leading-relaxed ${cls}`}>
      <Icon size={16} className="mt-0.5 shrink-0" strokeWidth={2.2} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

function Pre({ children }: { children: string }) {
  return (
    <pre className="num mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-slate-900 p-4 text-[12px] leading-relaxed text-slate-100">
      <code>{children}</code>
    </pre>
  );
}

function Band({
  tone, range, name, body,
}: {
  tone: "emerald" | "amber" | "rose" | "slate";
  range: string;
  name: string;
  body: string;
}) {
  const dot = {
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
    slate: "bg-slate-400",
  }[tone];
  return (
    <li className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} />
      <div>
        <p className="text-sm font-semibold text-slate-800">
          <span className="num mr-2 text-slate-400">{range}</span>
          {name}
        </p>
        <p className="mt-0.5 text-sm text-slate-600">{body}</p>
      </div>
    </li>
  );
}

function Faq({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="font-semibold text-slate-900">{q}</dt>
      <dd className="mt-1.5 text-sm leading-relaxed text-slate-600">
        {children}
      </dd>
    </div>
  );
}
