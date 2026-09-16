"use client";

import { useEffect, useRef } from "react";
import { gsap, ScrollTrigger, prefersReducedMotion } from "@/lib/gsap";

/**
 * Infinite marquee whose direction follows the scroll.
 *
 * Scrolling down runs it one way, scrolling up reverses it. That coupling is
 * what stops a marquee reading as decoration: it becomes a readout of what the
 * reader is doing rather than a loop playing regardless.
 */
export default function Marquee({ text, accent, copies = 3, speed = 15 }: {
  text: string; accent?: string; copies?: number; speed?: number;
}) {
  const root = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const marquee = root.current;
    const track = scroll.current;
    if (!marquee || !track || prefersReducedMotion()) return;

    const sets = Array.from(track.querySelectorAll<HTMLElement>(".marquee__set"));
    if (!sets.length) return;

    const width = sets[0].offsetWidth;
    const factor = window.innerWidth < 479 ? 0.25 : window.innerWidth < 991 ? 0.5 : 1;
    const duration = speed * (width / window.innerWidth) * factor;

    // totalProgress(0.5) starts the loop mid-cycle so there is never a visible
    // seam on the first pass.
    const loop = gsap.to(sets, { xPercent: -100, repeat: -1, duration, ease: "linear" }).totalProgress(0.5);
    gsap.set(sets, { xPercent: -100 });
    loop.timeScale(-1);
    loop.play();

    const trigger = ScrollTrigger.create({
      trigger: marquee, start: "top bottom", end: "bottom top",
      onUpdate: ({ direction }) => {
        const down = direction === 1;
        loop.timeScale(down ? -1 : 1);
        marquee.dataset.direction = down ? "forward" : "reverse";
      },
    });

    const drift = gsap.timeline({
      scrollTrigger: { trigger: marquee, start: "0% 100%", end: "100% 0%", scrub: 0 },
    });
    drift.fromTo(track, { x: "10vw" }, { x: "-10vw", ease: "none" });

    return () => {
      trigger.kill();
      drift.scrollTrigger?.kill(); drift.kill();
      loop.kill();
    };
  }, [speed, copies]);

  return (
    <section className="section marquee-block">
      <div className="marquee" ref={root} data-direction="forward">
        <div className="marquee__scroll" ref={scroll} style={{ marginLeft: "-10%", width: "120%" }}>
          {Array.from({ length: copies }).map((_, i) => (
            <div className="marquee__set" key={i} aria-hidden={i > 0}>
              <div className="marquee__item">
                <p>{text} {accent && <span>{accent}</span>}&nbsp;</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
