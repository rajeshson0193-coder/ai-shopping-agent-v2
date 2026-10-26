"""Deterministic eligibility and scoring. Unknown specs are neutral, not negative."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from shopping_agent.models import (
    ProductCandidate,
    QualityStatus,
    RankedProduct,
    ShoppingRequest,
    VerificationStatus,
)
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile


@dataclass
class RankingInternals:
    ranked: list[RankedProduct] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    duplicate_offers: list[dict] = field(default_factory=list)


def _dedupe_key(candidate: ProductCandidate) -> str:
    """One shortlist slot per recognized model family."""
    return (candidate.model or "").casefold()


def _dedupe_reason(kept: ProductCandidate, dropped: ProductCandidate) -> str:
    if kept.configuration != dropped.configuration:
        return (
            "same model family; prefer higher evidence score, configured offer, "
            "then lower verified listed price"
        )
    return (
        "same model/configuration; prefer higher evidence score, then lower verified listed price"
    )


def _exclusion_reason(candidate: ProductCandidate, budget: Decimal) -> str:
    if candidate.quality_status == QualityStatus.REJECTED and candidate.quality_reasons:
        return candidate.quality_reasons[0]
    if candidate.quality_status != QualityStatus.ELIGIBLE:
        if candidate.quality_reasons:
            return ";".join(candidate.quality_reasons)
        return f"quality_status_{candidate.quality_status.value}"
    if not candidate.model:
        return "missing_exact_model"
    if candidate.currency != "USD":
        return "non_usd_price"
    if candidate.listed_price is None:
        return "missing_price"
    if candidate.price_status != VerificationStatus.VERIFIED:
        return f"price_status_{candidate.price_status.value}"
    if candidate.listed_price > budget:
        return "price_above_budget"
    return "not_eligible"


def rank_candidates(
    request: ShoppingRequest,
    candidates: list[ProductCandidate],
    *,
    profile: CategoryProfile | None = None,
    limit: int = 5,
) -> RankingInternals:
    if profile is None:
        profile = get_profile(request.category)

    result = RankingInternals()
    eligible: list[tuple[ProductCandidate, int, list[str], bool]] = []

    for candidate in candidates:
        fit_reason = profile.request_fit(candidate, request)
        if (
            candidate.quality_status != QualityStatus.ELIGIBLE
            or not candidate.model
            or candidate.listed_price is None
            or candidate.price_status != VerificationStatus.VERIFIED
            or candidate.currency != "USD"
            or candidate.listed_price > request.budget
            or fit_reason
        ):
            reason = fit_reason or _exclusion_reason(candidate, request.budget)
            result.excluded.append(
                {
                    "name": candidate.name,
                    "model": candidate.model,
                    "url": candidate.product_url,
                    "source": candidate.source,
                    "reason": reason,
                }
            )
            continue
        score, reasons, provisional = profile.score_candidate(candidate)
        eligible.append((candidate, score, reasons, provisional))

    by_model: dict[str, tuple[ProductCandidate, int, list[str], bool]] = {}
    for item in eligible:
        candidate, score, reasons, provisional = item
        key = _dedupe_key(candidate)
        current = by_model.get(key)
        has_config = 0 if candidate.configuration else 1
        rank_key = (-score, has_config, candidate.listed_price, candidate.product_url.casefold())
        if current is None:
            by_model[key] = item
            continue
        old = current[0]
        old_has_config = 0 if old.configuration else 1
        old_key = (-current[1], old_has_config, old.listed_price, old.product_url.casefold())
        kept, dropped = (item, current) if rank_key < old_key else (current, item)
        by_model[key] = kept
        result.duplicate_offers.append(
            {
                "model": candidate.model,
                "configuration": candidate.configuration,
                "kept_url": kept[0].product_url,
                "deduplicated_url": dropped[0].product_url,
                "reason": _dedupe_reason(kept[0], dropped[0]),
            }
        )

    ranked = [
        RankedProduct(candidate=c, score=s, reasons=r, provisional=p)
        for c, s, r, p in by_model.values()
    ]
    ranked.sort(
        key=lambda item: (
            -item.score,
            item.candidate.listed_price,
            (item.candidate.model or "").casefold(),
        )
    )
    result.ranked = ranked[:limit]
    return result


def limitations(profile: CategoryProfile | None = None, *, live: bool = False) -> list[str]:
    spec_line = (
        "Live mode fetches allow-listed manufacturer pages and datasheet PDFs; when a storefront blocks, the next hint is tried. A failed or mismatched page stays unknown or inaccessible."
        if live
        else "This run used local manufacturer spec fixtures. Pass --live to fetch manufacturer pages."
    )
    prefix = [
        "A verified listed item price is not a verified delivered total unless the page states an order total.",
        spec_line,
        "Live eBay and SerpApi discovery run only with --live and the matching API keys.",
        "SerpApi is capped at 5 HTTP calls per run by default (1 shopping + up to 4 detail); eBay supplies the rest. Use --skip-serpapi for zero SerpApi credits.",
        "SerpApi prices stay unverified until a retailer page reports the same USD item price.",
    ]
    profile_lines = list(profile.extra_limitations(live)) if profile is not None else []
    suffix = [
        "Category focus areas listed as request priorities are descriptive only; they do not reweight scores or personalize ranking.",
        "The shortlist is the best eligible set from this candidate pool by the category's fixed evidence heuristic, not proof of market-wide optimality.",
        "Local Ollama may narrate this report for the UI; ranking and scores stay deterministic and evidence-based.",
        # FUTURE: LLM-assisted discovery (v1-style) is not enabled; keep discovery evidence-first.
    ]
    return prefix + profile_lines + suffix
