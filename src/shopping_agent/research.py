"""Attach manufacturer specification evidence.

Fixture mode uses the local spec catalog. Live mode fetches allow-listed
manufacturer pages and records why a claim stayed unknown or inaccessible.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from shopping_agent.http_fetch import PageFetch, fetch_page
from shopping_agent.models import Evidence, EvidenceStrength, ProductCandidate, VerificationStatus
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile
from shopping_agent.spec_extract import page_mentions_model

# Bound fetches per model so live laptop runs stay responsive.
# Earlier headphone demos were fast because hints were 1–2 small HTML pages;
# laptop hints often include multi‑MB owner manuals — keep this low.
MAX_HINT_FETCHES = 2


def _hint_fetch_order(hints: tuple[str, ...]) -> list[str]:
    """Prefer compact datasheets / HTML before huge owner manuals."""

    def rank(url: str) -> tuple[int, int]:
        lowered = url.casefold()
        if any(
            token in lowered
            for token in (
                "owners-manual",
                "owner-s-manual",
                "owner_s_manual",
                "/topicspdf/",
            )
        ):
            return (2, len(lowered))
        if ".pdf" in lowered:
            return (0, len(lowered))
        return (1, len(lowered))

    return sorted(hints, key=rank)


def _fixture_model_keys(model: str) -> list[str]:
    """Try exact identity first, then family stem for SKU-enriched models."""
    keys = [model]
    # Strip trailing chassis / Lenovo MT / HP product for fixture catalog lookup.
    family = re.sub(r"\s+15[A-Z]{2,4}\d{1,2}$", "", model, flags=re.I)
    family = re.sub(r"\s+\d{2}-[a-z]\d{3,4}[a-z]{0,2}$", "", family, flags=re.I)
    family = re.sub(r"\s+\d{4}$", "", family).strip()
    if family and family != model:
        keys.append(family)
    return keys


def _as_status(value: str | None) -> VerificationStatus:
    try:
        return VerificationStatus(value or "unknown")
    except ValueError:
        return VerificationStatus.UNKNOWN


def _blank_specs(
    candidate: ProductCandidate,
    profile: CategoryProfile,
    retrieved_at: datetime,
    status: VerificationStatus,
    reason: str,
    source_url: str | None = None,
) -> None:
    for field_name in profile.spec_fields:
        candidate.specifications[field_name] = Evidence(
            field_name=field_name,
            status=status,
            source_url=source_url,
            source_type="manufacturer_page" if source_url else None,
            retrieved_at=retrieved_at,
            evidence_strength=EvidenceStrength.INSUFFICIENT,
            reason=reason,
        )


def _load_spec_catalog(path: Path) -> dict:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    specs = payload.get("specs", {})
    return specs if isinstance(specs, dict) else {}


def _research_from_fixtures(
    candidates: list[ProductCandidate],
    profile: CategoryProfile,
) -> list[ProductCandidate]:
    catalog = _load_spec_catalog(profile.spec_fixture_path)
    retrieved_at = datetime.now(timezone.utc)

    for candidate in candidates:
        if not candidate.model:
            _blank_specs(
                candidate,
                profile,
                retrieved_at,
                VerificationStatus.UNKNOWN,
                "No exact model identity, so manufacturer specs were not researched",
            )
            continue

        model_specs = None
        for key in _fixture_model_keys(candidate.model):
            raw_specs = catalog.get(key)
            if isinstance(raw_specs, dict):
                model_specs = raw_specs
                break
        if not isinstance(model_specs, dict):
            _blank_specs(
                candidate,
                profile,
                retrieved_at,
                VerificationStatus.UNKNOWN,
                "No manufacturer spec fixture is configured for this model",
            )
            continue

        for field_name in profile.spec_fields:
            raw = model_specs.get(field_name, {})
            if not isinstance(raw, dict):
                raw = {}
            candidate.specifications[field_name] = Evidence(
                field_name=field_name,
                status=_as_status(raw.get("status")) if raw else VerificationStatus.UNKNOWN,
                value=raw.get("value"),
                source_url=raw.get("source_url"),
                source_type="manufacturer_spec_fixture",
                supporting_text=raw.get("supporting_text"),
                retrieved_at=retrieved_at,
                evidence_strength=EvidenceStrength.INSUFFICIENT,
                reason=raw.get("reason")
                or (None if raw else "No manufacturer spec fixture is configured for this claim"),
            )
    return candidates


def _apply_extracted(
    candidate: ProductCandidate,
    profile: CategoryProfile,
    page: PageFetch,
    retrieved_at: datetime,
) -> None:
    # Extract from text near the exact model first so footer/related-product
    # chrome on multi-product pages cannot supply unrelated claims.
    from shopping_agent.evidence_context import preparation_text_for_extraction

    source_text = preparation_text_for_extraction(page.text, candidate.model)
    extracted = profile.extract_specs(source_text, candidate)
    for field_name in profile.spec_fields:
        value, supporting, reason = extracted.get(field_name, (None, None, "No extraction result"))
        status = VerificationStatus.VERIFIED if value else VerificationStatus.UNKNOWN
        candidate.specifications[field_name] = Evidence(
            field_name=field_name,
            status=status,
            value=value,
            source_url=page.url,
            source_type="manufacturer_page",
            supporting_text=supporting,
            retrieved_at=retrieved_at,
            evidence_strength=EvidenceStrength.INSUFFICIENT,
            reason=reason,
        )


def _research_live(
    candidates: list[ProductCandidate],
    profile: CategoryProfile,
    timeout: int,
    fetch,
) -> list[ProductCandidate]:
    retrieved_at = datetime.now(timezone.utc)
    seen_models: dict[str, list[ProductCandidate]] = {}
    for candidate in candidates:
        if not candidate.model:
            _blank_specs(
                candidate,
                profile,
                retrieved_at,
                VerificationStatus.UNKNOWN,
                "No exact model identity, so manufacturer specs were not researched",
            )
            continue
        seen_models.setdefault(candidate.model.casefold(), []).append(candidate)

    page_cache: dict[str, PageFetch] = {}

    for _model_key, group in seen_models.items():
        model_name = group[0].model or ""
        listing_text = " ".join(
            part for part in (group[0].name, group[0].configuration) if part
        )
        hints = tuple(
            url
            for url in profile.page_hints_for_model(model_name, listing_text)
            if profile.allowed_manufacturer_url(model_name, url)
        )
        if not hints:
            for candidate in group:
                _blank_specs(
                    candidate,
                    profile,
                    retrieved_at,
                    VerificationStatus.UNKNOWN,
                    "No allow-listed manufacturer page is configured for this model",
                )
            continue

        attempts: list[str] = []
        usable_pages: list[PageFetch] = []
        from shopping_agent.evidence_context import preparation_text_for_extraction

        for url in _hint_fetch_order(hints)[:MAX_HINT_FETCHES]:
            if url not in page_cache:
                page_cache[url] = fetch(url, timeout=timeout)
            page = page_cache[url]
            attempts.append(f"{url} -> {page.outcome}: {page.reason}")
            if page.outcome != "ok":
                continue
            if not page_mentions_model(page.text, model_name):
                continue
            usable_pages.append(page)
            # Early-exit once a page yields usable specs for this listing.
            probe = group[0]
            source_text = preparation_text_for_extraction(page.text, probe.model)
            extracted = profile.extract_specs(source_text, probe)
            if profile.score_page_fit(extracted, probe) > 0:
                break

        if not usable_pages:
            ok_pages = [
                page_cache[url]
                for url in hints
                if url in page_cache and page_cache[url].outcome == "ok"
            ]
            if not ok_pages:
                reason = "Manufacturer page was not retrieved. " + " | ".join(attempts)
                for candidate in group:
                    _blank_specs(
                        candidate,
                        profile,
                        retrieved_at,
                        VerificationStatus.INACCESSIBLE,
                        reason,
                        source_url=hints[0],
                    )
                    candidate.evidence.append(
                        Evidence(
                            field_name="manufacturer_page_accessibility",
                            status=VerificationStatus.INACCESSIBLE,
                            source_url=hints[0],
                            source_type="manufacturer_page",
                            retrieved_at=retrieved_at,
                            reason=reason,
                        )
                    )
                continue

            reason = (
                "Page was retrieved but does not mention the exact model, so specifications were not taken from it. "
                + " | ".join(attempts)
            )
            for candidate in group:
                _blank_specs(
                    candidate,
                    profile,
                    retrieved_at,
                    VerificationStatus.UNKNOWN,
                    reason,
                    source_url=ok_pages[0].url,
                )
                candidate.evidence.append(
                    Evidence(
                        field_name="manufacturer_page_accessibility",
                        status=VerificationStatus.VERIFIED,
                        source_url=ok_pages[0].url,
                        source_type="manufacturer_page",
                        supporting_text="Manufacturer page text was retrieved.",
                        retrieved_at=retrieved_at,
                        reason=reason,
                    )
                )
            continue

        for candidate in group:
            best_page = usable_pages[0]
            best_score = -10_000
            for page in usable_pages:
                source_text = preparation_text_for_extraction(page.text, candidate.model)
                extracted = profile.extract_specs(source_text, candidate)
                score = profile.score_page_fit(extracted, candidate)
                if score > best_score:
                    best_score = score
                    best_page = page
            _apply_extracted(candidate, profile, best_page, retrieved_at)
            candidate.evidence.append(
                Evidence(
                    field_name="manufacturer_page_accessibility",
                    status=VerificationStatus.VERIFIED,
                    source_url=best_page.url,
                    source_type="manufacturer_page",
                    supporting_text=(
                        "Manufacturer page or datasheet mentions the exact model; "
                        "option values preferred to match this listing's configuration."
                    ),
                    retrieved_at=retrieved_at,
                    reason=" | ".join(attempts),
                )
            )
    return candidates


def research_candidates(
    candidates: list[ProductCandidate],
    *,
    profile: CategoryProfile | None = None,
    category: str | None = None,
    live: bool = False,
    timeout: int = 12,
    fetch=fetch_page,
) -> list[ProductCandidate]:
    if profile is None:
        if not category:
            raise ValueError("research_candidates requires profile= or category=")
        profile = get_profile(category)
    if live:
        return _research_live(candidates, profile, timeout, fetch)
    return _research_from_fixtures(candidates, profile)
