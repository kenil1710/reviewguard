import Link from "next/link";
import { ShieldCheck, Github, ExternalLink } from "lucide-react";
import { GITHUB, CHAIN } from "@/lib/chain";
import { ORACLE_ADDRESS, addressUrl } from "@/lib/genlayer";

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-2 font-bold text-slate-900">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-indigo-600 text-white">
                <ShieldCheck size={16} strokeWidth={2.4} aria-hidden="true" />
              </span>
              ReviewGuard
            </div>
            <p className="mt-3 text-sm leading-relaxed text-slate-500">
              A fake-review detector that any contract can read. Validators
              fetch the page themselves and agree on the numbers before anything
              is written down.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Product
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link href="/check" className="text-slate-600 hover:text-indigo-600">Check a product</Link></li>
              <li><Link href="/results" className="text-slate-600 hover:text-indigo-600">Browse results</Link></li>
              <li><Link href="/compare" className="text-slate-600 hover:text-indigo-600">Compare two</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Learn
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link href="/docs" className="text-slate-600 hover:text-indigo-600">Methodology</Link></li>
              <li><Link href="/docs#platforms" className="text-slate-600 hover:text-indigo-600">Supported platforms</Link></li>
              <li><Link href="/docs#integrate" className="text-slate-600 hover:text-indigo-600">Integration guide</Link></li>
              <li><Link href="/docs#faq" className="text-slate-600 hover:text-indigo-600">FAQ</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              On chain
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <a
                  href={addressUrl(ORACLE_ADDRESS)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-slate-600 hover:text-indigo-600"
                >
                  Contract <ExternalLink size={12} aria-hidden="true" />
                </a>
              </li>
              <li>
                <a
                  href={GITHUB}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-slate-600 hover:text-indigo-600"
                >
                  <Github size={13} aria-hidden="true" /> Source
                </a>
              </li>
              <li className="text-slate-500">{CHAIN.name}</li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-2 border-t border-slate-100 pt-6 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>
            ReviewGuard reports what a public review page shows. It is evidence
            about a page, not an accusation against a seller.
          </p>
          <p className="num">{ORACLE_ADDRESS}</p>
        </div>
      </div>
    </footer>
  );
}
