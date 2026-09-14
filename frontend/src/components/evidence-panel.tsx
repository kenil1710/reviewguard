import {
  CalendarDays, BarChart3, FileText, UserCheck, ThumbsUp, Images,
  MessageSquareReply, Hash, Info, FileWarning, ScrollText,
} from "lucide-react";
import type { Evidence } from "@/lib/types";
import { compact, exact, stars, spanLabel } from "@/lib/format";
import { NotPublished } from "./badges";

/**
 * What the validators actually found on the page.
 *
 * Every figure here is on the consensus axis — each one was independently
 * reproduced before it was stored. A figure the platform does not publish says
 * so in words; it is never rendered as a zero, because "0% verified" and "this
 * platform does not say" are different claims about a seller.
 */
export function EvidencePanel({ evidence: e }: { evidence: Evidence }) {
  const hist = e.rating_histogram;
  const hasHist = hist?.["5"] !== null && hist?.["5"] !== undefined;

  return (
    <div className="card p-6">
      <div className="flex items-center gap-2">
        <Hash size={16} className="text-slate-400" aria-hidden="true" />
        <h2 className="font-semibold text-slate-900">
          What the validators found
        </h2>
      </div>
      <p className="mt-1.5 text-sm text-slate-600">
        Every number below was reproduced independently by each validator before
        it was written. They are the inputs to the score, not a summary of it.
      </p>

      {/* ── the page itself.
          A page that was served without its review list is the difference
          between "nobody has reviewed this" and "we could not see the
          reviews", and those call for opposite responses. */}
      {!e.reviews_section && (
        <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <FileWarning
            size={16}
            className="mt-0.5 shrink-0 text-amber-600"
            strokeWidth={2.2}
            aria-hidden="true"
          />
          <div className="text-sm leading-relaxed text-amber-900">
            <strong className="font-semibold">
              The page stopped before its review list.
            </strong>{" "}
            It rendered{" "}
            <span className="num font-semibold">{exact(e.page_chars)}</span>{" "}
            characters and the individual reviews were not among them, so there
            was nothing to read. That is why this check is inconclusive rather
            than low — the product may be perfectly fine.
          </div>
        </div>
      )}

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        {/* ── reviews read */}
        <Section Icon={FileText} title="Reviews read">
          <Row label="Individual reviews parsed" value={<Num v={e.reviews_parsed} />} />
          <Row label="Median review length" value={<Num v={e.median_chars} suffix=" chars" />} />
          <Row label="Under 120 characters" value={<Num v={e.short_pct} suffix="%" />} />
          <Row label="Sharing an opening line" value={<Num v={e.dup_open_pct} suffix="%" />} />
          <Row label="Vocabulary variety" value={<Num v={e.lexical_pct} suffix="%" />} />
          <Row
            label="Page rendered"
            value={
              <span className="num inline-flex items-center gap-1 font-semibold text-slate-800">
                <ScrollText size={12} className="text-slate-400" aria-hidden="true" />
                {exact(e.page_chars)} chars
              </span>
            }
          />
        </Section>

        {/* ── timing */}
        <Section Icon={CalendarDays} title="When they were written">
          <Row label="Reviews carrying a date" value={<Num v={e.dated_reviews} />} />
          <Row label="Distinct days" value={<Num v={e.distinct_days} />} />
          <Row label="Most on any one day" value={<Num v={e.max_same_day} />} />
          <Row
            label="Spread across"
            value={
              <span className="num font-semibold text-slate-800">
                {spanLabel(e.span_days)}
              </span>
            }
          />
        </Section>

        {/* ── ratings */}
        <Section Icon={BarChart3} title="Ratings on the listing">
          <Row
            label="Listed average"
            value={
              e.avg_rating_x10 === null ? (
                <NotPublished />
              ) : (
                <span className="num font-semibold text-slate-800">
                  {stars(e.avg_rating_x10)} / 5
                </span>
              )
            }
          />
          <Row
            label="Total ratings"
            value={
              e.total_ratings === null ? (
                <NotPublished />
              ) : (
                <span className="num font-semibold text-slate-800">
                  {compact(e.total_ratings)}
                  <span className="ml-1 font-normal text-slate-400">
                    ({exact(e.total_ratings)})
                  </span>
                </span>
              )
            }
          />
          {hasHist ? (
            <div className="mt-3 space-y-1.5">
              {(["5", "4", "3", "2", "1"] as const).map((k) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="num w-8 shrink-0 text-right text-xs text-slate-500">
                    {k}★
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-amber-400"
                      style={{ width: `${hist[k] ?? 0}%` }}
                    />
                  </div>
                  <span className="num w-9 shrink-0 text-right text-xs font-medium text-slate-600">
                    {hist[k]}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 flex items-start gap-1.5 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
              <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
              This platform draws its star histogram rather than writing it, so
              there is nothing on the page to read. The rating-distribution
              dimension carries no weight here.
            </p>
          )}
        </Section>

        {/* ── who wrote them */}
        <Section Icon={UserCheck} title="Who wrote them">
          <Row
            label="Verified purchases"
            value={
              e.verified_pct === null ? (
                <NotPublished what="not published by this platform" />
              ) : (
                <Num v={e.verified_pct} suffix="%" />
              )
            }
          />
          <Row label="Distinct reviewer names" value={<Num v={e.distinct_names_pct} suffix="%" />} />
          <Row
            label="Generated-looking handles"
            value={<Num v={e.weak_handle_pct} suffix="%" tone={e.weak_handle_pct >= 40 ? "bad" : undefined} />}
          />
        </Section>

        {/* ── engagement */}
        <Section Icon={ThumbsUp} title="How people reacted">
          <Row
            label="Reviews with a helpful count"
            value={e.helpful_pct === null ? <NotPublished /> : <Num v={e.helpful_pct} suffix="%" />}
          />
          <Row
            label="Total helpful votes"
            value={
              e.helpful_total === null ? (
                <NotPublished />
              ) : (
                <span className="num font-semibold text-slate-800">
                  {compact(e.helpful_total)}
                </span>
              )
            }
          />
          <Row
            label="Customer photos"
            value={
              <Flag on={e.has_photos} Icon={Images} yes="present" no="none found" />
            }
          />
          <Row
            label="Seller response"
            value={
              <Flag
                on={e.has_response}
                Icon={MessageSquareReply}
                yes="present"
                no="none found"
              />
            }
          />
        </Section>
      </div>
    </div>
  );
}

function Section({
  Icon,
  title,
  children,
}: {
  Icon: typeof FileText;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
        <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
        {title}
      </h3>
      <dl className="mt-2.5 space-y-1.5">{children}</dl>
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <dt className="text-slate-600">{label}</dt>
      <dd className="shrink-0 text-right">{value}</dd>
    </div>
  );
}

function Num({
  v,
  suffix = "",
  tone,
}: {
  v: number;
  suffix?: string;
  tone?: "bad";
}) {
  return (
    <span
      className={`num font-semibold ${tone === "bad" ? "text-rose-600" : "text-slate-800"}`}
    >
      {exact(v)}
      {suffix}
    </span>
  );
}

function Flag({
  on,
  Icon,
  yes,
  no,
}: {
  on: boolean;
  Icon: typeof Images;
  yes: string;
  no: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-sm font-medium ${
        on ? "text-emerald-700" : "text-slate-400"
      }`}
    >
      <Icon size={13} strokeWidth={2.1} aria-hidden="true" />
      {on ? yes : no}
    </span>
  );
}
