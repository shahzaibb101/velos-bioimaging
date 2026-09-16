"use client";

import { useRef, ReactNode } from "react";
import Container from "@/components/Container";
import { useTextReveal } from "@/hooks/useTextReveal";
import { useInView } from "@/hooks/useInView";

/**
 * Label, heading, body, action. The heading gets the word-curtain reveal; the
 * rest rises on the standard entrance.
 *
 * `heading` takes a node rather than a string so a trailing clause can be
 * wrapped in <em> and recede into Lichen, letting a long sentence resolve
 * without needing a second type size.
 */
export default function Statement({
  label, heading, children, action, split = false, className = "", ascent = true,
}: {
  label?: string;
  heading: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  split?: boolean;
  className?: string;
  ascent?: boolean;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  useTextReveal(headingRef);
  useInView(bodyRef, { selector: ".inview" });

  return (
    <section className={`section statement ${split ? "statement--split" : ""} ${className}`}>
      <Container className="statement__inner">
        <aside className={ascent ? "ascent" : undefined}>
          {label && <span className="label inview">{label}</span>}
        </aside>
        <div className={`statement__body ${ascent ? "ascent" : ""}`} ref={bodyRef}>
          <h2 className="statement__heading" ref={headingRef}>{heading}</h2>
          {children && <div className="statement__text inview">{children}</div>}
          {action && <div className="inview">{action}</div>}
        </div>
      </Container>
    </section>
  );
}
