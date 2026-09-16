"use client";

import { useEffect, RefObject } from "react";
import { gsap, ScrollTrigger, SplitText, motionAllowed } from "@/lib/gsap";

/**
 * Word-by-word curtain reveal.
 *
 * Each word is wrapped and given an absolutely positioned overlay filled with
 * `currentColor`, then the overlay is wiped away with scaleY. Using currentColor
 * rather than a fixed value means the same component works on a light section
 * and a dark one with no configuration, and the curtain can never mismatch the
 * text it is covering.
 *
 * The overlays are removed from the DOM when the animation finishes so they
 * cannot interfere with selection or hit testing afterwards.
 */
export function useTextReveal(
  ref: RefObject<HTMLElement | null>,
  { duration = 0.8, stagger = 0.1, ease = "expo.out", start = "top 80%", delay = 0 } = {}
) {
  useEffect(() => {
    const el = ref.current;
    if (!el || !motionAllowed()) return;

    let split: SplitText | null = null;
    let trigger: ScrollTrigger | null = null;
    let cancelled = false;

    const run = async () => {
      if (document.fonts?.ready) await document.fonts.ready;
      await new Promise((r) => requestAnimationFrame(r));
      if (cancelled || !ref.current) return;

      split = new SplitText(el, { type: "words", wordsClass: "reveal-word" });
      const overlays: HTMLElement[] = [];

      (split.words as HTMLElement[]).forEach((word) => {
        word.style.position = "relative";
        word.style.overflow = "hidden";
        const overlay = document.createElement("span");
        overlay.setAttribute("aria-hidden", "true");
        overlay.style.cssText =
          "position:absolute;inset:0;background-color:currentColor;" +
          "transform-origin:bottom;transform:scaleY(1);pointer-events:none;z-index:1";
        word.appendChild(overlay);
        overlays.push(overlay);
      });

      trigger = ScrollTrigger.create({
        trigger: el,
        start,
        once: true,
        onEnter: () =>
          gsap.to(overlays, {
            scaleY: 0,
            duration,
            ease,
            stagger,
            delay,
            onComplete: () => overlays.forEach((o) => o.remove()),
          }),
      });
    };

    run();
    return () => {
      cancelled = true;
      trigger?.kill();
      split?.revert();
    };
  }, [ref, duration, stagger, ease, start, delay]);
}
