"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Side-by-side reconstruction viewer.
 *
 * Two layers are stacked and the top one is clipped to a draggable divider, so
 * the same pixels are compared in the same place. Toggling between two images
 * instead would make the eye do the registration, and the differences here are
 * subtle enough that it would lose.
 *
 * Pan and zoom apply to both layers through one shared transform, which is the
 * only way a wipe stays honest: if the layers could drift relative to each
 * other the comparison would be meaningless.
 */

interface Props {
  left: string;
  right: string;
  leftLabel: string;
  rightLabel: string;
  alt?: string;
}

const MIN_ZOOM = 1;
const MAX_ZOOM = 8;

export default function Viewer({ left, right, leftLabel, rightLabel, alt = "" }: Props) {
  const frame = useRef<HTMLDivElement>(null);
  const [wipe, setWipe] = useState(50);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const dragging = useRef<null | { kind: "wipe" | "pan"; x: number; y: number; ox: number; oy: number }>(null);

  const clampOffset = useCallback((next: { x: number; y: number }, scale: number) => {
    const el = frame.current;
    if (!el) return next;
    // Never let the image be dragged away from the frame: the maximum travel
    // is however much of it is hanging outside at the current zoom.
    const limitX = (el.clientWidth * (scale - 1)) / 2;
    const limitY = (el.clientHeight * (scale - 1)) / 2;
    return {
      x: Math.max(-limitX, Math.min(limitX, next.x)),
      y: Math.max(-limitY, Math.min(limitY, next.y)),
    };
  }, []);

  const onPointerDown = (event: React.PointerEvent) => {
    const el = frame.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * 100;
    const onHandle = Math.abs(px - wipe) < 3;
    dragging.current = {
      kind: onHandle || event.shiftKey ? "wipe" : "pan",
      x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y,
    };
    (event.target as Element).setPointerCapture?.(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const el = frame.current;
    const drag = dragging.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();

    if (!drag) {
      // Hovering near the divider should say so before you press.
      const px = ((event.clientX - rect.left) / rect.width) * 100;
      el.dataset.near = Math.abs(px - wipe) < 3 ? "true" : "false";
      return;
    }
    if (drag.kind === "wipe") {
      setWipe(Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100)));
    } else {
      setOffset(clampOffset({ x: drag.ox + (event.clientX - drag.x), y: drag.oy + (event.clientY - drag.y) }, zoom));
    }
  };

  const endDrag = () => { dragging.current = null; };

  const applyZoom = useCallback((factor: number) => {
    setZoom((current) => {
      const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, current * factor));
      setOffset((o) => clampOffset(o, next));
      return next;
    });
  }, [clampOffset]);

  /* Zoom on ctrl/cmd + wheel only.
     Capturing plain wheel would mean that scrolling the page with the pointer
     anywhere over this panel zooms instead of scrolling, and the panel is most
     of the viewport. Requiring the modifier also gets trackpad pinch for free,
     since browsers report pinch as a wheel event with ctrlKey set. */
  const onWheel = useCallback((event: WheelEvent) => {
    if (!event.ctrlKey && !event.metaKey) return;   // let the page scroll
    event.preventDefault();
    applyZoom(event.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, [applyZoom]);

  // Attached manually because React's onWheel is passive and cannot preventDefault.
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onWheel]);

  const transform = `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`;

  return (
    <div className="viewer">
      <div
        className="viewer__frame"
        ref={frame}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
      >
        {/* Both layers are full size and identically transformed; the top one
            is revealed with clip-path rather than being placed inside a
            narrower wrapper. A wrapper would resize the image it contains, so
            the two halves would be at different scales and the comparison
            would be a lie. */}
        <img className="viewer__layer" src={right} alt={alt} style={{ transform }} draggable={false} />
        <img
          className="viewer__layer"
          src={left}
          alt=""
          style={{ transform, clipPath: `inset(0 ${100 - wipe}% 0 0)` }}
          draggable={false}
        />

        <div className="viewer__divider" style={{ left: `${wipe}%` }} aria-hidden="true">
          <span className="viewer__handle" />
        </div>

        <span className="viewer__tag viewer__tag--left">{leftLabel}</span>
        <span className="viewer__tag viewer__tag--right">{rightLabel}</span>
        {zoom > 1.01 && <span className="viewer__zoom">{zoom.toFixed(1)}×</span>}
      </div>

      <div className="viewer__controls">
        <label className="viewer__slider">
          <span className="sr-only">Comparison position</span>
          <input
            type="range" min={0} max={100} step={0.1} value={wipe}
            onChange={(e) => setWipe(Number(e.target.value))}
            aria-label={`Wipe between ${leftLabel} and ${rightLabel}`}
          />
        </label>
        <div className="viewer__zoomers">
          <button className="viewer__reset" onClick={() => applyZoom(1 / 1.4)}
                  disabled={zoom <= MIN_ZOOM + 0.001} aria-label="Zoom out">&minus;</button>
          <button className="viewer__reset" onClick={() => applyZoom(1.4)}
                  disabled={zoom >= MAX_ZOOM - 0.001} aria-label="Zoom in">+</button>
        </div>
        <button
          className="viewer__reset"
          onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }); setWipe(50); }}
        >
          Reset view
        </button>
      </div>
      <p className="viewer__hint">
        Drag the divider to wipe, drag the image to pan, and zoom with the buttons or
        ctrl-scroll. Both panels share one transform, so the comparison stays pixel aligned
        at any magnification.
      </p>
    </div>
  );
}
