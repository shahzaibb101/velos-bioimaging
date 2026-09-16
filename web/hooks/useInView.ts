"use client";

import { useEffect, RefObject } from "react";
import { gsap, ScrollTrigger, motionAllowed } from "@/lib/gsap";

/**
 * The site-wide entrance: fade up 20px, 0.8s, power2.out, 0.05 stagger,
 * firing when the element's top reaches 80% of the viewport.
 *
 * Deliberately `play none none none` so it never reverses. Content that
 * re-hides when you scroll back up reads as a gimmick rather than as the page
 * settling into place.
 */
export function useInView(
  ref: RefObject<HTMLElement | null>,
  { selector = ".inview", y = 20, duration = 0.8, stagger = 0.05, start = "top 80%", delay = 0 } = {}
) {
  useEffect(() => {
    const el = ref.current;
    if (!el || !motionAllowed()) return;

    const targets = selector ? Array.from(el.querySelectorAll<HTMLElement>(selector)) : [el];
    if (!targets.length) return;

    gsap.set(targets, { opacity: 0, y });
    const tween = gsap.to(targets, {
      opacity: 1,
      y: 0,
      duration,
      stagger,
      delay,
      ease: "power2.out",
      scrollTrigger: { trigger: el, start, toggleActions: "play none none none" },
    });

    return () => {
      tween.scrollTrigger?.kill();
      tween.kill();
      gsap.set(targets, { clearProps: "opacity,transform" });
    };
  }, [ref, selector, y, duration, stagger, start, delay]);
}
