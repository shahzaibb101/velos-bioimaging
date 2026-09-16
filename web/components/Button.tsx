"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { gsap, MorphSVGPlugin } from "@/lib/gsap";

/* The two hand-drawn states for each shape. The corner is the trailing edge of
   the label; the blob is the arrow's container. Morphing both together is what
   makes the notch between them appear to lean on hover. */
const SHAPES = {
  corner: {
    rest: "M0 0h5.63c7.808 0 13.536 7.337 11.642 14.91l-6.09 24.359A11.527 11.527 0 0 1 0 48V0Z",
    hover: "M0 0c5.29 0 9.9 3.6 11.183 8.731l6.09 24.359C19.165 40.663 13.437 48 5.63 48H0V0Z",
  },
  blob: {
    rest: "M6.728 9.09A12 12 0 0 1 18.369 0H39c6.627 0 12 5.373 12 12v24c0 6.627-5.373 12-12 12H12.37C4.561 48-1.167 40.663.727 33.09l6-24Z",
    hover: "M.728 14.91C-1.166 7.338 4.562 0 12.369 0H39c6.628 0 12 5.373 12 12v24c0 6.627-5.372 12-12 12H18.37a12 12 0 0 1-11.641-9.09l-6-24Z",
  },
} as const;

type Variant = "primary" | "blob" | "solid" | "text";

interface ButtonProps {
  href: string;
  label: string;
  variant?: Variant;
  onDark?: boolean;
  className?: string;
  ariaLabel?: string;
  /** Morph on hover of an ancestor instead of the button itself, for cards. */
  hoverScope?: string;
}

export default function Button({
  href,
  label,
  variant = "primary",
  onDark = false,
  className = "",
  ariaLabel,
  hoverScope,
}: ButtonProps) {
  const root = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el || variant === "solid") return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

    const corner = el.querySelector<SVGPathElement>(".btn__corner path");
    const blob = el.querySelector<SVGPathElement>(".btn__icon path");
    if (!blob) return;

    // A card-level button should react to the whole card being hovered, not
    // only the 48px target, otherwise the arrow sits inert while the card lifts.
    const scope = (hoverScope ? el.closest(hoverScope) : null) ?? el;

    const to = (state: "rest" | "hover") => {
      if (corner) gsap.to(corner, { morphSVG: SHAPES.corner[state], duration: 0.3, ease: "power2.out" });
      gsap.to(blob, { morphSVG: SHAPES.blob[state], duration: 0.3, ease: "power2.out" });
    };
    const enter = () => to("hover");
    const leave = () => to("rest");

    scope.addEventListener("mouseenter", enter);
    scope.addEventListener("mouseleave", leave);
    return () => {
      scope.removeEventListener("mouseenter", enter);
      scope.removeEventListener("mouseleave", leave);
    };
  }, [variant, hoverScope]);

  const classes = [
    "btn",
    `btn--${variant}`,
    onDark && variant === "primary" ? "is-on-dark" : "",
    className,
  ].filter(Boolean).join(" ");

  if (variant === "solid") {
    return (
      <Link href={href} className={classes} data-label={label} aria-label={ariaLabel ?? label}>
        <span className="btn__label">{label}</span>
      </Link>
    );
  }

  return (
    <Link href={href} ref={root} className={classes} aria-label={ariaLabel ?? label}>
      {variant !== "blob" && (
        <span className="btn__label">
          {label}
          {variant === "primary" && (
            <span className="btn__corner" aria-hidden="true">
              <svg viewBox="0 0 18 48" fill="none"><path d={SHAPES.corner.rest} /></svg>
            </span>
          )}
        </span>
      )}
      <i className="btn__icon" aria-hidden="true">
        <svg viewBox="0 0 51 48" fill="none"><path d={SHAPES.blob.rest} fill="currentColor" /></svg>
      </i>
    </Link>
  );
}
