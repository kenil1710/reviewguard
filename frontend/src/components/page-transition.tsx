"use client";

import { motion, useReducedMotion } from "framer-motion";

/**
 * A short fade-and-rise on route change.
 *
 * Deliberately small — 200ms and eight pixels. A page of evidence about
 * somebody's product should feel like a document settling, not like a slide
 * deck. It is also fully skipped for a reader who has asked the OS for less
 * motion, which is the difference between a flourish and an accessibility bug.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  if (reduce) return <>{children}</>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
