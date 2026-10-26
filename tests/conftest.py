"""Shared pytest hooks. Live network smokes stay off unless explicitly enabled."""

from __future__ import annotations

import os
import re

import pytest


def _live_requested(config: pytest.Config) -> bool:
    flag = os.environ.get("SHOPBUDDY_LIVE", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    markexpr = (getattr(config.option, "markexpr", None) or "").strip()
    if not markexpr:
        return False
    # README: `pytest -m live`. Also allow `live and …` style expressions.
    normalized = re.sub(r"\s+", " ", markexpr.casefold())
    if normalized == "live":
        return True
    if re.search(r"(^| )\bnot\s+live\b", normalized):
        return False
    return bool(re.search(r"(^| )\blive\b", normalized))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: opt-in network smoke tests (pytest -m live or SHOPBUDDY_LIVE=1)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _live_requested(config):
        return
    skip_live = pytest.mark.skip(
        reason="live smoke tests off by default (enable with: pytest -m live  or  SHOPBUDDY_LIVE=1)"
    )
    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(skip_live)
