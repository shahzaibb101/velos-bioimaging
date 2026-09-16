"use client";

import { useEffect } from "react";

/**
 * Flips <html> from is-loading to has-loaded once fonts have resolved.
 *
 * Without this the hero headline paints in the fallback face, then reflows when
 * Aspekta arrives, and because the headline is split into masked lines the
 * reflow happens *after* the split has measured — so lines get clipped at the
 * wrong height. Waiting for fonts is not a nicety here, it is what keeps the
 * reveal correct.
 */
export default function LoadState() {
  useEffect(() => {
    let done = false;
    const reveal = () => {
      if (done) return;
      done = true;
      const root = document.documentElement;
      root.classList.remove("is-loading");
      root.classList.add("has-loaded");
    };
    if (document.fonts?.ready) document.fonts.ready.then(reveal);
    // Never leave the page invisible because a font request hung.
    const failsafe = setTimeout(reveal, 2000);
    return () => clearTimeout(failsafe);
  }, []);
  return null;
}
