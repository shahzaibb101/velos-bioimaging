"use client";

import { useEffect, RefObject } from "react";

type Edge = "top" | "right" | "bottom" | "left";
const OFFSCREEN: Record<Edge, string> = {
  top: "translateY(-100%)",
  bottom: "translateY(100%)",
  left: "translateX(-100%)",
  right: "translateX(100%)",
};

/** Which edge of `rect` the pointer is nearest. */
function nearestEdge(event: MouseEvent, el: HTMLElement, axis: "x" | "y" | "all"): Edge {
  const { left, top, width, height } = el.getBoundingClientRect();
  const x = event.clientX - left;
  const y = event.clientY - top;
  if (axis === "y") return y < height / 2 ? "top" : "bottom";
  if (axis === "x") return x < width / 2 ? "left" : "right";
  const distances: Record<Edge, number> = { top: y, right: width - x, bottom: height - y, left: x };
  return (Object.entries(distances) as [Edge, number][]).reduce((a, b) => (a[1] < b[1] ? a : b))[0];
}

/**
 * Direction-aware hover fill: the panel enters from whichever edge the cursor
 * actually crossed and leaves through whichever edge it exits by, so the fill
 * appears to be pushed by the pointer rather than simply switched on.
 *
 * Written once as a hook rather than per block, since three list-like blocks
 * all want it.
 *
 * The `offsetHeight` read is deliberate: it forces a reflow so the browser
 * commits the un-transitioned starting transform before the transition is
 * restored. Without it the panel slides from wherever it last stopped.
 */
export function useDirectionalHover(
  ref: RefObject<HTMLElement | null>,
  { itemSelector = ".hover-item", panelSelector = ".hover-panel", axis = "all" as "x" | "y" | "all" } = {}
) {
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    if (!window.matchMedia("(min-width: 1025px)").matches) return;

    const items = Array.from(root.querySelectorAll<HTMLElement>(itemSelector));
    const teardown: (() => void)[] = [];

    items.forEach((item) => {
      const panel = item.querySelector<HTMLElement>(panelSelector);
      if (!panel) return;

      const enter = (e: MouseEvent) => {
        const edge = nearestEdge(e, item, axis);
        panel.style.transition = "none";
        panel.style.transform = OFFSCREEN[edge];
        void panel.offsetHeight;
        panel.style.transition = "";
        panel.style.transform = "translate(0%, 0%)";
        item.dataset.status = `enter-${edge}`;
      };
      const leave = (e: MouseEvent) => {
        const edge = nearestEdge(e, item, axis);
        item.dataset.status = `leave-${edge}`;
        panel.style.transform = OFFSCREEN[edge];
      };

      item.addEventListener("mouseenter", enter);
      item.addEventListener("mouseleave", leave);
      teardown.push(() => {
        item.removeEventListener("mouseenter", enter);
        item.removeEventListener("mouseleave", leave);
      });
    });

    return () => teardown.forEach((fn) => fn());
  }, [ref, itemSelector, panelSelector, axis]);
}
