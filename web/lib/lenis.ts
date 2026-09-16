"use client";

import type Lenis from "lenis";

/**
 * Module-level handle on the smooth-scroll instance, plus the scrolling the
 * app actually needs.
 *
 * Deliberately not on `window`: the Lenis package already declares a
 * `window.lenis` of its own shape, and redeclaring it fights the library's
 * types.
 *
 * Everything here routes through Lenis rather than `window.scrollTo` or
 * `Element.scrollIntoView`. Lenis owns the scroll position, so native calls
 * move the document underneath it and the two desynchronise: the page jumps,
 * then slides back as Lenis reasserts where it thinks it should be.
 */
let instance: Lenis | null = null;

export const setLenis = (l: Lenis | null) => { instance = l; };
export const getLenis = () => instance;
export const stopScroll = () => instance?.stop();
export const startScroll = () => instance?.start();

const reducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Height of the fixed header, so scrolled-to content is not tucked under it. */
export function headerOffset(): number {
  if (typeof window === "undefined") return 0;
  return window.matchMedia("(min-width: 1025px)").matches ? 108 : 96;
}

export function scrollToTop(immediate = false): void {
  const jump = immediate || reducedMotion();
  if (instance) {
    instance.scrollTo(0, jump ? { immediate: true, force: true } : { duration: 1.0, force: true });
  } else {
    window.scrollTo({ top: 0, behavior: jump ? "auto" : "smooth" });
  }
}

/**
 * Bring an element into view, allowing for the fixed header.
 *
 * `force: true` matters. Lenis refuses scrollTo on a stopped instance, and the
 * instance is stopped while the hero intro plays and while the menu is open —
 * so without it, a scroll requested during either is silently dropped.
 */
export function scrollToElement(
  target: Element | null,
  { offset = -headerOffset(), duration = 1.0, immediate = false } = {}
): void {
  if (!target) return;
  const jump = immediate || reducedMotion();

  if (instance) {
    instance.scrollTo(target as HTMLElement, {
      offset,
      force: true,
      ...(jump ? { immediate: true } : { duration }),
    });
    return;
  }
  const top = target.getBoundingClientRect().top + window.scrollY + offset;
  window.scrollTo({ top, behavior: jump ? "auto" : "smooth" });
}
