"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { ScrollTrigger } from "@/lib/gsap";
import { scrollToTop, startScroll } from "@/lib/lenis";

/**
 * Put every route change back at the top of the page.
 *
 * The App Router restores scroll itself, but it does so through the document,
 * and Lenis owns the scroll position — so the browser's reset never reaches it
 * and you land halfway down a page you have just opened.
 *
 * Three other things have to happen on the same transition, and each of them is
 * a bug on its own if it is missed:
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

  useEffect(() => {
    if (first.current) {
      first.current = false;     // the initial load is already at the top
      return;
    }

    startScroll();
    scrollToTop(true);

    // After paint, so ScrollTrigger measures the page that is actually there.
    const frame = requestAnimationFrame(() => {
      ScrollTrigger.refresh();
      document.documentElement.classList.remove("has-scrolled");
    });

    // Move focus to the start of the new document without stealing it into a
    // visible focus ring: tabindex -1 makes <main> programmatically focusable.
    const main = document.getElementById("main");
    if (main) {
      main.focus({ preventScroll: true });
    }

    return () => cancelAnimationFrame(frame);
  }, [pathname]);

  return null;
}
