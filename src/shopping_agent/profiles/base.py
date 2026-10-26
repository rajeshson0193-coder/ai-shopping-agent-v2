"""Category profile contract.

Add a new shopping category by:
1. Creating ``profiles/<name>.py`` that builds a ``CategoryProfile``
2. Registering it in ``profiles/registry.py``

Shared pipeline stages should only call this interface — not import laptop/headphones
modules directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Pattern

from shopping_agent.models import ProductCandidate

# (value, supporting_text, reason)
SpecTriple = tuple[Any | None, str | None, str | None]
ExtractedSpecs = dict[str, SpecTriple]


@dataclass(frozen=True)
class CategoryProfile:
    """Plug-in description of one product category."""

    id: str
    priorities: tuple[str, ...]
    spec_fields: tuple[str, ...]
    accessory_terms: tuple[str, ...]
    known_retailer_domains: frozenset[str]
    manufacturer_domains: Mapping[str, tuple[str, ...]]
    listing_fixture_path: Path
    spec_fixture_path: Path
    claim_term_patterns: Mapping[str, Pattern[str]]
    accessory_reject_reason: str
    category_missing_reason: str

    matches_category: Callable[[str], bool]
    # Optional ShoppingRequest for form-factor / intent-aware query lists.
    discovery_queries: Callable[..., list[str]]
    discovery_search_query: Callable[..., str]
    extract_identity: Callable[[str], tuple[str | None, str | None, str | None]]
    looks_like_rejected_fake: Callable[[str], bool]
    # Second arg is optional listing text for CPU/platform hint ordering.
    page_hints_for_model: Callable[..., tuple[str, ...]]
    extract_specs: Callable[[str, ProductCandidate], ExtractedSpecs]
    score_page_fit: Callable[[ExtractedSpecs, ProductCandidate], int]
    apply_consistency: Callable[[ProductCandidate], Any]
    apply_fallback: Callable[[ProductCandidate, Any], Any]
    score_candidate: Callable[[ProductCandidate], tuple[int, list[str], bool]]
    extra_limitations: Callable[[bool], list[str]] = field(
        default=lambda _live: []  # type: ignore[misc]
    )
    # Return an exclusion reason when a candidate does not fit the request intent.
    request_fit: Callable[[ProductCandidate, Any], str | None] = field(
        default=lambda _candidate, _request: None  # type: ignore[misc]
    )
    # Reject single-bud / replacement-part / parts-only offers (complete products only).
    looks_like_incomplete_offer: Callable[[str], bool] = field(
        default=lambda _title: False  # type: ignore[misc]
    )
    incomplete_offer_reject_reason: str = "likely_incomplete_or_replacement_offer"

    def allowed_manufacturer_url(self, model: str, url: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        brand = (model.split(" ", 1)[0] if model else "").casefold()
        domains = self.manufacturer_domains.get(brand, ())
        host = parsed.hostname.casefold().rstrip(".")
        return any(host == domain or host.endswith("." + domain) for domain in domains)
