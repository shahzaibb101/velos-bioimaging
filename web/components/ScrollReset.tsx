"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { ScrollTrigger } from "@/lib/gsap";
import { scrollToTop, startScroll } from "@/lib/lenis";

/**
 * Scroll behaviour across route changes.
 *
 * Two different intents, and they want opposite things:
 *
 *  - Following a link is arriving somewhere new. It belongs at the top.
 *  - Going back is returning somewhere you have already been. It belongs where
 *    you left it, and forcing it to the top would throw away the position the
 *    reader is trying to get back to.
 *
 * The App Router restores scroll for history navigation on its own, but it
 * does so through the document, and Lenis owns the scroll position. The two
 * happen to settle correctly today only because the restore lands after this
 * effect; that is a race, so back/forward is detected explicitly and left
 * alone instead of being reset and then corrected.
 *
 * Three other things have to happen on every transition regardless:
 *
 *  - ScrollTrigger measures against a document that has just been replaced.
 *    The homepage pins 4800px of hero; leaving it without a refresh leaves
 *    stale pin spacers in the measurements.
 *  - Lenis can be stopped when navigation happens (the intro lock, or an open
 *    menu) and would otherwise stay stopped on the new page.
 *  - Focus stays on whatever link was clicked, so a screen reader announces
 *    nothing and the next Tab resumes from the old page's position.
 */
export default function ScrollReset() {
  const pathname = usePathname();
  const first = useRef(true);
  const cameFromHistory = useRef(false);

  // popstate fires before the router commits the new pathname, so this flag is
  // set by the time the effect below runs.
  useEffect(() => {
    const onPop = () => { cameFromHistory.current = true; };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    if (first.current) {
      first.current = false;     // the initial load is already at the top
      return;
    }

    const restoring = cameFromHistory.current;
    cameFromHistory.current = false;

    startScroll();
    if (!restoring) scrollToTop(true);

    // After paint, so ScrollTrigger measures the page that is actually there.
    const frame = requestAnimationFrame(() => {
      ScrollTrigger.refresh();
      document.documentElement.classList.toggle("has-scrolled", window.scrollY > 10);
    });

    // Move focus to the start of the new document without drawing a focus ring:
    // <main> carries tabindex -1 so it is programmatically focusable only.
    // Skipped when restoring, so returning to a page does not jump the reader
    // back to the top of it.
    if (!restoring) document.getElementById("main")?.focus({ preventScroll: true });

    return () => cancelAnimationFrame(frame);
  }, [pathname]);

  return null;
}
