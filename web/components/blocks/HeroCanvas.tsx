"use client";

import { useEffect, useRef } from "react";

/**
 * The hero surface: a reconstructed live-cell time-lapse that reacts to the
 * cursor as a physical object would.
 *
 * The reference achieves this with a WebGL layer that rotates the image on two
 * axes from the pointer and runs two mouse-tracked progressive blurs over it.
 * None of that needs a GL context. A 3D rotation on the element plus a
 * cursor-anchored radial scrim reproduces the same read: the image sits behind
 * the page rather than on it, and it acknowledges you without demanding
 * attention.
 *
 * Motion is integrated toward the pointer each frame rather than assigned, so
 * it carries momentum and settles instead of snapping. That single detail is
 * most of the difference between this feeling like an object and feeling like
 * a hover state.
 */

const TILT_DEGREES = 3.2;   // rotation at the far edge of the viewport
const DRIFT_PIXELS = 18;    // parallax travel of the image inside its frame
const EASE = 0.045;         // per-frame approach; lower is heavier

/* The source is a 5s loop of real reconstruction frames. Played at rate the
   cell drift reads as busy and the repeat becomes obvious; slowed to a ~14s
   cycle it becomes ambient, which is the register the reference's 25s loop
   sits in. Slowing playback rather than re-encoding keeps the frames exactly
   as the pipeline produced them. */
const PLAYBACK_RATE = 0.35;

export default function HeroCanvas({ poster, src }: { poster: string; src: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const media = useRef<HTMLVideoElement>(null);
  const scrim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = wrap.current;
    const video = media.current;
    const glow = scrim.current;
    if (!el || !video) return;

    /* Pacing and playback resilience apply on every device, unlike the
       pointer effects below.

       `autoplay` is not a guarantee. It can be refused by policy, dropped if
       the element is not yet decodable, or silently suspended when the tab is
       backgrounded and then restored. Any of those leaves the hero showing a
       still poster, which is exactly the failure this hero cannot afford. So
       playback is re-asserted on every event that could have interrupted it. */
    const pace = () => { video.playbackRate = PLAYBACK_RATE; };
    const kick = () => {
      pace();
      if (video.paused && !document.hidden) video.play().catch(() => {});
    };

    pace();
    video.addEventListener("loadedmetadata", pace);
    video.addEventListener("play", pace);
    video.addEventListener("canplay", kick);
    video.addEventListener("stalled", kick);
    video.addEventListener("suspend", kick);
    document.addEventListener("visibilitychange", kick);
    if (video.readyState >= 2) kick();

    const teardownPlayback = () => {
      video.removeEventListener("loadedmetadata", pace);
      video.removeEventListener("play", pace);
      video.removeEventListener("canplay", kick);
      video.removeEventListener("stalled", kick);
      video.removeEventListener("suspend", kick);
      document.removeEventListener("visibilitychange", kick);
    };

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      video.pause();
      return teardownPlayback;
    }
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      return teardownPlayback;
    }

    // Target is where the pointer is; current is where the image has got to.
    let targetX = 0, targetY = 0, currentX = 0, currentY = 0;
    let frame = 0;

    const onMove = (event: PointerEvent) => {
      targetX = (event.clientX / window.innerWidth) * 2 - 1;
      targetY = (event.clientY / window.innerHeight) * 2 - 1;
    };

    const tick = () => {
      currentX += (targetX - currentX) * EASE;
      currentY += (targetY - currentY) * EASE;

      video.style.transform =
        `translate3d(${-currentX * DRIFT_PIXELS}px, ${-currentY * DRIFT_PIXELS}px, 0) ` +
        `rotateX(${-currentY * TILT_DEGREES}deg) rotateY(${currentX * TILT_DEGREES}deg) ` +
        `scale(1.08)`;

      if (glow) {
        const x = (currentX * 0.5 + 0.5) * 100;
        const y = (currentY * 0.5 + 0.5) * 100;
        glow.style.background =
          `radial-gradient(60% 55% at ${x}% ${y}%, rgba(206,247,158,0.10) 0%, ` +
          `rgba(206,247,158,0.03) 35%, rgba(0,0,0,0.35) 78%, rgba(0,0,0,0.6) 100%)`;
      }
      frame = requestAnimationFrame(tick);
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    frame = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("pointermove", onMove);
      teardownPlayback();
      cancelAnimationFrame(frame);
      video.style.transform = "";
    };
  }, []);

  return (
    <div className="hero__media" ref={wrap}>
      <video
        ref={media}
        poster={poster}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        aria-label="Live-cell time-lapse reconstructed into quantitative phase"
      >
        <source src={src} type="video/mp4" />
      </video>
      <div className="hero__scrim" ref={scrim} aria-hidden="true" />
    </div>
  );
}
