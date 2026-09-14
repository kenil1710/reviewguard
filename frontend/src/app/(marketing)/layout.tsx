import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

/** No wallet and no network badge here. A landing page that asks for a wallet
 *  before it has said what the product does is a landing page people leave. */
export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader wallet={false} />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
