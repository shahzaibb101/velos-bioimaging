"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { MorphSVGPlugin } from "gsap/MorphSVGPlugin";

/* SplitText and MorphSVG were paid GSAP Club plugins until 2025. They now ship
   in the public package, so the masked line reveals and the morphing button
   blobs cost nothing to use. */
if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, SplitText, MorphSVGPlugin);
}

export { gsap, ScrollTrigger, SplitText, MorphSVGPlugin };

export const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** The reference gates most motion behind desktop + no reduced-motion. */
export const motionAllowed = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: no-preference) and (min-width: 1025px)").matches;
