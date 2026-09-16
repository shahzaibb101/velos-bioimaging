import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import SmoothScroll from "@/components/SmoothScroll";
import LoadState from "@/components/LoadState";
import ScrollReset from "@/components/ScrollReset";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  metadataBase: new URL("https://velosbio.com"),
  title: {
    default: "Velos BioImaging — Label-free imaging, reconstructed",
    template: "%s — Velos BioImaging",
  },
  description:
    "Quantitative phase imaging for live cells. We reconstruct unstained cells into calibrated phase maps and per-cell dry mass, without dyes, without photodamage.",
  openGraph: {
    type: "website",
    siteName: "Velos BioImaging",
    title: "Velos BioImaging — Label-free imaging, reconstructed",
    description:
      "Quantitative phase imaging for live cells. Calibrated phase maps and per-cell dry mass from unstained samples.",
  },
  robots: { index: true, follow: true },
};

/* The intro lock matches the hero's clip-path reveal: 300ms delay plus a
   2000ms expansion. Scrolling during it would fight the animation, so the page
   is held for exactly that long and no longer. */
const INTRO_LOCK_MS = 2300;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="is-loading">
      <body>
        <LoadState />
        <SmoothScroll introLockMs={INTRO_LOCK_MS} />
        <ScrollReset />
        <a className="skip-link" href="#main">Skip to content</a>
        <Header />
        {/* tabIndex -1 so a route change can move focus here without it
            becoming a tab stop of its own. */}
        <main id="main" tabIndex={-1}>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
