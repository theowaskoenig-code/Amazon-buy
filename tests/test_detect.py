"""Tests for the detection + criteria logic.

Two layers:
  * pure tests (parse_price, evaluate) — no browser needed.
  * browser tests — load the HTML fixtures in real Chromium and run inspect()+evaluate(),
    plus a checkout dry-run/live gate test. These auto-skip if Playwright/Chromium
    aren't available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autobuyer.config import Config
from autobuyer.detect import Detection, evaluate, inspect, parse_price

FIX = Path(__file__).parent / "fixtures"


def make_cfg(**over) -> Config:
    base = dict(
        product_url="https://www.amazon.de/dp/X",
        marketplace_base="https://www.amazon.de",
        expected_title_substring="Midea PortaSplit",
        required_seller="Midea",
        max_price=1199.0,
        any_color=True,
        poll_min_seconds=4.0,
        poll_max_seconds=9.0,
        dry_run=True,
        headless=True,
        user_data_dir="user_data",
    )
    base.update(over)
    return Config(**base)


# --- parse_price (pure) ----------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.199,00 €", 1199.0),       # German: dot thousands, comma decimal
        ("1.299,00 €", 1299.0),
        ("999,00 €", 999.0),               # comma decimal only
        ("€1,199.00", 1199.0),             # English: comma thousands, dot decimal
        ("1199.00", 1199.0),               # plain dot decimal
        ("1.199", 1199.0),                 # German thousands, no decimal
        ("1.234.567", 1234567.0),          # multiple dot thousands
        ("49,99 €", 49.99),
        ("", None),
        (None, None),
        ("Derzeit nicht verfügbar", None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


# --- evaluate (pure) -------------------------------------------------------

def _buyable_detection(**over) -> Detection:
    base = dict(
        title="Midea PortaSplit Klimaanlage",
        price=1199.0,
        price_text="1.199,00 €",
        seller="Midea",
        has_buy_control=True,
        availability_text="Auf Lager",
        out_of_stock_marker=False,
        captcha=False,
    )
    base.update(over)
    return Detection(**base)


def test_evaluate_buys_when_all_criteria_met():
    should, reasons = evaluate(_buyable_detection(), make_cfg())
    assert should is True


def test_evaluate_rejects_wrong_seller():
    d = _buyable_detection(seller="CoolDeals GmbH")
    should, reasons = evaluate(d, make_cfg())
    assert should is False
    assert any("seller" in r.lower() for r in reasons)


def test_evaluate_rejects_over_price():
    d = _buyable_detection(price=1299.0)
    should, reasons = evaluate(d, make_cfg())
    assert should is False
    assert any("exceeds max" in r for r in reasons)


def test_evaluate_rejects_out_of_stock():
    d = _buyable_detection(has_buy_control=False, out_of_stock_marker=True)
    should, reasons = evaluate(d, make_cfg())
    assert should is False


def test_evaluate_rejects_unknown_seller():
    d = _buyable_detection(seller="")
    should, reasons = evaluate(d, make_cfg())
    assert should is False
    assert any("seller unknown" in r for r in reasons)


def test_evaluate_rejects_unparsed_price():
    d = _buyable_detection(price=None)
    should, reasons = evaluate(d, make_cfg())
    assert should is False


def test_evaluate_captcha_short_circuits():
    d = _buyable_detection(captcha=True)
    should, reasons = evaluate(d, make_cfg())
    assert should is False
    assert any("captcha" in r.lower() for r in reasons)


def test_evaluate_seller_check_skipped_when_blank():
    d = _buyable_detection(seller="Whoever")
    should, _ = evaluate(d, make_cfg(required_seller=""))
    assert should is True


# --- browser-backed tests --------------------------------------------------

@pytest.fixture(scope="module")
def browser_page():
    pw = pytest.importorskip("playwright.sync_api")
    try:
        with pw.sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as exc:  # chromium not installed
                pytest.skip(f"chromium unavailable: {exc}")
            page = browser.new_page()
            yield page
            browser.close()
    except Exception as exc:
        pytest.skip(f"playwright unavailable: {exc}")


def _load(page, name: str):
    page.goto((FIX / name).as_uri(), wait_until="domcontentloaded")
    return page


def test_inspect_in_stock_midea_buys(browser_page):
    _load(browser_page, "in_stock_midea.html")
    d = inspect(browser_page)
    assert d.has_buy_control is True
    assert d.price == 1199.0
    assert "midea" in d.seller.lower()
    should, reasons = evaluate(d, make_cfg())
    assert should is True, reasons


def test_inspect_thirdparty_rejected(browser_page):
    _load(browser_page, "in_stock_thirdparty.html")
    d = inspect(browser_page)
    should, reasons = evaluate(d, make_cfg())
    assert should is False
    assert any("seller" in r.lower() for r in reasons)


def test_inspect_over_price_rejected(browser_page):
    _load(browser_page, "over_price.html")
    d = inspect(browser_page)
    assert d.price == 1299.0
    should, reasons = evaluate(d, make_cfg())
    assert should is False
    assert any("exceeds max" in r for r in reasons)


def test_inspect_out_of_stock_rejected(browser_page):
    _load(browser_page, "out_of_stock.html")
    d = inspect(browser_page)
    assert d.has_buy_control is False
    should, reasons = evaluate(d, make_cfg())
    assert should is False


# --- checkout dry-run / live gate -----------------------------------------

def test_place_order_dryrun_does_not_click(browser_page):
    from autobuyer import checkout

    _load(browser_page, "checkout.html")
    status = checkout.place_order(browser_page, make_cfg(dry_run=True), stamp="test")
    assert status == checkout.DRYRUN
    assert browser_page.evaluate("window.__ORDER_PLACED") is False


def test_place_order_live_clicks(browser_page):
    from autobuyer import checkout

    _load(browser_page, "checkout.html")
    status = checkout.place_order(browser_page, make_cfg(dry_run=False), stamp="test")
    assert status == checkout.PLACED
    assert browser_page.evaluate("window.__ORDER_PLACED") is True
