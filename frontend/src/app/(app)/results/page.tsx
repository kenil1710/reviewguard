import type { Metadata } from "next";
import Link from "next/link";
import { LayoutGrid, ShieldCheck, ShieldAlert, ShieldX, HelpCircle } from "lucide-react";
import { ResultCards } from "@/components/result-cards";
import { safeRecent, safeStats } from "@/lib/oracle";

export const metadata: Metadata = { title: "Results" };
export const revalidate = 30;

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const [items, stats] = await Promise.all([safeRecent(100), safeStats()]);

  const tiles = [
    {
      Icon: LayoutGrid,
      label: "Pages checked",
      value: stats?.pages_tracked ?? 0,
      tone: "text-slate-700",
    },
    {
      Icon: ShieldCheck,
      label: "Authentic",
      value: stats?.authentic ?? 0,
      tone: "text-emerald-600",
    },
    {
      Icon: ShieldAlert,
      label: "Suspicious",
      value: stats?.suspicious ?? 0,
      tone: "text-amber-600",
    },
    {
      Icon: ShieldX,
      label: "Manipulated",
      value: stats?.manipulated ?? 0,
      tone: "text-rose-600",
    },
    {
      Icon: HelpCircle,
      label: "Inconclusive",
      value: stats?.inconclusive ?? 0,
      tone: "text-slate-500",
    },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Checked products
        </h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Every check ever written to the contract, newest first. Each one was
          independently reproduced by validators before it was stored.
        </p>
      </header>

      <ul className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {tiles.map(({ Icon, label, value, tone }) => (
          <li key={label} className="card p-4">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
              {label}
            </div>
            <p className={`num mt-1.5 text-2xl font-bold ${tone}`}>{value}</p>
          </li>
        ))}
      </ul>

      {stats && stats.conclusive_checks > 0 && (
        <p className="mb-8 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          Of{" "}
          <strong className="num font-semibold text-slate-800">
            {stats.conclusive_checks}
          </strong>{" "}
          checks that could be called,{" "}
          <strong className="num font-semibold text-rose-600">
            {stats.manipulation_rate_pct}%
          </strong>{" "}
          showed manipulation. Inconclusive checks are excluded from that
          denominator on purpose — counting a page nobody could read as
          &ldquo;clean&rdquo; would make the number improve every time the
          oracle failed.
        </p>
      )}

      <ResultCards items={items} initialQuery={q ?? ""} />

      <p className="mt-10 text-center text-sm text-slate-500">
        Not here yet?{" "}
        <Link href="/check" className="font-semibold text-indigo-600 hover:underline">
          Check a product
        </Link>
        .
      </p>
    </div>
  );
}
