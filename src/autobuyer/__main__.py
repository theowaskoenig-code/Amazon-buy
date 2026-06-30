"""Command-line entry point.

    python -m autobuyer login        # log in to Amazon once (session persists)
    python -m autobuyer check        # one-shot: report current page state + verdict
    python -m autobuyer run          # watch the page and auto-checkout when buyable

Add --config PATH to use a config file other than ./config.yaml.
"""

from __future__ import annotations

import argparse
import sys

from . import notify
from .config import load_config


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        default="config.yaml",
        help="path to the config file (default: config.yaml)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autobuyer",
        description="Watch an Amazon product page and auto-checkout when it's buyable.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="open Amazon to log in once; session persists")
    _add_config_arg(p_login)

    p_check = sub.add_parser("check", help="one-shot status + buy/no-buy verdict")
    _add_config_arg(p_check)

    p_run = sub.add_parser("run", help="watch the page and auto-checkout when buyable")
    _add_config_arg(p_run)
    p_run.add_argument(
        "--live",
        action="store_true",
        help="override config and place a REAL order (disables dry-run)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        notify.error(str(exc))
        return 2

    # Imports deferred so `--help` works without Playwright installed.
    if args.command == "login":
        from .browser import login

        login(cfg)
        return 0

    if args.command == "check":
        from .monitor import check_once

        check_once(cfg)
        return 0

    if args.command == "run":
        from dataclasses import replace

        from .monitor import run

        if getattr(args, "live", False):
            cfg = replace(cfg, dry_run=False)
        if not cfg.dry_run:
            notify.warn(
                "LIVE mode: this WILL place a real order when criteria are met. "
                "Make sure max_price and required_seller are correct."
            )
        try:
            run(cfg)
        except KeyboardInterrupt:
            notify.info("\nStopped by user.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
