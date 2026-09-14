import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "ReviewGuard — Are those reviews real?",
    template: "%s · ReviewGuard",
  },
  description:
    "Submit any product review page. GenLayer validators independently fetch it, score five manipulation signals, and agree on the numbers before anything is written on chain.",
  openGraph: {
    title: "ReviewGuard — Are those reviews real?",
    description:
      "A fake-review detector any contract can read. Five dimensions, bound by consensus.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
