import { NextResponse } from "next/server";
import { getCheckByUrl } from "@/lib/oracle";

/** The latest check for a URL, for the compare page. */
export async function GET(req: Request) {
  const url = new URL(req.url).searchParams.get("url") ?? "";
  if (!url.trim()) {
    return NextResponse.json({ found: false, reason: "no URL given" });
  }
  try {
    return NextResponse.json(await getCheckByUrl(url.trim().slice(0, 300)));
  } catch {
    return NextResponse.json({
      found: false,
      reason: "the network did not answer just now; try again",
    });
  }
}
