import type { Metadata } from "next";
import { GitCompare } from "lucide-react";
import { CompareView } from "@/components/compare-view";

export const metadata: Metadata = { title: "Compare" };

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string }>;
}) {
  const { a } = await searchParams;
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <header className="mb-8">
        <div className="flex items-center gap-2">
          <GitCompare size={22} className="text-indigo-600" strokeWidth={2.2} aria-hidden="true" />
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Compare two products
          </h1>
        </div>
        <p className="mt-2 max-w-2xl text-slate-600">
          Put two checked pages side by side, dimension by dimension. Signals a
          platform does not publish are left out of the comparison rather than
          counted as a loss.
        </p>
      </header>
      <CompareView initialA={a ?? ""} />
    </div>
  );
}
