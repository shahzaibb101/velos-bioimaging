"use client";

import { useEffect } from "react";

/**
 * Declares the surface the header is sitting on.
 *
 * The hero infers this from an IntersectionObserver because its own dark panel
 * scrolls past. A page that is dark from top to bottom has nothing to observe,
 * and without this it inherits the light treatment and paints an ink logo onto
 * an ink background.
 *
 * Mounted per page rather than derived from the route, so a page can change
 * its mind (a dark app behind a light modal, say) without the header needing a
 * table of which URLs are dark.
 */
export default function HeaderTheme({ surface }: { surface: "dark" | "light" }) {
  useEffect(() => {
    if (surface !== "dark") return;
    const root = document.documentElement;
    root.classList.add("invert-logo");
    return () => root.classList.remove("invert-logo");
  }, [surface]);
  return null;
}
