"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Logo from "./Logo";
import Button from "./Button";
import Container from "./Container";
import { startScroll, stopScroll } from "@/lib/lenis";

const NAV = [
  { href: "/platform", label: "Platform" },
  { href: "/science", label: "Science" },
];

export default function Header() {
  const [open, setOpen] = useState(false);

  /* `has-scrolled` drives the logo plate and fill; it lives on <html> so any
     block can respond to it without prop drilling. Threshold is 10px so it
     does not flicker on a trackpad nudge. */
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        document.documentElement.classList.toggle("has-scrolled", window.scrollY > 10);
        frame = 0;
      });
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("scroll", onScroll); cancelAnimationFrame(frame); };
  }, []);

  // A full-screen menu that leaves the page scrollable behind it is disorienting.
  useEffect(() => {
    document.documentElement.dataset.nav = open ? "open" : "closed";
    if (open) stopScroll(); else startScroll();
  }, [open]);

  return (
    <>
      <header className="header">
        <Container className="header__inner">
          <Link href="/" className="header__logo" aria-label="Velos BioImaging, home">
            <Logo />
          </Link>

          <nav className="header__nav" aria-label="Main">
            <ul className="header__menu">
              {NAV.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} className="header__link">{item.label}</Link>
                </li>
              ))}
            </ul>
            <Button href="/reconstruct" label="Open the app" variant="solid" className="header__cta" />
            <button
              className="header__toggle"
              aria-label={open ? "Close menu" : "Open menu"}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
            >
              <span /><span />
            </button>
          </nav>
        </Container>
      </header>

      <nav className="header__popup" aria-label="Menu" aria-hidden={!open}>
        <ul className="header__popup-menu">
          {[...NAV, { href: "/reconstruct", label: "Open the app" }].map((item) => (
            <li key={item.href}>
              <Link href={item.href} className="header__popup-link" onClick={() => setOpen(false)}>
                <span>{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
        <div className="header__popup-cta">
          <a href="mailto:hello@velosbio.com"><span>hello@velosbio.com</span></a>
        </div>
      </nav>
    </>
  );
}
