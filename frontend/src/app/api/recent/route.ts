import { NextResponse } from "next/server";
import { getRecent } from "@/lib/oracle";

/** The most recent checks, for tooling that needs to work against whatever is
 *  actually on chain rather than against a hardcoded list. */
export async function GET(req: Request) {
  const n = Number(new URL(req.url).searchParams.get("count") ?? 20);
  try {
    const items = await getRecent(Number.isFinite(n) ? Math.min(100, Math.max(1, n)) : 20);
    return NextResponse.json({ count: items.length, items });
  } catch {
    return NextResponse.json({ count: 0, items: [] });
  }
}
