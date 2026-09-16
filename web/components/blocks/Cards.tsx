"use client";

import { useEffect, useRef } from "react";
import { gsap, ScrollTrigger, motionAllowed } from "@/lib/gsap";

export interface Card {
  index: string;
  heading: string;
  text: string;
  icon: React.ReactNode;
  tone?: "light" | "dark" | "teal";
}

/**
 * Capability cards.
 *
 * Cards wipe in by animating clip-path from a zero-width polygon rather than
 * by fading. A fade would let the card's background bleed through the section
 * behind it mid-transition; a clip keeps every edge hard, which is what suits
 * a layout built entirely from flat blocks with no shadows.
 */
export default function Cards({ cards }: { cards: Card[] }) {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el || !motionAllowed()) return;

    const items = Array.from(el.querySelectorAll<HTMLElement>(".card"));
    const contents = items.map((card) =>
      Array.from(card.querySelectorAll<HTMLElement>(".card__index, .card__icon, .card__heading, .card__text"))
    );

    gsap.set(items, { clipPath: "polygon(0 0, 0% 0, 0% 100%, 0% 100%)" });
    contents.flat().forEach((node) => gsap.set(node, { opacity: 0, y: 20 }));

    const wipe = gsap.to(items, {
      clipPath: "polygon(0 0, 100% 0, 100% 100%, 0% 100%)",
      duration: 1, ease: "expo.out", stagger: 0.15,
      scrollTrigger: { trigger: el, start: "top 80%", toggleActions: "play none none none" },
    });

    const timeline = gsap.timeline({
      scrollTrigger: { trigger: el, start: "top 80%", toggleActions: "play none none none" },
    });
    timeline.to({}, { duration: 0.6 });
    contents.forEach((nodes, i) => {
      timeline.to(nodes, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out", stagger: 0.2 }, i * 0.15);
    });

    return () => {
      wipe.scrollTrigger?.kill(); wipe.kill();
      timeline.scrollTrigger?.kill(); timeline.kill();
      gsap.set([...items, ...contents.flat()], { clearProps: "all" });
    };
  }, [cards.length]);

  return (
    <section className="section">
      <div className="cards" ref={root}>
        {cards.map((card) => (
          <article
            key={card.index}
            className={`card ${card.tone === "dark" ? "card--dark" : card.tone === "teal" ? "card--teal" : ""}`}
          >
            <span className="card__index">{card.index}</span>
            <div className="card__icon" aria-hidden="true">{card.icon}</div>
            <div className="card__content">
              <h3 className="card__heading">{card.heading}</h3>
              <p className="card__text">{card.text}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
