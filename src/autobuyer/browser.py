"""Browser lifecycle: a persistent, logged-in Chromium context via Playwright.

We use ``launch_persistent_context`` with a user-data dir so the Amazon login
(including any 2FA) is done once and reused across runs — no cookie juggling.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import notify
from .config import Config

# A normal-looking macOS desktop UA (the user runs this on a Mac mini).
# Headless-detection is reduced further by running headed (headless: false).
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@contextmanager
def browser_context(cfg: Config):
    """Yield a logged-in (persistent) Playwright browser context.

    Usage:
        with browser_context(cfg) as ctx:
            page = ctx.new_page()
            ...
    """
    user_data = Path(cfg.user_data_dir)
    user_data.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=cfg.headless,
            user_agent=_USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="de-DE",
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            yield ctx
        finally:
            ctx.close()


def login(cfg: Config) -> None:
    """Open Amazon so the user can log in once; the session persists on disk."""
    notify.info(
        f"Opening {cfg.marketplace_base} — log in (and pass any 2FA) in the window, "
        f"then come back here and press Enter."
    )
    # Force headed for login regardless of config, so the user can actually type.
    forced = Config(**{**cfg.__dict__, "headless": False})
    with browser_context(forced) as ctx:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg.marketplace_base, wait_until="domcontentloaded")
        try:
            input("Press Enter once you are fully logged in... ")
        except (EOFError, KeyboardInterrupt):
            pass
    notify.success(
        f"Login session saved to '{cfg.user_data_dir}/'. You won't need to log in again "
        f"unless Amazon expires the session."
    )
