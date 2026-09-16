"""Verify the scroll and navigation behaviour on the live deployment."""

from playwright.sync_api import sync_playwright

SITE = "https://velos-web-production.up.railway.app"
results = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((ok, label, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # 1. Navigating away from a scrolled page lands at the top.
    page.goto(SITE, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(5000)
    page.mouse.wheel(0, 2600)
    page.wait_for_timeout(2500)
    before = page.evaluate("Math.round(window.scrollY)")
    page.click('.header__link[href="/platform"]')
    page.wait_for_url("**/platform", timeout=20_000)
    page.wait_for_timeout(2500)
    after = page.evaluate("Math.round(window.scrollY)")
    check("route change scrolls to top", after < 5, f"was {before}px, now {after}px")
    check("focus moves to main", page.evaluate("document.activeElement?.id") == "main")

    # 2. Back returns to where you were, rather than to the top. Following a
    #    link is arriving somewhere new; going back is returning somewhere you
    #    have already been, and the reader wants their position back.
    page.mouse.wheel(0, 1800)
    page.wait_for_timeout(2000)
    page.go_back()
    page.wait_for_timeout(3000)
    restored = page.evaluate("Math.round(window.scrollY)")
    check("back restores the previous position", abs(restored - before) < 120,
          f"left home at {before}px, returned to {restored}px")

    # 3. Results scroll into view, below the fixed header.
    page.goto(f"{SITE}/reconstruct", wait_until="networkidle", timeout=60_000)
    page.wait_for_selector(".sample", timeout=30_000)
    page.wait_for_timeout(1200)
    page.query_selector_all(".sample")[0].click()
    page.wait_for_selector(".viewer__frame", timeout=180_000)
    page.wait_for_timeout(3000)
    top = page.evaluate("Math.round(document.querySelector('.viewer__frame').getBoundingClientRect().top)")
    check("results scroll into view under the header", 60 <= top <= 220, f"viewer top at {top}px")

    # 4. Wheel over the viewer scrolls the page rather than zooming.
    scroll_before = page.evaluate("Math.round(window.scrollY)")
    transform_before = page.evaluate("document.querySelector('.viewer__layer').style.transform")
    page.mouse.move(700, 450)
    page.mouse.wheel(0, 500)
    page.wait_for_timeout(2000)
    scroll_after = page.evaluate("Math.round(window.scrollY)")
    transform_after = page.evaluate("document.querySelector('.viewer__layer').style.transform")
    check("viewer does not trap page scroll", scroll_after > scroll_before,
          f"{scroll_before} -> {scroll_after}")
    check("plain wheel does not zoom", transform_before == transform_after)

    # 5. Zoom buttons work.
    page.eval_on_selector(".viewer__frame", "el => el.scrollIntoView({block:'center'})")
    page.wait_for_timeout(1200)
    page.query_selector_all(".viewer__zoomers .viewer__reset")[1].click()
    page.wait_for_timeout(1000)
    check("zoom controls work", "scale(1.4" in page.evaluate("document.querySelector('.viewer__layer').style.transform"))

    # 6. Mobile: the menu closes when navigating from it.
    mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    mobile.goto(SITE, wait_until="networkidle", timeout=60_000)
    mobile.wait_for_timeout(5000)
    mobile.click(".header__toggle")
    mobile.wait_for_timeout(1500)
    opened = mobile.evaluate("document.documentElement.dataset.nav")
    mobile.click(".header__popup-link")
    mobile.wait_for_url("**/platform", timeout=20_000)
    mobile.wait_for_timeout(2500)
    check("mobile menu closes on navigation",
          opened == "open" and mobile.evaluate("document.documentElement.dataset.nav") == "closed")
    check("mobile route change scrolls to top", mobile.evaluate("Math.round(window.scrollY)") < 5)

    browser.close()

failed = [r for r in results if not r[0]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
raise SystemExit(1 if failed else 0)
