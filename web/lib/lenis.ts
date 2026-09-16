"use client";

import type Lenis from "lenis";

/**
 * Module-level handle on the smooth-scroll instance.
 *
 * Deliberately not on `window`: the Lenis package already declares a
 * `window.lenis` of its own shape, and redeclaring it fights the library's
 * types. A module singleton gives the same "anything can reach it" ergonomics
 * with none of that.
 */
let instance: Lenis | null = null;

export const setLenis = (l: Lenis | null) => { instance = l; };
export const getLenis = () => instance;
export const stopScroll = () => instance?.stop();
export const startScroll = () => instance?.start();
export const scrollToTop = (immediate = false) =>
  instance?.scrollTo(0, immediate ? { immediate: true } : { duration: 1.2 });
