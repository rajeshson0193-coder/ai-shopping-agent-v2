"""Opt-in live smoke tests for manufacturer page-hint URLs.

Default `pytest` skips these (see conftest). Enable with:

    pytest -m live
    # or
    $env:SHOPBUDDY_LIVE = "1"; pytest -m live

Not a CI gate: manufacturer sites may 403 / geo-block / rate-limit. Those outcomes
skip the case. Hard failures are dead slugs (404) or pages that do not mention
the model — the bug unit-only URL-string tests miss.
"""

from __future__ import annotations

import pytest

from shopping_agent.http_fetch import fetch_page
from shopping_agent.profiles.headphones import MODEL_PAGE_HINTS as HEADPHONE_HINTS
from shopping_agent.profiles.headphones import page_hints_for_model as headphone_hints
from shopping_agent.profiles.laptops import MODEL_PAGE_HINTS as LAPTOP_HINTS
from shopping_agent.profiles.laptops import page_hints_for_model as laptop_hints
from shopping_agent.spec_extract import page_mentions_model

# Soft / environment outcomes — not proof the slug is wrong.
_SOFT_OUTCOMES = frozenset({"blocked", "timeout", "unreachable"})

# Display names for MODEL_PAGE_HINTS keys (page_mentions_model casefolds either way).
_HEADPHONE_MODELS = {
    "soundcore q20i": "Soundcore Q20i",
    "soundcore p30i": "Soundcore P30i",
    "soundcore space a40": "Soundcore Space A40",
    "sony wh-ch520": "Sony WH-CH520",
    "sony wf-c700n": "Sony WF-C700N",
    "jbl vibe beam 2": "JBL Vibe Beam 2",
    "jbl tune beam": "JBL Tune Beam",
    "jlab studio 2": "JLab Studio 2",
    "skullcandy sesh anc": "Skullcandy SESH ANC",
    "samsung galaxy buds fe": "Samsung Galaxy Buds FE",
    "treblab z2": "TREBLAB Z2",
}


def _allow_listed_hint_cases() -> list[tuple[str, str, str]]:
    """(category, model, url) — primary hint per headphone model, all P30i hints,
    plus a small laptop proving-query set (incl. dynamic Latitude).
    """
    cases: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(category: str, model: str, url: str) -> None:
        key = (model.casefold(), url)
        if key in seen:
            return
        seen.add(key)
        cases.append((category, model, url))

    for key, urls in HEADPHONE_HINTS.items():
        model = _HEADPHONE_MODELS[key]
        add("headphones", model, urls[0])

    # Dead-slug regression target: every configured P30i URL, not only the primary.
    p30i = "Soundcore P30i"
    for url in HEADPHONE_HINTS["soundcore p30i"]:
        add("headphones", p30i, url)

    laptop_primaries = (
        "Lenovo IdeaPad Slim 3",
        "Dell Inspiron 15 3530",
        "HP Pavilion 15",
    )
    for model in laptop_primaries:
        urls = laptop_hints(model)
        assert urls, f"expected static hints for {model}"
        add("laptop", model, urls[0])

    # Dynamic Dell Latitude hints (unit tests only check URL strings today).
    latitude = "Dell Latitude 3500"
    lat_urls = laptop_hints(latitude)
    assert lat_urls
    add("laptop", latitude, lat_urls[0])

    return cases


LIVE_HINT_CASES = _allow_listed_hint_cases()


def test_live_hint_allow_list_matches_profile_hints():
    """Keep the smoke allow-list honest without hitting the network."""
    for category, model, url in LIVE_HINT_CASES:
        if category == "headphones":
            hints = headphone_hints(model)
        else:
            hints = laptop_hints(model)
        assert url in hints, f"{model}: allow-listed URL not in page_hints_for_model()\n{url}"


def test_live_hint_allow_list_covers_every_headphone_primary():
    primaries = {urls[0] for urls in HEADPHONE_HINTS.values()}
    covered = {url for category, _, url in LIVE_HINT_CASES if category == "headphones"}
    missing = primaries - covered
    assert not missing, f"headphone primary hints missing from live allow-list: {missing}"


@pytest.mark.live
@pytest.mark.parametrize(
    "category,model,url",
    LIVE_HINT_CASES,
    ids=[f"{c}:{m}:{u.split('://', 1)[-1][:60]}" for c, m, u in LIVE_HINT_CASES],
)
def test_live_page_hint_reachable_and_mentions_model(category: str, model: str, url: str):
    del category  # used in parametrize id / allow-list only
    page = fetch_page(url, timeout=20)

    if page.outcome in _SOFT_OUTCOMES:
        pytest.skip(f"{page.outcome}: {page.reason} ({url})")

    assert page.outcome == "ok", (
        f"page-hint not reachable for {model}: outcome={page.outcome!r} "
        f"status={page.status_code!r} reason={page.reason!r}\n{url}"
    )
    assert page.text.strip(), f"empty page text for {model}: {url}"
    assert page_mentions_model(page.text, model), (
        f"page retrieved but does not mention {model!r}: {url}"
    )


def test_laptop_static_hint_keys_stay_https():
    """Fast guardrail next to live smokes; no network."""
    for model_key, urls in LAPTOP_HINTS.items():
        assert urls, model_key
        assert all(u.startswith("https://") for u in urls), model_key
