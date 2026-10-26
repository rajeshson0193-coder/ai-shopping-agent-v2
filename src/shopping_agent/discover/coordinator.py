"""Run discovery sources independently and keep going if one source fails."""

from __future__ import annotations

from dataclasses import dataclass, field

from shopping_agent.discover import ebay, serpapi
from shopping_agent.discover.fixtures import load_fixture_listings
from shopping_agent.models import ProductCandidate, ShoppingRequest
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile


@dataclass
class DiscoveryResult:
    candidates: list[ProductCandidate] = field(default_factory=list)
    source_errors: dict[str, str] = field(default_factory=dict)
    sources_used: list[str] = field(default_factory=list)


def _merge_same_url(existing: ProductCandidate, incoming: ProductCandidate) -> None:
    existing.evidence.extend(incoming.evidence)
    if existing.listed_price is None and incoming.listed_price is not None:
        existing.listed_price = incoming.listed_price
        existing.currency = incoming.currency
        existing.price_status = incoming.price_status
        existing.source = incoming.source
    if existing.condition is None and incoming.condition:
        existing.condition = incoming.condition
        existing.condition_status = incoming.condition_status


def discover_products(
    request: ShoppingRequest,
    max_results_per_source: int = 10,
    timeout: int = 30,
    use_fixtures: bool = True,
    live: bool = False,
    skip_serpapi: bool = False,
    profile: CategoryProfile | None = None,
    serpapi_max_calls: int | None = None,
) -> DiscoveryResult:
    if profile is None:
        profile = get_profile(request.category)

    result = DiscoveryResult()
    ordered: list[ProductCandidate] = []
    by_url_map: dict[str, ProductCandidate] = {}

    # eBay is the primary live source; SerpApi is a small quota-capped supplement.
    if use_fixtures:
        try:
            found = load_fixture_listings(request, profile=profile)
            result.sources_used.append("fixtures")
            for candidate in found:
                existing = by_url_map.get(candidate.product_url)
                if existing is None:
                    by_url_map[candidate.product_url] = candidate
                    ordered.append(candidate)
                else:
                    _merge_same_url(existing, candidate)
        except Exception as exc:  # noqa: BLE001
            result.source_errors["fixtures"] = str(exc)

    if live:
        if ebay.credentials_configured():
            try:
                found = ebay.search_products(
                    request,
                    profile=profile,
                    max_results=max_results_per_source,
                    timeout=timeout,
                )
                result.sources_used.append("ebay")
                for candidate in found:
                    existing = by_url_map.get(candidate.product_url)
                    if existing is None:
                        by_url_map[candidate.product_url] = candidate
                        ordered.append(candidate)
                    else:
                        _merge_same_url(existing, candidate)
            except Exception as exc:  # noqa: BLE001
                result.source_errors["ebay"] = str(exc)
        else:
            result.source_errors["ebay"] = "credentials_not_configured"

        if skip_serpapi:
            result.source_errors["serpapi"] = "skipped_to_preserve_monthly_quota"
        elif serpapi.credentials_configured():
            shopping, detail, total = serpapi.allocate_call_budget(serpapi_max_calls)
            # Ask SerpApi for at most as many offers as remaining detail slots.
            serpapi_limit = min(max_results_per_source, max(detail, 0))
            if total <= 0 or shopping <= 0 or serpapi_limit <= 0:
                result.source_errors["serpapi"] = (
                    f"disabled_by_call_budget(total={total}, shopping={shopping}, detail={detail})"
                )
            else:
                try:
                    found = serpapi.search_products(
                        request,
                        profile=profile,
                        max_results=serpapi_limit,
                        timeout=timeout,
                        max_calls_override=serpapi_max_calls,
                    )
                    result.sources_used.append("serpapi")
                    result.source_errors["serpapi_quota"] = (
                        f"budgeted_{total}_calls_split_{shopping}_shopping_{detail}_detail"
                    )
                    for candidate in found:
                        existing = by_url_map.get(candidate.product_url)
                        if existing is None:
                            by_url_map[candidate.product_url] = candidate
                            ordered.append(candidate)
                        else:
                            _merge_same_url(existing, candidate)
                except Exception as exc:  # noqa: BLE001
                    result.source_errors["serpapi"] = str(exc)
        else:
            result.source_errors["serpapi"] = "credentials_not_configured"

    if not result.sources_used and not use_fixtures and not live:
        raise RuntimeError(
            "No discovery sources available. Use fixtures (default) or set API keys with --live."
        )
    if not result.sources_used:
        raise RuntimeError(
            "No discovery sources available. Use fixtures (default) or set API keys with --live."
        )

    result.candidates = ordered
    return result
