import { PageTransition } from "@/components/page-transition";

/** A template rather than a layout: Next.js remounts a template on every
 *  navigation, which is what makes the transition fire at all. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}
