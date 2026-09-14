import Link from "next/link";
import { ShieldCheck, Search, LayoutGrid, GitCompare, BookOpen } from "lucide-react";
import { WalletBadge } from "./wallet-badge";

const NAV = [
  { href: "/check", label: "Check", Icon: Search },
  { href: "/results", label: "Results", Icon: LayoutGrid },
  { href: "/compare", label: "Compare", Icon: GitCompare },
  { href: "/docs", label: "Docs", Icon: BookOpen },
];

/**
 * The app header. `wallet` is false on the marketing layout: a landing page
 * that asks for a wallet before it has said what the product does is a landing
 * page people leave.
 */
export function SiteHeader({ wallet = true }: { wallet?: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-[#FAFAF9]/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 font-bold tracking-tight text-slate-900"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-white shadow-sm">
            <ShieldCheck size={18} strokeWidth={2.4} aria-hidden="true" />
          </span>
          <span className="text-[15px]">ReviewGuard</span>
        </Link>

        <nav className="ml-2 hidden items-center gap-1 md:flex">
          {NAV.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-white hover:text-slate-900"
            >
              <Icon size={16} strokeWidth={2} aria-hidden="true" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {wallet ? (
            <WalletBadge />
          ) : (
            <Link
              href="/check"
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700"
            >
              <Search size={15} strokeWidth={2.2} aria-hidden="true" />
              Check a product
            </Link>
          )}
        </div>
      </div>

      <nav className="flex items-center gap-1 overflow-x-auto border-t border-slate-200/70 px-4 pb-2 pt-1.5 md:hidden">
        {NAV.map(({ href, label, Icon }) => (
          <Link
            key={href}
            href={href}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-slate-600"
          >
            <Icon size={14} strokeWidth={2} aria-hidden="true" />
            {label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
