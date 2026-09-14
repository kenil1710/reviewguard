import { NextResponse } from "next/server";
import { ORACLE_ADDRESS, relayClient, retry, feePreset } from "@/lib/genlayer";
import { detectPlatform } from "@/lib/oracle";

export const maxDuration = 300;

/**
 * Submit a check on the visitor's behalf.
 *
 * A refusal from the contract comes back as `{status: "REJECTED", reason}` in
 * the RETURN VALUE, not as a revert — that is rule 2, and it is what lets this
 * route tell a visitor *why* their URL was turned down instead of showing them
 * a transaction error. The route mirrors that: it never throws at the client,
 * it answers `{ok: false, reason}`.
 */
export async function POST(req: Request) {
  let url = "";
  try {
    const body = (await req.json()) as { url?: string };
    url = String(body?.url ?? "").trim().slice(0, 300);
  } catch {
    return NextResponse.json({ ok: false, reason: "bad request body" });
  }
  if (!url) return NextResponse.json({ ok: false, reason: "no URL given" });

  // Detect first so an unsupported host costs nothing on chain and the visitor
  // gets the real reason rather than a generic failure.
  try {
    const det = await detectPlatform(url);
    if (!det?.supported) {
      return NextResponse.json({
        ok: false,
        reason:
          det?.reason ??
          "ReviewGuard cannot read that page. Supported: Amazon, Google Play, App Store.",
      });
    }
  } catch {
    /* detection is a courtesy; if it fails, let the contract decide */
  }

  const relay = relayClient();
  if (!relay) {
    return NextResponse.json({
      ok: false,
      reason:
        "This deployment has no relayer configured. Connect a wallet and submit the check yourself, or set RELAYER_PRIVATE_KEY.",
    });
  }

  try {
    // The distribution is not optional on studio-dev: without it the
    // transaction reverts with FeeValueMustBeNonZero(1) before the contract
    // ever runs.
    const fees = await feePreset(relay.wallet);
    const hash = await retry(() =>
      relay.wallet.writeContract({
        address: ORACLE_ADDRESS,
        functionName: "check_reviews",
        args: [url, ""],
        value: BigInt(0),
        fees: {
          distribution: fees.distribution,
          feeValue: fees.feeValue,
        },
      } as never),
    );

    const receipt = (await relay.wallet.waitForTransactionReceipt({
      hash: hash as `0x${string}`,
      status: "FINALIZED",
      retries: 200,
      interval: 3000,
    } as never)) as unknown as {
      consensusStatus?: string;
      result?: unknown;
      returnValue?: unknown;
    };

    const decoded =
      (receipt?.result as Record<string, unknown>) ??
      (receipt?.returnValue as Record<string, unknown>) ??
      null;

    if (decoded && decoded.status === "REJECTED") {
      return NextResponse.json({
        ok: false,
        reason: String(decoded.reason ?? "the check was refused"),
        refunded_wei: String(decoded.refunded_wei ?? "0"),
        tx: hash,
      });
    }
    if (decoded && decoded.status === "OK") {
      return NextResponse.json({
        ok: true,
        check_id: Number(decoded.check_id),
        url_key: String(decoded.url_key ?? ""),
        trust_level: String(decoded.trust_level ?? ""),
        overall: Number(decoded.overall ?? 0),
        tx: hash,
      });
    }

    // The receipt shape varies by SDK version, and a decided round is not the
    // same moment as a readable one. Rather than telling a visitor it failed
    // when it very likely worked, POLL for the record the write should have
    // created. A single read here reported a false failure on a check that had
    // in fact settled forty seconds later.
    const { getCheckByUrl, forget } = await import("@/lib/oracle");
    for (let i = 0; i < 24; i++) {
      forget("get_check_by_url", [url]);
      try {
        const rec = await getCheckByUrl(url);
        if (rec && "found" in rec && rec.found) {
          return NextResponse.json({
            ok: true,
            check_id: rec.check_id,
            url_key: rec.url_key,
            trust_level: rec.trust_level,
            overall: rec.overall,
            tx: hash,
          });
        }
      } catch {
        /* a bad minute on the RPC is not a failed check */
      }
      await new Promise((r) => setTimeout(r, 5000));
    }
    return NextResponse.json({
      ok: false,
      reason:
        "The validators are still settling this one. It usually appears under Browse results within a minute or two.",
      tx: hash,
    });
  } catch (e) {
    const msg = String((e as Error)?.message ?? e);
    return NextResponse.json({
      ok: false,
      reason: /rate limit|-32029/i.test(msg)
        ? "The network is rate limiting right now. Wait a moment and try again."
        : msg.slice(0, 300),
    });
  }
}
