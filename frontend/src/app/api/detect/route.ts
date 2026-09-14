import { NextResponse } from "next/server";
import { detectPlatform } from "@/lib/oracle";

/** Platform detection for the check form, proxied through the server so the
 *  browser never spends the visitor's share of the RPC rate limit. */
export async function GET(req: Request) {
  const url = new URL(req.url).searchParams.get("url") ?? "";
  if (!url.trim()) {
    return NextResponse.json({
      supported: false,
      platform: "",
      url_key: "",
      reason: "no URL given",
    });
  }
  try {
    const out = await detectPlatform(url.trim().slice(0, 300));
    return NextResponse.json(out);
  } catch {
    return NextResponse.json({
      supported: false,
      platform: "",
      url_key: "",
      reason: "the network did not answer just now; try again",
    });
  }
}
