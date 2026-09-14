"use client";

import { useEffect, useState, useCallback } from "react";
import { Wallet, AlertTriangle, Check, Loader2 } from "lucide-react";
import { CHAIN, CHAIN_HEX, CHAIN_PARAMS } from "@/lib/chain";

type Eth = {
  request: (a: { method: string; params?: unknown[] }) => Promise<unknown>;
  on?: (e: string, cb: (...a: unknown[]) => void) => void;
  removeListener?: (e: string, cb: (...a: unknown[]) => void) => void;
};

declare global {
  interface Window {
    ethereum?: Eth;
  }
}

/**
 * Wallet state, on app pages only.
 *
 * Connecting is optional throughout: checks are free and the site relays them,
 * so this is a convenience for a visitor who wants their own address on the
 * record, not a gate in front of the product.
 */
export function WalletBadge() {
  const [address, setAddress] = useState<string | null>(null);
  const [chainId, setChainId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hasWallet, setHasWallet] = useState(false);

  useEffect(() => {
    const eth = window.ethereum;

    let alive = true;
    // `hasWallet` is set inside the async block with everything else rather
    // than synchronously at the top of the effect: a synchronous setState here
    // is a cascading render, and the first paint should be the
    // no-wallet-needed state anyway — that is the honest default, since a
    // check is free and the site relays it.
    (async () => {
      if (!alive) return;
      setHasWallet(Boolean(eth));
      if (!eth) return;
      try {
        const accts = (await eth.request({ method: "eth_accounts" })) as string[];
        const cid = (await eth.request({ method: "eth_chainId" })) as string;
        if (!alive) return;
        setAddress(accts?.[0] ?? null);
        setChainId(cid ?? null);
      } catch {
        /* a wallet that refuses to answer is the same as no wallet here */
      }
    })();

    if (!eth) return () => { alive = false; };

    const onAccounts = (...a: unknown[]) =>
      setAddress(((a[0] as string[]) ?? [])[0] ?? null);
    const onChain = (...a: unknown[]) => setChainId((a[0] as string) ?? null);
    eth.on?.("accountsChanged", onAccounts);
    eth.on?.("chainChanged", onChain);
    return () => {
      alive = false;
      eth.removeListener?.("accountsChanged", onAccounts);
      eth.removeListener?.("chainChanged", onChain);
    };
  }, []);

  const connect = useCallback(async () => {
    const eth = window.ethereum;
    if (!eth) {
      window.open("https://metamask.io/download/", "_blank", "noreferrer");
      return;
    }
    setBusy(true);
    try {
      const accts = (await eth.request({
        method: "eth_requestAccounts",
      })) as string[];
      setAddress(accts?.[0] ?? null);
      const cid = (await eth.request({ method: "eth_chainId" })) as string;
      setChainId(cid);
    } catch {
      /* the user declined; nothing to report */
    } finally {
      setBusy(false);
    }
  }, []);

  /** Switch, and ADD the network if the wallet has never seen it. Without the
   *  add fallback a first-time visitor's switch attempt dead-ends on error
   *  4902 with no way forward. */
  const switchChain = useCallback(async () => {
    const eth = window.ethereum;
    if (!eth) return;
    setBusy(true);
    try {
      await eth.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: CHAIN_HEX }],
      });
    } catch (e) {
      const code = (e as { code?: number })?.code;
      if (code === 4902 || code === -32603) {
        try {
          await eth.request({
            method: "wallet_addEthereumChain",
            params: [CHAIN_PARAMS],
          });
        } catch {
          /* declined */
        }
      }
    } finally {
      try {
        const cid = (await eth.request({ method: "eth_chainId" })) as string;
        setChainId(cid);
      } catch {
        /* ignore */
      }
      setBusy(false);
    }
  }, []);

  const wrongChain = Boolean(address) && chainId !== null && chainId !== CHAIN_HEX;

  if (!hasWallet) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-500">
        <Check size={14} className="text-emerald-600" strokeWidth={2.4} aria-hidden="true" />
        Studio Dev
        {/* The reassurance is the point of this badge, but it does not fit
            beside a logo at 390px and wrapping it to two lines reads as a
            layout bug. It appears from `sm` up. */}
        <span className="hidden sm:inline">· no wallet needed</span>
      </span>
    );
  }

  if (wrongChain) {
    return (
      <button
        onClick={switchChain}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 transition-colors hover:bg-amber-100 disabled:opacity-60"
      >
        {busy ? (
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        ) : (
          <AlertTriangle size={14} strokeWidth={2.4} aria-hidden="true" />
        )}
        Switch to {CHAIN.name}
      </button>
    );
  }

  if (address) {
    return (
      <span className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700">
        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Studio Dev
        </span>
        <span className="num">
          {address.slice(0, 6)}…{address.slice(-4)}
        </span>
      </span>
    );
  }

  return (
    <button
      onClick={connect}
      disabled={busy}
      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60"
    >
      {busy ? (
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
      ) : (
        <Wallet size={14} strokeWidth={2.2} aria-hidden="true" />
      )}
      Connect
    </button>
  );
}
