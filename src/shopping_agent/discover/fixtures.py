"""Load local discovery fixtures so the pipeline runs without API keys."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from shopping_agent.models import (
    Evidence,
    ProductCandidate,
    ShoppingRequest,
    VerificationStatus,
    utc_now,
)
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile


def _status(value: str | None) -> VerificationStatus:
    if not value:
        return VerificationStatus.UNKNOWN
    try:
        return VerificationStatus(value)
    except ValueError:
        return VerificationStatus.UNKNOWN


def load_fixture_listings(
    request: ShoppingRequest,
    profile: CategoryProfile | None = None,
) -> list[ProductCandidate]:
    if profile is None:
        profile = get_profile(request.category)
    fixture_path = profile.listing_fixture_path
    if not fixture_path.is_file():
        raise FileNotFoundError(f"Discovery fixture not found: {fixture_path}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    listings = payload.get("listings", [])
    retrieved_at = utc_now()
    candidates: list[ProductCandidate] = []

    for item in listings:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("product_url", "")).strip()
        if not name or not url.startswith("https://"):
            continue

        price = None
        raw_price = item.get("listed_price")
        if raw_price not in (None, ""):
            try:
                parsed = Decimal(str(raw_price))
            except (InvalidOperation, ValueError):
                parsed = None
            if parsed is not None and parsed.is_finite() and parsed >= 0:
                price = parsed

        price_status = _status(item.get("price_status"))
        condition_status = _status(item.get("condition_status"))
        condition = item.get("condition") if isinstance(item.get("condition"), str) else None

        evidence = [
            Evidence(
                field_name="discovery",
                status=VerificationStatus.VERIFIED,
                value=name,
                source_url=url,
                source_type="fixture_listing",
                supporting_text=f"Fixture listing title: {name}",
                retrieved_at=retrieved_at,
            )
        ]
        if price is not None:
            evidence.append(
                Evidence(
                    field_name="listed_price",
                    status=price_status,
                    value=price,
                    source_url=url,
                    source_type="fixture_listing_price",
                    supporting_text=(
                        f"Fixture reports {price} {item.get('currency', 'USD')} as the listed item price. "
                        "Shipping and tax are not included."
                    ),
                    retrieved_at=retrieved_at,
                )
            )
        if condition:
            evidence.append(
                Evidence(
                    field_name="condition",
                    status=condition_status,
                    value=condition,
                    source_url=url,
                    source_type="fixture_listing_condition",
                    supporting_text=f"Fixture listing condition: {condition}",
                    retrieved_at=retrieved_at,
                )
            )

        candidates.append(
            ProductCandidate(
                name=name,
                product_url=url,
                source=str(item.get("source", "fixture")),
                listed_price=price,
                currency=str(item.get("currency", request.currency)),
                price_status=price_status,
                condition=condition,
                condition_status=condition_status,
                evidence=evidence,
            )
        )
    return candidates
