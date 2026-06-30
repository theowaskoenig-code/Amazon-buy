"""Load and validate config.yaml into a typed Config object."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Config:
    product_url: str
    marketplace_base: str
    expected_title_substring: str
    required_seller: str
    max_price: float
    any_color: bool
    poll_min_seconds: float
    poll_max_seconds: float
    dry_run: bool
    headless: bool
    user_data_dir: str

    @property
    def user_data_path(self) -> Path:
        return Path(self.user_data_dir).expanduser().resolve()


_DEFAULTS = {
    "marketplace_base": "https://www.amazon.de",
    "expected_title_substring": "",
    "required_seller": "",
    "any_color": True,
    "poll_min_seconds": 4.0,
    "poll_max_seconds": 9.0,
    "dry_run": True,
    "headless": False,
    "user_data_dir": "user_data",
}


def load_config(path: str | Path = "config.yaml") -> Config:
    """Read ``path`` (YAML), apply defaults, validate, return a Config.

    Raises FileNotFoundError if the file is missing and ValueError on bad values.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Config file '{p}' not found. Copy config.example.yaml to config.yaml "
            f"and fill it in."
        )

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file '{p}' must contain a YAML mapping.")

    merged = {**_DEFAULTS, **raw}

    if not merged.get("product_url"):
        raise ValueError("config: 'product_url' is required.")
    if "REPLACE_WITH_ASIN" in str(merged["product_url"]):
        raise ValueError(
            "config: 'product_url' still has the placeholder — paste the real product URL."
        )

    try:
        cfg = Config(
            product_url=str(merged["product_url"]),
            marketplace_base=str(merged["marketplace_base"]),
            expected_title_substring=str(merged["expected_title_substring"]),
            required_seller=str(merged["required_seller"]),
            max_price=float(merged["max_price"]),
            any_color=bool(merged["any_color"]),
            poll_min_seconds=float(merged["poll_min_seconds"]),
            poll_max_seconds=float(merged["poll_max_seconds"]),
            dry_run=bool(merged["dry_run"]),
            headless=bool(merged["headless"]),
            user_data_dir=str(merged["user_data_dir"]),
        )
    except KeyError as exc:
        raise ValueError(f"config: missing required key {exc}") from exc

    if cfg.max_price <= 0:
        raise ValueError("config: 'max_price' must be greater than 0.")
    if cfg.poll_min_seconds <= 0 or cfg.poll_max_seconds <= 0:
        raise ValueError("config: poll intervals must be greater than 0.")
    if cfg.poll_max_seconds < cfg.poll_min_seconds:
        raise ValueError("config: 'poll_max_seconds' must be >= 'poll_min_seconds'.")

    return cfg
