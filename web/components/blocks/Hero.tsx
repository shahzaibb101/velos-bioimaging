"use client";

import { useEffect, useRef } from "react";
import Container from "@/components/Container";
import Button from "@/components/Button";
import HeroCanvas from "./HeroCanvas";
import { gsap, ScrollTrigger, SplitText, prefersReducedMotion } from "@/lib/gsap";

const STATEMENTS = [
  "Living cells are almost perfectly transparent. They barely absorb light, so under an ordinary microscope there is nothing to see.",
  "They do slow light down. That delay carries the cell's entire structure, and every camera ever built throws it away.",
  "We reconstruct it. No dye, no bleaching, no phototoxicity, and a dry mass in picograms for every cell in the field.",
];

const CLIP_OPEN = { duration: 2, delay: 0.3, ease: "expo.inOut" };

export default function Hero() {
  const root = useRef<HTMLElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const background = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const lead = useRef<HTMLParagraphElement>(null);
  const action = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const current = useRef<HTMLElement>(null);

  /* The opening. Everything else waits on it, so it is its own effect and runs
     before fonts resolve — the capsule is geometry, not type. */
  useEffect(() => {
    if (!canvas.current) return;
    if (prefersReducedMotion()) {
      gsap.set(canvas.current, { clipPath: "inset(0% round 0%)" });
      return;
    }
    const radius = window.matchMedia("(min-width: 1025px)").matches ? "200px" : "100px";
    const tween = gsap.fromTo(
      canvas.current,
      { clipPath: `inset(50% 50% 50% 50% round ${radius})` },
      {
        clipPath: "inset(0% 0% 0% 0% round 20px)",
        ...CLIP_OPEN,
        onComplete: () => gsap.set(canvas.current, { clipPath: "inset(0% round 0%)" }),
      }
    );
    return () => { tween.kill(); };
  }, []);

  /* Headline and lead. Split into masked lines only after fonts resolve,
     because SplitText measures line breaks and the fallback face breaks
     differently from Aspekta. */
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let splits: SplitText[] = [];
    let timeline: gsap.core.Timeline | null = null;
    let cancelled = false;

    (async () => {
      if (document.fonts?.ready) await document.fonts.ready;
      if (cancelled) return;

      timeline = gsap.timeline({ delay: 1.6 });
      [heading.current, lead.current].forEach((el) => {
        if (!el) return;
        const split = new SplitText(el, { type: "lines", linesClass: "line", mask: "lines", aria: "none" });
        splits.push(split);
        gsap.set(split.lines, { y: 110 });
        el.style.opacity = "1";
        timeline!.to(split.lines, { y: 0, ease: "power2.out", stagger: { each: 0.05 }, duration: 0.8 }, 0);
      });

      if (action.current) {
        gsap.set(action.current, { opacity: 0, y: 20, scale: 0.9 });
        timeline.to(action.current, { opacity: 1, y: 0, scale: 1, ease: "back.out(1.7)", duration: 0.6 }, 0.4);
      }
    })();

    return () => { cancelled = true; timeline?.kill(); splits.forEach((s) => s.revert()); };
  }, []);

  /* Background: the frame un-insets to full bleed, and the video drifts in
     scale so the hero keeps moving even where the copy has stopped. */
  useEffect(() => {
    if (!panel.current || !frame.current || prefersReducedMotion()) return;
    const el = frame.current;
    const media = canvas.current?.querySelector<HTMLElement>(".hero__media");

    const trigger = ScrollTrigger.create({
      trigger: panel.current,
      start: "top top",
      end: "bottom+=50px bottom",
      scrub: 1,
      onUpdate: ({ progress }) => {
        const base = window.matchMedia("(max-width: 1024px)").matches ? 8 : 12;
        const inset = base - base * progress;
        el.style.top = el.style.left = `${inset}px`;
        el.style.width = `calc(100% - ${inset * 2}px)`;
        el.style.height = `calc(100lvh - ${inset * 2}px)`;
        el.style.borderRadius = `${20 - 20 * progress}px`;
        if (media) gsap.set(media, { opacity: 0.875 - progress * 0.275, scale: 1 + progress * 0.2 });
      },
    });
    return () => trigger.kill();
  }, []);

  /* The pinned statement sequence, and the background pin that has to span it.
     Both live in one effect because the background's pin distance depends on
     how far the scroller pins for, and creating them out of order leaves the
     background un-pinned behind the statements — which shows up as white text
     on the page canvas. */
  useEffect(() => {
    const el = scroller.current;
    const bg = background.current;
    const heroEl = root.current;
    if (!el || !bg || !heroEl || prefersReducedMotion()) return;

    const items = Array.from(el.querySelectorAll<HTMLElement>(".hero__statement"));
    if (!items.length) return;

    const splits = items.map((item) => {
      const p = item.querySelector("p")!;
      // "words" has to be in the split even though nothing styles them.
      // Splitting straight to chars makes every character its own inline-block,
      // and the browser will then happily break a line between two of them, so
      // "away" wraps as "awa / y". Keeping word wrappers gives it something
      // atomic to break on.
      const split = new SplitText(p, {
        type: "lines, words, chars",
        linesClass: "line",
        wordsClass: "word",
        charsClass: "char",
        mask: "lines",
        aria: "none",
      });
      gsap.set(split.chars, { opacity: 0.4 });
      return split;
    });

    gsap.set(items[0], { autoAlpha: 1 });
    items.slice(1).forEach((item) => gsap.set(item, { autoAlpha: 0 }));

    let active = 0;
    const swap = (from: number, to: number) => {
      if (from === to) return;
      gsap.to(splits[from].lines, {
        autoAlpha: 0, y: -30, ease: "power4.out", duration: 0.4, stagger: 0.05,
        onComplete: () => gsap.set(items[from], { autoAlpha: 0 }),
      });
      gsap.delayedCall(0.5, () => {
        gsap.set(items[to], { autoAlpha: 1 });
        gsap.fromTo(splits[to].lines, { autoAlpha: 0, y: 30 },
          { autoAlpha: 1, y: 0, ease: "power4.out", duration: 0.5, stagger: 0.05 });
      });
    };

    const travel = items.length * 1000;

    const pinStatements = ScrollTrigger.create({
      trigger: el,
      start: "top top",
      end: `+=${travel}px`,
      pin: true,
      scrub: true,
      onUpdate: ({ progress }) => {
        const index = Math.max(0, Math.min(items.length - 1, Math.floor(progress * items.length + 1e-6)));
        if (bar.current) gsap.set(bar.current, { scaleX: progress });
        if (current.current) current.current.textContent = String(index + 1).padStart(2, "0");
        if (index !== active) { swap(active, index); active = index; }

        const chars = splits[index].chars as HTMLElement[];
        const local = Math.min((progress * items.length - index) * 1.5, 1);
        const upto = Math.floor(local * chars.length);
        chars.forEach((c, i) => {
          const opacity = i < upto ? 1 : i === upto ? 0.4 + (local * chars.length - upto) * 0.6 : 0.4;
          gsap.set(c, { opacity });
        });
      },
    });

    // pinSpacing:false so the background rides along without adding its own
    // scroll length on top of the scroller's.
    const pinBackground = ScrollTrigger.create({
      trigger: heroEl,
      start: "top top",
      end: () => `+=${el.offsetTop + el.offsetHeight + travel}px`,
      pin: bg,
      pinSpacing: false,
    });

    ScrollTrigger.refresh();

    return () => {
      pinStatements.kill();
      pinBackground.kill();
      splits.forEach((s) => s.revert());
    };
  }, []);

  /* While the hero fills the viewport the header sits on a dark surface.
     The initial state is computed synchronously rather than waiting on the
     observer: IntersectionObserver only reports *changes*, and under React's
     double-invoked effects in development the first mount's cleanup can strip
     the class after the second mount's callback has already fired, leaving the
     header in its light state over a dark hero until something else scrolls. */
  useEffect(() => {
    const el = root.current;
    if (!el) return;

    const apply = (visible: boolean) =>
      document.documentElement.classList.toggle("invert-logo", visible);

    const box = el.getBoundingClientRect();
    apply(box.top < window.innerHeight && box.bottom > 0);

    const observer = new IntersectionObserver(
      ([entry]) => apply(entry.isIntersecting),
      { threshold: 0 }
    );
    observer.observe(el);
    return () => { observer.disconnect(); apply(false); };
  }, []);

  return (
    <section className="hero" ref={root}>
      <div className="hero__panel" ref={panel}>
        <Container className="hero__inner">
          <h1 className="hero__heading" ref={heading} style={{ opacity: 0 }}>
            Label-free imaging, reconstructed.
          </h1>
          <div className="hero__bottom">
            <p className="hero__lead" ref={lead} style={{ opacity: 0 }}>
              Quantitative phase imaging for live cells. Calibrated phase maps and per-cell dry
              mass, from samples that were never stained.
            </p>
            <div className="hero__action" ref={action}>
              <Button href="/reconstruct" label="Open the app" onDark />
            </div>
          </div>
        </Container>
      </div>

      <div className="hero__scroller" ref={scroller}>
        <Container className="hero__scroller-inner">
          <span className="hero__eyebrow">What we do</span>
          <div className="hero__progress"><span ref={bar} /></div>
          <div className="hero__statements">
            <aside className="hero__index">
              <span ref={current}>01</span><i>/</i><i>{String(STATEMENTS.length).padStart(2, "0")}</i>
            </aside>
            <div className="hero__stage">
              {STATEMENTS.map((text, i) => (
                <div className="hero__statement" key={i}><p>{text}</p></div>
              ))}
            </div>
          </div>
        </Container>
      </div>

      <figure className="hero__background" ref={background}>
        <div className="hero__frame" ref={frame}>
          <div className="hero__canvas" ref={canvas}>
            <HeroCanvas poster="/media/hero-poster.jpg" src="/media/hero-reconstruction.mp4" />
          </div>
        </div>
      </figure>
    </section>
  );
}
