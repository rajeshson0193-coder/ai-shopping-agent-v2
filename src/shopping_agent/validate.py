"""Separate populated fields, verification status, and evidence strength."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from shopping_agent.evidence_context import (
    looks_like_cable_not_port,
    supporting_text_tied_to_model,
)
from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    VerificationStatus,
)
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile
from shopping_agent.retailer_pages import corroborate_listed_price

_WEAK_CONTEXT = re.compile(
    r"\b(?:menu|navigation|breadcrumb|related products|you may also like|skip to content|"
    r"facebook|instagram|choose your location)\b",
    re.I,
)


def _valid_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def audit_evidence(
    record: Evidence,
    profile: CategoryProfile,
    *,
    model: str | None = None,
) -> Evidence:
    notes: list[str] = []
    status = record.status
    text = record.supporting_text
    source_url = record.source_url
    value = record.value
    claim_terms = profile.claim_term_patterns

    if status != VerificationStatus.VERIFIED:
        strength = EvidenceStrength.INSUFFICIENT
        notes.append(f"Claim status is {status.value}; it is not confirmed.")
    elif not _valid_http_url(source_url) or not isinstance(text, str) or not text.strip():
        strength = EvidenceStrength.INSUFFICIENT
        notes.append("Verified status lacks a usable source URL or supporting text.")
    elif _WEAK_CONTEXT.search(text) or len(text.strip()) > 900:
        strength = EvidenceStrength.WEAK
        notes.append("Supporting text contains navigation or page chrome.")
    elif record.field_name in claim_terms and claim_terms[record.field_name].search(text) is None:
        strength = EvidenceStrength.WEAK
        notes.append("Supporting text does not contain a claim-specific term.")
    elif record.field_name == "charging_port" and looks_like_cable_not_port(text):
        strength = EvidenceStrength.WEAK
        notes.append(
            "Supporting text mentions a USB-C cable, not an explicit charging-port claim."
        )
    elif (
        model
        and (record.source_type or "") == "manufacturer_page"
        and not supporting_text_tied_to_model(text, model)
    ):
        # Live page snippets must name the model (or brandless alias). Otherwise a
        # footer/related-product claim can look "claim-relevant" and score as STRONG.
        strength = EvidenceStrength.WEAK
        notes.append("Supporting text is not clearly tied to this exact model.")
    elif value in (None, ""):
        strength = EvidenceStrength.INSUFFICIENT
        notes.append("The verified record has no explicit value.")
    else:
        strength = EvidenceStrength.STRONG
        notes.append("Source URL and claim-relevant, model-linked supporting text are present.")

    record.evidence_strength = strength
    extra = " ".join(notes)
    record.reason = extra if not record.reason else f"{record.reason}. {extra}"
    return record


def validate_candidates(
    candidates: list[ProductCandidate],
    *,
    profile: CategoryProfile | None = None,
    category: str | None = None,
    live: bool = False,
    timeout: int = 12,
    fetch=None,
) -> list[ProductCandidate]:
    if profile is None:
        if not category:
            raise ValueError("validate_candidates requires profile= or category=")
        profile = get_profile(category)

    for candidate in candidates:
        if live and candidate.price_status != VerificationStatus.VERIFIED:
            if fetch is None:
                corroborate_listed_price(candidate, timeout=timeout)
            else:
                corroborate_listed_price(candidate, timeout=timeout, fetch=fetch)
        elif candidate.delivered_total_status != VerificationStatus.VERIFIED:
            candidate.delivered_total = None
            candidate.delivered_total_status = VerificationStatus.UNKNOWN

        for spec in candidate.specifications.values():
            audit_evidence(spec, profile, model=candidate.model)
        claims = profile.apply_consistency(candidate)
        profile.apply_fallback(candidate, claims)

        for record in candidate.evidence:
            if record.field_name in {"listed_price", "condition", "discovery"}:
                if record.status == VerificationStatus.VERIFIED and _valid_http_url(record.source_url):
                    if record.supporting_text:
                        record.evidence_strength = EvidenceStrength.STRONG
                    else:
                        record.evidence_strength = EvidenceStrength.INSUFFICIENT
                else:
                    record.evidence_strength = EvidenceStrength.INSUFFICIENT
    return candidates
