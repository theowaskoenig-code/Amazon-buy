"""Detection logic: read the product page and decide whether to buy.

Split into three pieces so the decision is easy to unit-test:

* ``parse_price``  — pure string -> float, handles German + English number formats.
* ``inspect``      — reads the live Playwright page into a ``Detection`` snapshot.
* ``evaluate``     — pure: given a ``Detection`` + ``Config``, returns (should_buy, reasons).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import selectors


@dataclass
class Detection:
    """A snapshot of what we observed on the product page."""

    title: str = ""
    price: float | None = None
    price_text: str = ""
    seller: str = ""
    has_buy_control: bool = False
    availability_text: str = ""
    out_of_stock_marker: bool = False
    captcha: bool = False
    notes: list[str] = field(default_factory=list)


def parse_price(text: str | None) -> float | None:
    """Parse a price string into a float.

    Handles German ("1.199,00 €" -> 1199.0) and English ("€1,199.00") formats by
    treating the right-most '.' or ',' as the decimal separator and the other as a
    thousands separator. Returns None if no number is found.
    """
    if not text:
        return None

    # Keep only digits and separators.
    cleaned = re.sub(r"[^0-9.,]", "", text)
    if not cleaned:
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        # The right-most separator is the decimal point; the other is thousands.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        # Comma only: decimal if a single comma with exactly two trailing digits,
        # else it's a thousands separator.
        if cleaned.count(",") == 1 and re.search(r",\d{2}$", cleaned):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_dot:
        # Dot only: decimal if a single dot with exactly two trailing digits
        # (e.g. "1199.00"); otherwise thousands (e.g. German "1.199", "1.234.567").
        if not (cleaned.count(".") == 1 and re.search(r"\.\d{2}$", cleaned)):
            cleaned = cleaned.replace(".", "")
    # digits-only: leave as-is.

    try:
        return float(cleaned)
    except ValueError:
        return None


def _text_or_empty(page, selector: str) -> str:
    """Return inner_text of the first matching element, or '' if none/timeout."""
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            return ""
        return (loc.inner_text(timeout=2000) or "").strip()
    except Exception:
        return ""


def _extract_seller(merchant_text: str) -> str:
    """Pull the merchant name out of a 'Sold by / Verkauf durch X' blob."""
    low = merchant_text.lower()
    for prefix in selectors.SOLD_BY_PREFIXES:
        idx = low.find(prefix)
        if idx == -1:
            continue
        tail = merchant_text[idx + len(prefix):].strip(" :\n\t")
        # Take the first line / up to a separator.
        tail = re.split(r"[\n\r]|  +|•", tail)[0].strip()
        if tail:
            return tail
    return ""


def inspect(page) -> Detection:
    """Read the current product page into a Detection snapshot.

    Never raises on missing elements — absent fields stay at their defaults so
    ``evaluate`` can make a safe (no-buy) decision.
    """
    d = Detection()

    # CAPTCHA / bot-check first — if present nothing else is trustworthy.
    try:
        body = (page.content() or "").lower()
    except Exception:
        body = ""
    url = ""
    try:
        url = (page.url or "").lower()
    except Exception:
        pass
    if any(m in body or m in url for m in selectors.CAPTCHA_MARKERS):
        d.captcha = True
        d.notes.append("captcha/bot-check page detected")
        return d

    d.title = _text_or_empty(page, selectors.PRODUCT_TITLE)

    d.price_text = _text_or_empty(page, selectors.PRICE_OFFSCREEN)
    if not d.price_text:
        d.price_text = _text_or_empty(page, selectors.PRICE_WHOLE)
    d.price = parse_price(d.price_text)

    seller_text = _text_or_empty(page, selectors.SELLER_LINK)
    if not seller_text:
        merchant = _text_or_empty(page, selectors.MERCHANT_INFO)
        seller_text = _extract_seller(merchant)
    d.seller = seller_text

    try:
        buy = page.locator(selectors.BUY_NOW_BUTTON).first
        cart = page.locator(selectors.ADD_TO_CART_BUTTON).first
        d.has_buy_control = bool(buy.count()) or bool(cart.count())
    except Exception:
        d.has_buy_control = False

    d.availability_text = _text_or_empty(page, selectors.AVAILABILITY)
    low_avail = d.availability_text.lower()
    d.out_of_stock_marker = any(m in low_avail for m in selectors.OUT_OF_STOCK_MARKERS)
    # Also catch out-of-stock text rendered outside #availability.
    if not d.out_of_stock_marker and not d.has_buy_control:
        d.out_of_stock_marker = any(m in body for m in selectors.OUT_OF_STOCK_MARKERS)

    return d


def evaluate(d: Detection, cfg) -> tuple[bool, list[str]]:
    """Pure decision: should we buy this snapshot? Returns (should_buy, reasons).

    `reasons` always explains the verdict (why-not when False, the passing
    criteria when True).
    """
    reasons: list[str] = []

    if d.captcha:
        return False, ["captcha/bot-check — cannot evaluate, human needed"]

    if not d.has_buy_control:
        reasons.append("no Buy-Now/Add-to-Cart control present")
    if d.out_of_stock_marker:
        reasons.append(f"out-of-stock marker present (availability: {d.availability_text!r})")

    # Title sanity-check.
    want_title = (cfg.expected_title_substring or "").strip().lower()
    if want_title and want_title not in d.title.lower():
        reasons.append(
            f"title {d.title!r} does not contain expected {cfg.expected_title_substring!r}"
        )

    # Seller check.
    want_seller = (cfg.required_seller or "").strip().lower()
    if want_seller:
        if not d.seller:
            reasons.append("seller unknown (could not read merchant) — refusing to buy")
        elif want_seller not in d.seller.lower():
            reasons.append(
                f"seller {d.seller!r} does not match required {cfg.required_seller!r}"
            )

    # Price check.
    if d.price is None:
        reasons.append("price could not be parsed — refusing to buy")
    elif d.price > cfg.max_price:
        reasons.append(f"price {d.price:.2f} exceeds max {cfg.max_price:.2f}")

    if reasons:
        return False, reasons

    ok = [
        "buyable control present",
        "in stock",
        f"price {d.price:.2f} <= {cfg.max_price:.2f}",
    ]
    if want_seller:
        ok.append(f"seller {d.seller!r} matches {cfg.required_seller!r}")
    if want_title:
        ok.append("title matches")
    return True, ok
