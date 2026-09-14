import type { Metadata } from "next";
import { ShieldCheck, Zap, Clock, Scale } from "lucide-react";
import { CheckForm } from "@/components/check-form";
import { safeConfig } from "@/lib/oracle";

export const metadata: Metadata = { title: "Check a product" };
export const revalidate = 120;

const EXAMPLES = [
  "https://www.amazon.com/dp/B07FZ8S74R",
  "https://play.google.com/store/apps/details?id=com.spotify.music",
  "https://apps.apple.com/us/app/instagram/id389801252",
];

export default async function CheckPage() {
  const cfg = await safeConfig();
  const fee = cfg?.fee_wei ?? "0";
  const rate = cfg?.rate_limit_seconds ?? 300;
  const cooldown = cfg?.url_cooldown_seconds ?? 900;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Check a product
        </h1>
        <p className="mt-2 text-slate-600">
          Paste a product page and the validators will read it for you. Nothing
          is stored unless they agree on every number.
        </p>
      </header>

      <CheckForm examples={EXAMPLES} />

      <div className="mt-6 card p-6">
        <h2 className="text-sm font-semibold text-slate-800">
          What this costs and what it limits
        </h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="flex gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
              <Zap size={15} strokeWidth={2.2} aria-hidden="true" />
            </span>
            <div>
              <dt className="text-sm font-semibold text-slate-800">
                Fee: {fee === "0" ? "free" : `${fee} wei`}
              </dt>
              <dd className="mt-0.5 text-xs leading-relaxed text-slate-500">
                Asking whether your money is about to be spent on a lie should
                not cost anything. The fee machinery exists and is fully tested
                — it is simply set to zero.
              </dd>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600">
              <Clock size={15} strokeWidth={2.2} aria-hidden="true" />
            </span>
            <div>
              <dt className="text-sm font-semibold text-slate-800">
                One check per wallet every {rate / 60} minutes
              </dt>
              <dd className="mt-0.5 text-xs leading-relaxed text-slate-500">
                And the same page can only be re-checked every{" "}
                {cooldown / 60} minutes. Both are fixed constants, not owner
                settings — an owner who could retune them could price a
                competitor out of the oracle.
              </dd>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-indigo-50 text-indigo-600">
              <ShieldCheck size={15} strokeWidth={2.2} aria-hidden="true" />
            </span>
            <div>
              <dt className="text-sm font-semibold text-slate-800">
                Refused checks refund
              </dt>
              <dd className="mt-0.5 text-xs leading-relaxed text-slate-500">
                A refusal credits your deposit back and tells you why, rather
                than reverting — a revert would roll back the record but keep
                the money.
              </dd>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600">
              <Scale size={15} strokeWidth={2.2} aria-hidden="true" />
            </span>
            <div>
              <dt className="text-sm font-semibold text-slate-800">
                Inconclusive is a real answer
              </dt>
              <dd className="mt-0.5 text-xs leading-relaxed text-slate-500">
                If the page does not render at least {cfg?.min_reviews ?? 3}{" "}
                reviews, you get &ldquo;inconclusive&rdquo; rather than a guess.
                That is the design, not a failure.
              </dd>
            </div>
          </div>
        </dl>
      </div>
    </div>
  );
}
