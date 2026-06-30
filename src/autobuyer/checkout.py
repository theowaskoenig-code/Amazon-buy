"""Checkout flow: click Buy Now and place the order (gated by dry-run).

The dry-run gate is the single most important safety mechanism here: in dry-run
we navigate all the way to the order-review screen and then STOP, logging
"WOULD place order" without ever clicking the final button.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import notify, selectors

SCREENSHOT_DIR = Path("screenshots")


def _page_of(root):
    """Return the owning Page for a Page-or-Frame locator root."""
    return getattr(root, "page", root)


def _screenshot(page, name: str) -> str | None:
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / name
        page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception as exc:  # screenshots are best-effort
        notify.warn(f"could not save screenshot {name}: {exc}")
        return None


def _checkout_root(page):
    """Return where the place-order button lives: the turbo iframe, or the page."""
    try:
        frame_el = page.locator(selectors.TURBO_CHECKOUT_IFRAME).first
        if frame_el.count():
            frame = frame_el.content_frame()
            if frame is not None:
                return frame
    except Exception:
        pass
    return page


# Checkout outcomes.
PLACED = "placed"  # a real order was placed
DRYRUN = "dryrun"  # reached the review screen, did NOT click (dry_run: true)
FAILED = "failed"  # could not complete the flow


def place_order(root, cfg, stamp: str = "order") -> str:
    """Find the place-order button and click it — unless dry-run.

    Returns one of PLACED / DRYRUN / FAILED.
    """
    page = _page_of(root)
    try:
        button = root.locator(selectors.PLACE_ORDER_BUTTONS).first
        button.wait_for(state="visible", timeout=15000)
    except Exception as exc:
        notify.error(f"place-order button not found: {exc}")
        _screenshot(page, f"{stamp}-no-place-order-button.png")
        return FAILED

    if cfg.dry_run:
        notify.warn(
            "DRY RUN — reached the order-review screen and found the 'Place order' "
            "button. WOULD place the order now. Not clicking (dry_run: true)."
        )
        _screenshot(page, f"{stamp}-dryrun-review.png")
        return DRYRUN

    notify.info("Placing the order...")
    button.click()
    # Give Amazon a moment to record the order and render confirmation.
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        time.sleep(3)

    shot = _screenshot(page, f"{stamp}-confirmation.png")
    notify.success("ORDER PLACED.")
    if shot:
        notify.info(f"Confirmation screenshot: {shot}")
    return PLACED


def buy_now(page, cfg, stamp: str = "order") -> str:
    """Run the Buy-Now -> Place-Order flow on a product page.

    Returns one of PLACED / DRYRUN / FAILED.
    """
    # Prefer the one-click "Buy Now" button; fall back to Add-to-Cart.
    clicked = False
    for sel in (selectors.BUY_NOW_BUTTON, selectors.ADD_TO_CART_BUTTON):
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.click(timeout=8000)
                clicked = True
                break
        except Exception as exc:
            notify.warn(f"could not click {sel}: {exc}")

    if not clicked:
        notify.error("no Buy-Now / Add-to-Cart button to click")
        return FAILED

    # Let the turbo checkout iframe (or full checkout page) load.
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    time.sleep(1.0)

    root = _checkout_root(page)
    return place_order(root, cfg, stamp=stamp)
