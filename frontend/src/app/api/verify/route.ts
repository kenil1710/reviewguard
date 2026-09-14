import { NextResponse } from "next/server";
import { verifyCheck } from "@/lib/oracle";

/** Recompute a stored check from its own stored evidence, on demand. */
export async function GET(req: Request) {
  const id = Number(new URL(req.url).searchParams.get("id") ?? 0);
  if (!Number.isFinite(id) || id <= 0) {
    return NextResponse.json({ verified: false, reason: "bad id" });
  }
  try {
    return NextResponse.json(await verifyCheck(id));
  } catch {
    return NextResponse.json({
      verified: false,
      reason: "the network did not answer just now; try again",
    });
  }
}
