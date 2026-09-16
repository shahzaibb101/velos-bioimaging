"""Capture the live deployment for the proposal.

Drives the real site at its public URL, including running an actual
reconstruction job, so every frame is the deployed product rather than a
local build or a mockup.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "https://velos-web-production.up.railway.app"
OUT = Path.home() / "Downloads" / "velos-bioimaging-screenshots"
VIEWPORT = {"width": 1600, "height": 1000}


def settle(page, seconds: float = 1.2) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def shot(page, name: str, note: str) -> None:
    path = OUT / name
    page.screenshot(path=str(path))
    size = path.stat().st_size / 1000
    print(f"  {name:<44} {size:6.0f} KB   {note}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)

        # --- 1. Hero -------------------------------------------------------
        page.goto(SITE, wait_until="networkidle", timeout=60_000)
        # The hero opens over 2.3s and the headline reveals at 1.6s; wait past
        # both so the capture is the settled state, not a half-played frame.
        settle(page, 5)
        shot(page, "01-hero.png", "homepage hero, live reconstruction playing behind")

        # --- 2. Capability cards ------------------------------------------
        page.mouse.wheel(0, 4800)
        settle(page, 2.5)
        page.mouse.wheel(0, 900)
        settle(page, 2.5)
        shot(page, "02-capabilities.png", "what the pipeline does, three stages")

        # --- 3. Platform page ---------------------------------------------
        page.goto(f"{SITE}/platform", wait_until="networkidle", timeout=60_000)
        settle(page, 3)
        shot(page, "03-platform.png", "platform page, the physics explained")

        # --- 4. App, before a run ------------------------------------------
        page.goto(f"{SITE}/reconstruct", wait_until="networkidle", timeout=60_000)
        page.wait_for_selector(".sample", timeout=30_000)
        settle(page, 1.5)
        shot(page, "04-app-acquisitions.png", "reconstruction app, sample acquisitions")

        # --- 5. Job running -------------------------------------------------
        page.query_selector_all(".sample")[0].click()
        page.wait_for_selector(".progress", timeout=20_000)
        settle(page, 1.2)
        shot(page, "05-app-running.png", "job queued and running, live progress")

        # --- 6. The comparison viewer ---------------------------------------
        page.wait_for_selector(".viewer", timeout=180_000)
        settle(page, 3)
        page.mouse.wheel(0, 620)
        settle(page, 1.5)
        shot(page, "06-app-viewer.png", "raw camera vs reconstruction, wipe comparison")

        # --- 7. Disagreement layer -------------------------------------------
        for button in page.query_selector_all(".app__layerpick:first-child .chip"):
            if "Model minus physics" in (button.inner_text() or ""):
                button.click()
                break
        settle(page, 2)
        shot(page, "07-app-disagreement.png", "where the model departs from the physics")

        # --- 8. Scores and per-cell measurements ------------------------------
        page.mouse.wheel(0, 900)
        settle(page, 2)
        shot(page, "08-app-scorecard.png", "three methods scored against ground truth")

        page.mouse.wheel(0, 700)
        settle(page, 1.5)
        shot(page, "09-app-cells.png", "per-cell dry mass table and exports")

        browser.close()


if __name__ == "__main__":
    print(f"capturing {SITE}\n")
    started = time.perf_counter()
    main()
    print(f"\nwrote to {OUT}  ({time.perf_counter()-started:.0f}s)")
