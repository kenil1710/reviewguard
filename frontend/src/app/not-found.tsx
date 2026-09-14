import Link from "next/link";
import { ShieldQuestion, Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-indigo-50 text-indigo-600">
          <ShieldQuestion size={26} strokeWidth={2.1} aria-hidden="true" />
        </span>
        <h1 className="mt-5 text-2xl font-bold text-slate-900">
          There is nothing here
        </h1>
        <p className="mt-2 text-slate-600">
          The page you asked for does not exist.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
        >
          <Home size={16} aria-hidden="true" /> Back to ReviewGuard
        </Link>
      </div>
    </div>
  );
}
