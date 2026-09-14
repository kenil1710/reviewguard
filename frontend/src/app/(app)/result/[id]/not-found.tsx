import Link from "next/link";
import { SearchX, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-20 sm:px-6">
      <div className="card p-8 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-slate-400">
          <SearchX size={22} strokeWidth={2} aria-hidden="true" />
        </span>
        <h1 className="mt-4 text-xl font-bold text-slate-900">
          That check id does not exist
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Check ids start at 1 and count up. Browse the results to find the one
          you meant.
        </p>
        <Link
          href="/results"
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
        >
          <ArrowLeft size={15} aria-hidden="true" /> Browse results
        </Link>
      </div>
    </div>
  );
}
