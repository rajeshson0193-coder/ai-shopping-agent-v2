"""Run parse → discover → identify → research → validate → rank."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from shopping_agent.discover import discover_products
from shopping_agent.http_fetch import fetch_page
from shopping_agent.identify import identify_candidates
from shopping_agent.models import PipelineResult, ShoppingRequest
from shopping_agent.parse import parse_request
from shopping_agent.profiles.registry import get_profile, supported_category_ids
from shopping_agent.rank import limitations, rank_candidates
from shopping_agent.research import research_candidates
from shopping_agent.validate import validate_candidates

ProgressCallback = Callable[[str], None]


def run_research(
    text: str,
    *,
    limit: int = 5,
    max_results_per_source: int = 20,
    timeout: int = 30,
    use_fixtures: bool = True,
    live: bool = False,
    page_fetch=None,
    budget: Decimal | None = None,
    skip_serpapi: bool = False,
    serpapi_max_calls: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    def progress(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    progress("Parsing your request…")
    request: ShoppingRequest = parse_request(text, budget=budget)
    try:
        profile = get_profile(request.category)
    except KeyError as exc:
        supported = ", ".join(supported_category_ids())
        raise ValueError(
            f"Unsupported category {request.category!r}. "
            f"Registered profiles: {supported}."
        ) from exc

    progress(f"Using budget ${request.budget} USD ({request.category})…")

    if live:
        progress("Searching live listings…")
    else:
        progress("Loading local listing fixtures…")
    discovery = discover_products(
        request,
        profile=profile,
        max_results_per_source=max_results_per_source,
        timeout=timeout,
        use_fixtures=use_fixtures,
        live=live,
        skip_serpapi=skip_serpapi,
        serpapi_max_calls=serpapi_max_calls,
    )
    progress("Identifying product models…")
    identified = identify_candidates(discovery.candidates, profile=profile)
    fetch = page_fetch or fetch_page
    # Manufacturer / retailer page fetches should fail fast; discovery can keep
    # the wider pipeline timeout for marketplace APIs.
    page_timeout = min(int(timeout), 12)
    if live:
        progress("Checking manufacturer pages…")
    else:
        progress("Loading manufacturer spec fixtures…")
    researched = research_candidates(
        identified, profile=profile, live=live, timeout=page_timeout, fetch=fetch
    )
    progress("Validating evidence…")
    validated = validate_candidates(
        researched, profile=profile, live=live, timeout=page_timeout, fetch=fetch
    )
    progress("Ranking the shortlist…")
    ranking = rank_candidates(request, validated, profile=profile, limit=limit)

    return PipelineResult(
        request=request,
        recommendations=ranking.ranked,
        excluded=ranking.excluded,
        duplicate_offers=ranking.duplicate_offers,
        source_errors=discovery.source_errors,
        limitations=limitations(profile, live=live),
        stages_run=[
            "parse",
            "discover",
            "identify",
            "research",
            "validate",
            "rank",
        ],
    )
