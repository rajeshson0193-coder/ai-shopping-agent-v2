"""Identify exact models and reject accessories. No guessing."""

from __future__ import annotations

from urllib.parse import urlparse

from shopping_agent.models import ProductCandidate, QualityStatus, VerificationStatus
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile

# Search-result shells are not product pages we can verify.
_REJECT_HOSTS = {
    "google.com",
    "www.google.com",
    "shopping.google.com",
    "serpapi.com",
}


def _known_domain(url: str, domains: frozenset[str]) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _rejected_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in _REJECT_HOSTS)


def _price_evidence(candidate: ProductCandidate):
    for record in candidate.evidence:
        if record.field_name == "listed_price":
            return record
    return None


def identify_candidates(
    candidates: list[ProductCandidate],
    *,
    profile: CategoryProfile | None = None,
    category: str | None = None,
) -> list[ProductCandidate]:
    if profile is None:
        if not category:
            raise ValueError("identify_candidates requires profile= or category=")
        profile = get_profile(category)

    for candidate in candidates:
        title = candidate.name or ""
        lowered = title.casefold()
        parsed = urlparse(candidate.product_url)

        if parsed.scheme != "https" or not parsed.hostname:
            candidate.quality_status = QualityStatus.REJECTED
            candidate.quality_reasons = ["invalid_or_non_https_product_url"]
            continue

        if _rejected_host(candidate.product_url):
            candidate.quality_status = QualityStatus.REJECTED
            candidate.quality_reasons = ["search_result_url_not_product_page"]
            continue

        # Incomplete/replacement offers before generic accessories so diagnostics
        # keep the more specific reason (e.g. single-bud vs ear tips).
        if profile.looks_like_incomplete_offer(title):
            brand, model, configuration = profile.extract_identity(title)
            candidate.brand = brand
            candidate.model = model
            candidate.configuration = configuration
            candidate.quality_status = QualityStatus.REJECTED
            candidate.quality_reasons = [profile.incomplete_offer_reject_reason]
            continue

        if any(term in lowered for term in profile.accessory_terms):
            candidate.quality_status = QualityStatus.REJECTED
            candidate.quality_reasons = [profile.accessory_reject_reason]
            continue

        if profile.looks_like_rejected_fake(title):
            candidate.quality_status = QualityStatus.REJECTED
            candidate.quality_reasons = ["likely_noncatalog_or_fake_product_title"]
            continue

        brand, model, configuration = profile.extract_identity(title)
        candidate.brand = brand
        candidate.model = model
        candidate.configuration = configuration

        reasons: list[str] = []
        if not profile.matches_category(title):
            reasons.append(profile.category_missing_reason)
        if not model:
            reasons.append("no_recognized_model_in_title")
        if not _known_domain(candidate.product_url, profile.known_retailer_domains):
            reasons.append("source_domain_not_in_known_retailer_registry")

        if reasons:
            candidate.quality_status = QualityStatus.NEEDS_REVIEW
            candidate.quality_reasons = reasons
        else:
            candidate.quality_status = QualityStatus.ELIGIBLE
            candidate.quality_reasons = []

        for record in candidate.evidence:
            if record.field_name != "discovery":
                continue
            if model:
                record.status = VerificationStatus.VERIFIED
                record.supporting_text = (
                    f"{record.supporting_text or title}. Recognized model: {model}."
                )

        price_record = _price_evidence(candidate)
        has_usd_price = (
            candidate.listed_price is not None
            and candidate.currency.upper() == "USD"
            and candidate.listed_price >= 0
        )

        fixture_price = (
            price_record is not None
            and price_record.source_type == "fixture_listing_price"
            and price_record.status == VerificationStatus.VERIFIED
        )
        if model and has_usd_price and (candidate.source == "ebay" or fixture_price):
            # eBay Browse API, or a fixture that already marked listed price verified.
            # This is still not a delivered total.
            candidate.price_status = VerificationStatus.VERIFIED
            if price_record is not None:
                price_record.status = VerificationStatus.VERIFIED
        else:
            candidate.price_status = VerificationStatus.UNKNOWN
            if price_record is not None:
                price_record.status = VerificationStatus.UNKNOWN

    return candidates
