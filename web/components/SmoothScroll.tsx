"use client";

import { useEffect } from "react";
import Lenis from "lenis";
import { gsap, ScrollTrigger, prefersReducedMotion } from "@/lib/gsap";
import { setLenis } from "@/lib/lenis";

/**
 * Lenis driven by the GSAP ticker rather than its own rAF loop.
 *
 * Running two independent animation loops is the usual cause of scroll-linked
 * animations drifting a frame behind the scroll position. Handing Lenis the
 * ticker's time and switching off lag smoothing keeps ScrollTrigger and the
 * scroll itself on exactly the same clock.
 *
 * `introLockMs` holds the page still while the hero opens. The reference locks
 * for 2300ms, which is the 300ms clip-path delay plus its 2000ms duration.
 */
export default function SmoothScroll({ introLockMs = 0 }: { introLockMs?: number }) {
  useEffect(() => {
    const reduced = prefersReducedMotion();

    const lenis = new Lenis({
      lerp: 0.1,
      duration: 1.2,
      autoRaf: false,
      anchors: true,
      prevent: (node) => node.classList?.contains("modal_view") ?? false,
    });
    setLenis(lenis);

    lenis.on("scroll", ScrollTrigger.update);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);

    window.scrollTo(0, 0);
    lenis.scrollTo(0, { immediate: true });

    let release: number | undefined;
    if (reduced) {
      document.documentElement.classList.add("has-reduced-motion");
      lenis.stop();
    } else if (introLockMs > 0) {
      lenis.stop();
      release = window.setTimeout(() => lenis.start(), introLockMs);
    }

    const onResize = () => ScrollTrigger.refresh();
    window.addEventListener("resize", onResize, { passive: true });

    return () => {
      if (release) clearTimeout(release);
      window.removeEventListener("resize", onResize);
      gsap.ticker.remove(tick);
      lenis.destroy();
      setLenis(null);
    };
  }, [introLockMs]);

  return null;
}
