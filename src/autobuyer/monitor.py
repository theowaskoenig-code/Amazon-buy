"""The watch loop: reload the product page, detect, and buy when criteria match."""

from __future__ import annotations

import random
import time

from . import checkout, notify
from .browser import browser_context
from .config import Config
from .detect import evaluate, inspect


def _wait_for_human(page) -> None:
    """Pause on a CAPTCHA / 2FA wall until the user has cleared it."""
    notify.alert(
        "ACTION NEEDED",
        "Amazon is showing a CAPTCHA or bot-check. Solve it in the browser window, "
        "then return here and press Enter to resume watching.",
    )
    try:
        input("Press Enter once the page is back to normal... ")
    except (EOFError, KeyboardInterrupt):
        pass


def _try_color_variants(page, cfg: Config, stamp: str) -> str | None:
    """If the current variant isn't buyable, try other colour swatches.

    Returns a checkout status (PLACED/DRYRUN/FAILED) if a variant was acted on,
    else None.
    """
    from . import selectors

    try:
        swatches = page.locator(selectors.COLOR_SWATCHES)
        count = swatches.count()
    except Exception:
        return None
    if count <= 1:
        return None

    for i in range(count):
        try:
            swatches.nth(i).click(timeout=4000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(0.8)
        except Exception:
            continue
        d = inspect(page)
        should, reasons = evaluate(d, cfg)
        if should:
            notify.success(f"matching colour variant #{i + 1} is buyable — buying")
            return checkout.buy_now(page, cfg, stamp=f"{stamp}-variant{i + 1}")
    return None


def check_once(cfg: Config) -> None:
    """One-shot: report the current state of the product page and exit."""
    with browser_context(cfg) as ctx:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg.product_url, wait_until="domcontentloaded", timeout=30000)
        d = inspect(page)
        should, reasons = evaluate(d, cfg)
        notify.log(f"title:   {d.title or '(none)'}")
        notify.log(f"price:   {d.price if d.price is not None else '(unparsed)'}  ({d.price_text!r})")
        notify.log(f"seller:  {d.seller or '(unknown)'}")
        notify.log(f"buyable control: {d.has_buy_control}   out-of-stock marker: {d.out_of_stock_marker}")
        if should:
            notify.success("VERDICT: would buy — " + "; ".join(reasons))
        else:
            notify.warn("VERDICT: would NOT buy — " + "; ".join(reasons))


def run(cfg: Config) -> None:
    """Watch the product page until it's buyable, then check out."""
    mode = "DRY RUN (no real purchase)" if cfg.dry_run else "LIVE (will place a real order)"
    notify.log(f"[bold]Watching[/bold] {cfg.product_url}")
    notify.log(f"Mode: [bold]{mode}[/bold]  ·  max €{cfg.max_price:.2f}  ·  seller~{cfg.required_seller or 'any'}")
    notify.info("Press Ctrl+C to stop.\n")

    with browser_context(cfg) as ctx:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        round_no = 0
        consecutive_errors = 0

        while True:
            round_no += 1
            try:
                page.goto(cfg.product_url, wait_until="domcontentloaded", timeout=30000)
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                backoff = min(60, 2 ** consecutive_errors)
                notify.warn(f"[{round_no}] load failed ({exc}); backing off {backoff}s")
                time.sleep(backoff)
                continue

            d = inspect(page)
            if d.captcha:
                _wait_for_human(page)
                continue

            should, reasons = evaluate(d, cfg)
            if should:
                notify.alert("IN STOCK", f"{d.title}\nprice {d.price} · seller {d.seller}")
                status = checkout.buy_now(page, cfg, stamp=f"buy-r{round_no}")
            else:
                status = None
                if cfg.any_color:
                    status = _try_color_variants(page, cfg, stamp=f"buy-r{round_no}")
                if status is None:
                    notify.info(f"[{round_no}] not buyable: {'; '.join(reasons)}")

            if status == checkout.PLACED:
                notify.success("Purchase complete. Stopping.")
                return
            if status == checkout.DRYRUN:
                notify.success(
                    "Dry-run reached the checkout review screen successfully. "
                    "Flip 'dry_run: false' in config.yaml to buy for real. Stopping."
                )
                return
            if status == checkout.FAILED:
                notify.warn("checkout attempt failed — staying in the watch loop")

            delay = random.uniform(cfg.poll_min_seconds, cfg.poll_max_seconds)
            time.sleep(delay)
