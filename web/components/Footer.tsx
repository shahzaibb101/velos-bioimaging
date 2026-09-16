"use client";

import Link from "next/link";
import { useRef } from "react";
import Container from "./Container";
import Button from "./Button";
import { useInView } from "@/hooks/useInView";

const NAVIGATE = [
  { href: "/platform", label: "Platform" },
  { href: "/science", label: "Science" },
  { href: "/reconstruct", label: "Open the app" },
];

const CONNECT = [
  { href: "mailto:hello@velosbio.com", label: "hello@velosbio.com" },
  { href: "mailto:partnering@velosbio.com", label: "partnering@velosbio.com" },
];

export default function Footer() {
  const root = useRef<HTMLElement>(null);
  useInView(root, { selector: ".inview" });

  return (
    <footer className="footer" ref={root}>
      <div className="footer__backdrop" aria-hidden="true">
        <img src="/media/hero-poster.jpg" alt="" />
      </div>

      <Container className="footer__inner">
        <div className="footer__main">
          <div>
            <h2 className="footer__heading inview">
              We turn unstained cells into measurements, <em>and show our working.</em>
            </h2>
            <div className="footer__cta inview">
              <Button href="/reconstruct" label="Open the app" onDark />
            </div>
          </div>

          <div className="footer__info">
            <div className="footer__col">
              <p className="footer__col-label inview">Navigate</p>
              <ul>
                {NAVIGATE.map((item) => (
                  <li key={item.href} className="inview">
                    <Link href={item.href} className="footer__link">{item.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
            <div className="footer__col">
              <p className="footer__col-label inview">Contact</p>
              <ul>
                {CONNECT.map((item) => (
                  <li key={item.href} className="inview">
                    <a href={item.href} className="footer__link">{item.label}</a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <div className="footer__bottom">
          <p className="footer__meta">© {new Date().getFullYear()} Velos BioImaging</p>
          <p className="footer__meta">
            Specimens are simulated. The physics, reconstruction and measurements are not.
          </p>
        </div>

        <div className="footer__wordmark" aria-hidden="true">
          <svg viewBox="0 0 1000 150" preserveAspectRatio="xMidYMid meet">
            <text x="0" y="118" fontFamily="Aspekta, sans-serif" fontSize="150" letterSpacing="-7">
              VelosBio
            </text>
          </svg>
        </div>
      </Container>
    </footer>
  );
}
