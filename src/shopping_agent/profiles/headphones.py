"""Wireless earbuds/headphones category profile (US, typically under $150)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    VerificationStatus,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

# Descriptive category focus areas only — not scoring weights. Ranking uses the
# fixed evidence heuristic in score_candidate (ANC/type/port/condition).
HEADPHONE_PRIORITIES = (
    "noise cancellation",
    "battery life",
    "comfort and fit",
    "sound quality",
    "value",
)

SPEC_FIELDS = ("headphone_type", "anc_support", "battery_life", "charging_port")

MODEL_PAGE_HINTS: dict[str, tuple[str, ...]] = {
    "soundcore q20i": (
        "https://www.soundcore.com/products/q20i-a3004z31",
        "https://service.soundcore.com/article-description/soundcore-Q20i-Headphones-FAQ?urlName=soundcore-Q20i-Headphones-FAQ",
    ),
    "soundcore p30i": (
        "https://www.soundcore.com/products/soundcore-p30i",
        "https://www.soundcore.com/uk/products/a3959-soundcore-p30i",
    ),
    "soundcore space a40": (
        "https://www.soundcore.com/products/space-a40-a3936011",
        "https://www.soundcore.com/space-a40",
    ),
    "sony wh-ch520": (
        "https://www.sony.com/electronics/support/wireless-headphones-bluetooth-headphones/wh-ch520/specifications",
    ),
    "sony wf-c700n": (
        "https://www.sony.com/electronics/support/wireless-headphones-bluetooth-headphones/wf-c700n/specifications",
        "https://electronics.sony.com/audio/headphones/truly-wireless-headphones/p/wfc700n-b",
    ),
    "jbl vibe beam 2": (
        "https://www.jbl.com/JBLVBEAM2BLKAM.html",
        "https://support.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw5385e405/pdfs/JBL_Vibe_Beam_2_Specsheet_EN.pdf",
    ),
    "jbl tune beam": (
        "https://www.jbl.com/JBL-TUNE-BEAM.html",
        "https://www.jbl.com/bluetooth-earbuds/JBL+TUNE+BEAM-.html",
    ),
    "jlab studio 2": (
        "https://help.jlab.com/pages/studio-2-wireless-on-ear-headphones-product-support-page",
    ),
    "skullcandy sesh anc": (
        # Support page states True Wireless + ANC; avoid Sesh ANC Active (different SKU).
        "https://www.skullcandy.com/blogs/product-help/sesh-anc",
    ),
    "samsung galaxy buds fe": (
        # /mobile-audio/galaxy-buds-fe/ currently serves Buds3 FE chrome; prefer /app/ path.
        "https://www.samsung.com/us/app/mobile-audio/galaxy-buds-fe/",
        "https://www.samsung.com/us/support/answer/ANS10001314/",
    ),
    "treblab z2": (
        "https://treblab.com/products/treblab-z2",
    ),
}

# Known form factors when title/configuration does not state them clearly.
_OVER_ON_EAR_MODELS = frozenset(
    {
        "soundcore q20i",
        "soundcore q20i plus",
        "sony wh-ch520",
        "jlab studio 2",
        "treblab z2",
    }
)
_TRUE_WIRELESS_MODELS = frozenset(
    {
        "jbl vibe beam 2",
        "jbl tune beam",
        "skullcandy sesh anc",
        "soundcore p30i",
        "soundcore space a40",
        "sony wf-c700n",
        "samsung galaxy buds fe",
    }
)

MANUFACTURER_DOMAINS: dict[str, tuple[str, ...]] = {
    "soundcore": ("soundcore.com", "anker.com"),
    "sony": ("sony.com",),
    "jbl": ("jbl.com",),
    "jlab": ("jlab.com",),
    "skullcandy": ("skullcandy.com",),
    "treblab": ("treblab.com",),
    "samsung": ("samsung.com",),
}

KNOWN_RETAILER_DOMAINS = frozenset(
    {
        "amazon.com",
        "bestbuy.com",
        "bhphotovideo.com",
        "costco.com",
        "ebay.com",
        "target.com",
        "walmart.com",
        "newegg.com",
        "adorama.com",
        "jbl.com",
        "soundcore.com",
        "anker.com",
        "sony.com",
        "jlab.com",
        "skullcandy.com",
        "treblab.com",
        "samsung.com",
    }
)

CATEGORY_TERMS = (
    "headphone",
    "headphones",
    "earbud",
    "earbuds",
    "earphone",
    "earphones",
    "headset",
    "buds",
    "wireless earbuds",
    "noise cancelling",
    "noise-canceling",
)

ACCESSORY_TERMS = (
    "ear tip",
    "ear tips",
    "ear tip replacement",
    "charging case only",
    "case only",
    "replacement cable",
    "headphone stand",
    "headphone holder",
    "earpad",
    "ear pad",
    "ear cushions",
    # Incomplete / parts-only offers (also covered by looks_like_incomplete_offer).
    "earbud replacement",
    "earbuds replacement",
    "replacement earbud",
    "replacement ear bud",
    "parts only",
    "replacement part",
    "replacement parts",
)

# Single-bud / side-specific / parts-only listings — model match alone is not enough.
_INCOMPLETE_OFFER_RE = re.compile(
    r"(?:"
    r"\bear\s*buds?\s+replacement\b|"
    r"\breplacement\s+(?:ear\s*)?buds?\b|"
    r"\breplacement\s+(?:right|left)\b|"
    r"\b(?:right|left)\s+side\b|"
    r"\b(?:single|one)\s+(?:ear\s*)?buds?\b|"
    r"\b(?:right|left)\s+(?:ear\s*)?buds?\s+only\b|"
    r"\bonly\s+(?:the\s+)?(?:right|left)\s+(?:ear\s*)?buds?\b|"
    r"\b(?:right|left)[\s-]+only\b|"
    r"\bparts?\s+only\b|"
    r"\breplacement\s+parts?\b|"
    r"\bjust\s+(?:the\s+)?(?:right|left)\s+(?:ear\s*)?buds?\b|"
    r"\b(?:missing|without)\s+(?:the\s+)?(?:left|right)\s+(?:ear\s*)?buds?\b"
    r")",
    re.I,
)
_COMPLETE_PAIR_RE = re.compile(
    r"\b(?:"
    r"left\s*(?:and|&|/)\s*right|"
    r"right\s*(?:and|&|/)\s*left|"
    r"both\s+(?:sides|earbuds|buds)|"
    r"complete\s+pair|"
    r"pair\s+of\s+(?:earbuds|buds)"
    r")\b",
    re.I,
)

# Longer / more-specific patterns first. Unsupported siblings (SESH ANC Active,
# Tune Beam 2, …) must not canonicalize to a shorter allow-listed model — only add
# a pattern + page hints when that exact SKU is intentionally supported.
_MODEL_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:anker\s+)?soundcore(?:\s+by\s+anker)?\s+q20i\s+plus\b", re.I), "Soundcore", "Soundcore Q20i Plus"),
    (re.compile(r"\b(?:anker\s+)?soundcore(?:\s+by\s+anker)?\s+q20i\b", re.I), "Soundcore", "Soundcore Q20i"),
    (re.compile(r"\bsoundcore\s+by\s+anker\s+q20i\b", re.I), "Soundcore", "Soundcore Q20i"),
    (re.compile(r"\b(?:anker\s+)?soundcore(?:\s+by\s+anker)?\s+space\s+a40\b", re.I), "Soundcore", "Soundcore Space A40"),
    (re.compile(r"\b(?:anker\s+)?soundcore(?:\s+by\s+anker)?\s+p30i\b", re.I), "Soundcore", "Soundcore P30i"),
    (re.compile(r"\bsony\s+wh[-\s]?ch520\b", re.I), "Sony", "Sony WH-CH520"),
    (re.compile(r"\bsony\s+wf[-\s]?c700n\b", re.I), "Sony", "Sony WF-C700N"),
    (re.compile(r"\bjbl\s+vibe\s+beam\s+2\b", re.I), "JBL", "JBL Vibe Beam 2"),
    # Tune Beam 2 is a different SKU — not allow-listed (unlike Vibe Beam 2).
    (re.compile(r"\bjbl\s+tune\s+beam\b(?!\s*2\b)", re.I), "JBL", "JBL Tune Beam"),
    (re.compile(r"\bjlab\s+studio\s+2\b", re.I), "JLab", "JLab Studio 2"),
    # SESH ANC Active is a different SKU; still allow "SESH ANC Active Noise…".
    (
        re.compile(
            r"\bskullcandy\s+sesh\s+anc\b(?!\s+active\b(?!\s+(?:noise|cancell)))",
            re.I,
        ),
        "Skullcandy",
        "Skullcandy SESH ANC",
    ),
    (re.compile(r"\bsamsung\s+galaxy\s+buds\s*fe\b", re.I), "Samsung", "Samsung Galaxy Buds FE"),
    (re.compile(r"\btreblab\s+z2\b", re.I), "TREBLAB", "TREBLAB Z2"),
)

# After a model match, reject unlisted generation/edition tokens so "… Pro" / "… 2"
# cannot inherit the base model's manufacturer hints. Tokens already consumed by a
# longer allow-listed pattern (Q20i Plus, Vibe Beam 2) never reach this check.
_UNLISTED_VARIANT_SUFFIX_RE = re.compile(
    r"^\s+(?:pro|plus|max|mini|se|neo|evo|\d+|gen\s*\d+)\b",
    re.I,
)

_TYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\btrue\s+wireless\b|\btws\b|\bearbuds?\b|\bbuds\b", re.I), "true wireless earbuds"),
    (re.compile(r"\bover[-\s]?ear\b", re.I), "over-ear headphones"),
    (re.compile(r"\bon[-\s]?ear\b", re.I), "on-ear headphones"),
    (re.compile(r"\bin[-\s]?ear\b", re.I), "in-ear headphones"),
    (re.compile(r"\bheadphones?\b", re.I), "wireless headphones"),
)

_ANC_TITLE_RE = re.compile(
    r"\b(?:active\s+noise\s+cancell?(?:ing|ation)|ANC|noise\s+cancell?(?:ing|ation))\b",
    re.I,
)
_NO_ANC_TITLE_RE = re.compile(
    r"\b(?:no\s+ANC|without\s+(?:ANC|noise\s+cancell)|non[-\s]?ANC)\b",
    re.I,
)
_BATTERY_TITLE_RE = re.compile(
    r"\b(?:up\s+to\s+)?(\d{1,3})\s*(?:hours?|hrs?)\b[^.]{0,40}\b(?:battery|playtime|playback)\b"
    r"|\b(?:battery|playtime|playback)\b[^.]{0,40}\b(?:up\s+to\s+)?(\d{1,3})\s*(?:hours?|hrs?)\b",
    re.I,
)

# Manufacturer page extractors
_TYPE_PAGE_PATTERNS = (
    (re.compile(r"\bon[- ]ear headphones\b", re.I), "on-ear headphones"),
    (re.compile(r"\bover[- ]ear headphones\b", re.I), "over-ear headphones"),
    (
        re.compile(
            r"\btrue wireless(?:\s+sport)?(?:\s+noise cancell?ing)?(?:\s+active)?"
            r"\s+earbuds\b",
            re.I,
        ),
        "true wireless earbuds",
    ),
    (re.compile(r"\btrue wireless in[- ]ear\b", re.I), "true wireless earbuds"),
    (re.compile(r"\btrue wireless product\b", re.I), "true wireless earbuds"),
    (
        re.compile(r"\b(?:headphone|product)\s*type\s*[:：]\s*true wireless\b", re.I),
        "true wireless earbuds",
    ),
    (re.compile(r"\bwireless earbuds\b", re.I), "true wireless earbuds"),
    (re.compile(r"\bin[- ]ear headphones\b", re.I), "in-ear headphones"),
)
_ANC_PAGE_PATTERNS = (
    (re.compile(r"\b(?:does not feature|does not support|without) active noise cancell?ation\b", re.I), "unsupported"),
    (
        re.compile(
            r"\b(?:active noise cancellation|active noise cancelling|adaptive noise cancelling|"
            r"hybrid active noise cancelling)\b",
            re.I,
        ),
        "supported",
    ),
)
_BATTERY_PAGE_PATTERNS = (
    re.compile(
        r"[^.]{0,100}(?:\d{1,3}\s*(?:total\s*)?hours?[^.]{0,160}(?:playtime|playback|battery life|charging case|ANC off|ANC on)"
        r"|(?:playtime|playback)[^.]{0,160}\d{1,3}\s*(?:total\s*)?hours?)[^.]*\.",
        re.I,
    ),
    re.compile(
        r"(?:total playtime|total playback time|music playtime|playtime|playback time|battery life)"
        r"\s*\(?hours?\)?\s*[:：]?\s*(?:up to\s*)?\d{1,3}\s*(?:hours?|hrs?|h)?\b",
        re.I,
    ),
)
_PORT_PAGE_PATTERNS = (
    # Cable mentions are not a charging-port claim ("USB-C Rapid Charge cable" ≠ USB-C port).
    (re.compile(r"(?:charging port|port)\s*(?:is|:|of)?\s*(USB[- ]?C|USB Type-C|Type-C)", re.I), "USB-C"),
    (re.compile(r"(USB[- ]?C|USB Type-C|Type-C)\s+(?:charging port|port)", re.I), "USB-C"),
    (re.compile(r"(?:charging port|port)\s*(?:is|:|of)?\s*(Micro-USB|Micro USB)", re.I), "Micro-USB"),
)
_NAV_NOISE = re.compile(
    r"\b(?:skip to content|add to cart|sign in|facebook|instagram|related products|menu)\b",
    re.I,
)


@dataclass(frozen=True)
class HeadphoneListingClaims:
    headphone_type: str | None = None
    anc_support: str | None = None
    battery_hours: int | None = None


def matches_headphones_category(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in CATEGORY_TERMS)


def looks_like_rejected_fake(title: str) -> bool:
    return False


def looks_like_incomplete_offer(title: str) -> bool:
    """True for single-side / replacement-part offers that are not a complete product."""
    if not isinstance(title, str) or not title.strip():
        return False
    if _COMPLETE_PAIR_RE.search(title):
        return False
    return bool(_INCOMPLETE_OFFER_RE.search(title))


_EARBUD_DISCOVERY_QUERIES = (
    "JBL Vibe Beam 2 earbuds",
    "Skullcandy SESH ANC earbuds",
    "Soundcore P30i earbuds",
    "Soundcore Space A40 earbuds",
    "Sony WF-C700N earbuds",
    "Samsung Galaxy Buds FE",
    "JBL Tune Beam earbuds",
    "true wireless earbuds ANC under 100",
    "wireless earbuds noise cancelling",
)

_HEADPHONE_DISCOVERY_QUERIES = (
    "Soundcore Q20i headphones",
    "Sony WH-CH520 headphones",
    "JLab Studio 2 headphones",
    "TREBLAB Z2 headphones",
    "noise cancelling headphones under 150",
    "wireless over ear headphones ANC",
)


def _prefers_true_wireless(request) -> bool:
    if request is None:
        return False
    constraints = getattr(request, "constraints", None) or []
    if "prefer_true_wireless" in constraints:
        return True
    raw = str(getattr(request, "raw_text", "") or "")
    return bool(re.search(r"\b(?:earbuds?|earphones?|\btws\b|true\s+wireless|buds)\b", raw, re.I))


def discovery_queries(request=None) -> list[str]:
    if _prefers_true_wireless(request):
        return list(_EARBUD_DISCOVERY_QUERIES)
    # Mixed catalog when the user asked for headphones generally.
    return list(_EARBUD_DISCOVERY_QUERIES[:4]) + list(_HEADPHONE_DISCOVERY_QUERIES)


def discovery_search_query(request=None) -> str:
    if _prefers_true_wireless(request):
        return "true wireless earbuds ANC"
    return "wireless headphones earbuds"


def resolved_form_factor(candidate: ProductCandidate) -> str | None:
    """Best-effort form factor from specs, configuration, model, or title."""
    spec = candidate.specifications.get("headphone_type") if candidate.specifications else None
    if spec is not None and spec.value:
        return str(spec.value).casefold()
    configuration = (candidate.configuration or "").casefold()
    for token in (
        "true wireless earbuds",
        "over-ear headphones",
        "on-ear headphones",
        "in-ear headphones",
    ):
        if token in configuration:
            return token
    model_key = (candidate.model or "").casefold()
    if model_key in _TRUE_WIRELESS_MODELS:
        return "true wireless earbuds"
    if model_key in _OVER_ON_EAR_MODELS:
        if "wh-ch520" in model_key or "studio 2" in model_key:
            return "on-ear headphones"
        return "over-ear headphones"
    title = candidate.name or ""
    claims = extract_listing_claims_from_text(title)
    return claims.headphone_type.casefold() if claims.headphone_type else None


def request_fit(candidate: ProductCandidate, request) -> str | None:
    if not _prefers_true_wireless(request):
        return None
    form = resolved_form_factor(candidate)
    if form in {"over-ear headphones", "on-ear headphones", "wireless headphones"}:
        return "form_factor_mismatch_for_earbuds_query"
    model_key = (candidate.model or "").casefold()
    if model_key in _OVER_ON_EAR_MODELS:
        return "form_factor_mismatch_for_earbuds_query"
    return None


def page_hints_for_model(model: str, listing_text: str = "") -> tuple[str, ...]:
    del listing_text
    if not model or not model.strip():
        return ()
    return MODEL_PAGE_HINTS.get(model.casefold().strip(), ())


def extract_identity(title: str) -> tuple[str | None, str | None, str | None]:
    if not isinstance(title, str) or not title.strip():
        return None, None, None

    brand = None
    model = None
    for pattern, found_brand, canonical in _MODEL_PATTERNS:
        match = pattern.search(title)
        if not match:
            continue
        # Unlisted edition/generation after the allow-listed stem → no identity.
        if _UNLISTED_VARIANT_SUFFIX_RE.match(title[match.end() :]):
            brand = None
            model = None
            break
        brand = found_brand
        model = canonical
        break

    claims = extract_listing_claims_from_text(title)
    configuration = None
    parts: list[str] = []
    if claims.headphone_type:
        parts.append(claims.headphone_type)
    if claims.anc_support == "supported":
        parts.append("ANC")
    elif claims.anc_support == "unsupported":
        parts.append("no ANC")
    if claims.battery_hours is not None:
        parts.append(f"{claims.battery_hours}h battery")
    if parts:
        configuration = " / ".join(parts)
    return brand, model, configuration


def extract_listing_claims_from_text(text: str) -> HeadphoneListingClaims:
    headphone_type = None
    for pattern, value in _TYPE_PATTERNS:
        if pattern.search(text):
            headphone_type = value
            break

    anc_support = None
    if _NO_ANC_TITLE_RE.search(text):
        anc_support = "unsupported"
    elif _ANC_TITLE_RE.search(text):
        anc_support = "supported"

    battery_hours = None
    battery_match = _BATTERY_TITLE_RE.search(text)
    if battery_match:
        raw = battery_match.group(1) or battery_match.group(2)
        if raw:
            battery_hours = int(raw)

    return HeadphoneListingClaims(
        headphone_type=headphone_type,
        anc_support=anc_support,
        battery_hours=battery_hours,
    )


def extract_listing_claims(candidate: ProductCandidate) -> HeadphoneListingClaims:
    text = " ".join(part for part in (candidate.name or "", candidate.configuration or "") if part)
    return extract_listing_claims_from_text(text)


def _snippet(text: str, match: re.Match[str], model: str | None = None) -> str:
    from shopping_agent.evidence_context import model_linked_snippet

    return model_linked_snippet(text, match, model)


def extract_headphone_specs(text: str, candidate: ProductCandidate | None = None):
    from shopping_agent.evidence_context import claim_near_model

    model = candidate.model if candidate is not None else None
    found: dict[str, tuple[str | None, str | None, str]] = {}

    # Prefer the earliest product-type claim near the model. Storefront footers
    # often list every category ("Over Ear Headphones", "True Wireless Earbuds").
    type_hits: list[tuple[int, str, re.Match[str]]] = []
    for pattern, value in _TYPE_PAGE_PATTERNS:
        for match in pattern.finditer(text):
            if model and not claim_near_model(text, match.start(), match.end(), model):
                continue
            type_hits.append((match.start(), value, match))
    type_hits.sort(key=lambda item: item[0])
    if type_hits:
        _, headphone_type, type_match = type_hits[0]
        found["headphone_type"] = (
            headphone_type,
            _snippet(text, type_match, model),
            "explicit product-type wording near model"
            if model
            else "explicit product-type wording",
        )
    else:
        found["headphone_type"] = (
            None,
            None,
            "No explicit headphone/earbud type wording found",
        )

    anc_value = None
    anc_match = None
    for pattern, value in _ANC_PAGE_PATTERNS:
        for match in pattern.finditer(text):
            if model and not claim_near_model(text, match.start(), match.end(), model):
                continue
            anc_value = value
            anc_match = match
            break
        if anc_match is not None:
            break
    found["anc_support"] = (
        (anc_value, _snippet(text, anc_match, model), "explicit ANC wording")
        if anc_match
        else (None, None, "No explicit ANC support wording found")
    )

    battery_value = None
    battery_match = None
    for pattern in _BATTERY_PAGE_PATTERNS:
        for match in pattern.finditer(text):
            if model and not claim_near_model(text, match.start(), match.end(), model):
                continue
            claim = re.sub(r"\s+", " ", match.group(0)).strip()
            has_duration = bool(re.search(r"\b\d{1,3}\s*(?:hours?|hrs?|h)\b", claim, re.I))
            has_context = bool(
                re.search(
                    r"\b(?:battery life|playtime|playback time|total playtime)\b",
                    claim,
                    re.I,
                )
            )
            is_other = bool(
                re.search(
                    r"\b(?:charge time|charging time|standby time|talk time)\b",
                    claim,
                    re.I,
                )
            )
            if not has_duration or not has_context or is_other or _NAV_NOISE.search(claim):
                continue
            hours = re.search(r"(\d{1,3})\s*(?:hours?|hrs?|h)\b", claim, re.I)
            battery_value = f"{hours.group(1)} hours" if hours else claim
            battery_match = match
            break
        if battery_match is not None:
            break
    found["battery_life"] = (
        (battery_value, _snippet(text, battery_match, model), "explicit battery/playtime wording")
        if battery_match
        else (None, None, "No explicit battery-life claim linked to playtime")
    )

    port_value = None
    port_match = None
    for pattern, value in _PORT_PAGE_PATTERNS:
        for match in pattern.finditer(text):
            if model and not claim_near_model(text, match.start(), match.end(), model):
                continue
            port_value = value
            port_match = match
            break
        if port_match is not None:
            break
    found["charging_port"] = (
        (port_value, _snippet(text, port_match, model), "explicit charging-port wording")
        if port_match
        else (None, None, "No explicit charging-port wording found")
    )
    return found


def _extract_specs(text: str, candidate: ProductCandidate):
    return extract_headphone_specs(text, candidate)


def _score_page_fit(extracted, candidate: ProductCandidate) -> int:
    claims = extract_listing_claims(candidate)
    score = sum(1 for value, _, _ in extracted.values() if value)
    anc = extracted.get("anc_support", (None, None, None))[0]
    if claims.anc_support and anc:
        score += 4 if claims.anc_support == anc else -3
    htype = extracted.get("headphone_type", (None, None, None))[0]
    if claims.headphone_type and htype and claims.headphone_type.casefold() in str(htype).casefold():
        score += 2
    return score


def _mark_conflict(record: Evidence, detail: str) -> None:
    record.status = VerificationStatus.CONFLICTING
    record.evidence_strength = EvidenceStrength.INSUFFICIENT
    note = f"Conflicts with listing configuration: {detail}"
    record.reason = note if not record.reason else f"{record.reason}. {note}"


def _mark_family_only(record: Evidence, detail: str) -> None:
    if record.status != VerificationStatus.VERIFIED or record.value in (None, ""):
        return
    record.evidence_strength = EvidenceStrength.WEAK
    note = f"Family datasheet claim is not tied to this offer's configuration: {detail}"
    record.reason = note if not record.reason else f"{record.reason}. {note}"


def apply_consistency(candidate: ProductCandidate) -> HeadphoneListingClaims:
    claims = extract_listing_claims(candidate)

    anc = candidate.specifications.get("anc_support")
    if anc and anc.status == VerificationStatus.VERIFIED and anc.value not in (None, ""):
        if claims.anc_support and claims.anc_support != str(anc.value).casefold():
            _mark_conflict(
                anc,
                f"listing ANC {claims.anc_support} vs manufacturer {anc.value}",
            )
        elif claims.anc_support is None:
            _mark_family_only(anc, "listing does not state ANC")

    battery = candidate.specifications.get("battery_life")
    if battery and battery.status == VerificationStatus.VERIFIED and battery.value not in (None, ""):
        mfr_hours = None
        match = re.search(r"(\d{1,3})", str(battery.value))
        if match:
            mfr_hours = int(match.group(1))
        if (
            claims.battery_hours is not None
            and mfr_hours is not None
            and abs(claims.battery_hours - mfr_hours) > 8
        ):
            _mark_conflict(
                battery,
                f"listing ~{claims.battery_hours}h vs manufacturer ~{mfr_hours}h",
            )
        elif claims.battery_hours is None:
            _mark_family_only(battery, "listing does not state battery life")

    htype = candidate.specifications.get("headphone_type")
    if htype and htype.status == VerificationStatus.VERIFIED and htype.value not in (None, ""):
        if claims.headphone_type is None:
            _mark_family_only(htype, "listing does not state headphone type")

    return claims


def _needs_listing_fallback(record: Evidence | None) -> bool:
    if record is None:
        return True
    if record.status in {
        VerificationStatus.CONFLICTING,
        VerificationStatus.UNKNOWN,
        VerificationStatus.INACCESSIBLE,
    }:
        return True
    if (
        record.status == VerificationStatus.VERIFIED
        and record.evidence_strength == EvidenceStrength.WEAK
        and (record.source_type or "").startswith("manufacturer")
    ):
        return True
    return False


def apply_fallback(candidate: ProductCandidate, claims: HeadphoneListingClaims | None = None) -> HeadphoneListingClaims:
    claims = claims or extract_listing_claims(candidate)
    listing_text = " ".join(part for part in (candidate.name or "", candidate.configuration or "") if part)

    def _replace(field_name: str, value: str, supporting: str) -> None:
        previous = candidate.specifications.get(field_name)
        if previous is not None and previous.value not in (None, ""):
            candidate.evidence.append(previous)
        candidate.specifications[field_name] = Evidence(
            field_name=field_name,
            status=VerificationStatus.VERIFIED,
            value=value,
            source_url=candidate.product_url,
            source_type="listing_title",
            supporting_text=supporting,
            evidence_strength=EvidenceStrength.WEAK,
            reason="Explicit listing title/configuration claim used because manufacturer evidence was missing or conflicting",
        )

    if claims.headphone_type and _needs_listing_fallback(candidate.specifications.get("headphone_type")):
        _replace(
            "headphone_type",
            claims.headphone_type,
            f"Listing states type: {claims.headphone_type}. Title: {listing_text[:180]}",
        )
    if claims.anc_support and _needs_listing_fallback(candidate.specifications.get("anc_support")):
        _replace(
            "anc_support",
            claims.anc_support,
            f"Listing states ANC: {claims.anc_support}. Title: {listing_text[:180]}",
        )
    if claims.battery_hours is not None and _needs_listing_fallback(candidate.specifications.get("battery_life")):
        _replace(
            "battery_life",
            f"{claims.battery_hours} hours",
            f"Listing states ~{claims.battery_hours}h battery. Title: {listing_text[:180]}",
        )
    return claims


def _strong_spec(candidate: ProductCandidate, field_name: str):
    record = candidate.specifications.get(field_name)
    if record is None:
        return None
    if (
        record.status == VerificationStatus.VERIFIED
        and record.evidence_strength == EvidenceStrength.STRONG
        and record.value not in (None, "")
    ):
        return record
    return None


def score_candidate(candidate: ProductCandidate) -> tuple[int, list[str], bool]:
    """Match v1 evidence-aware weights: only strong manufacturer specs score.

    ANC +20, headphone type +10, charging port +5, new +3 / used-refurb -5.
    Battery life is recorded but not scored until normalization is reliable.
    Listing-title fallbacks stay weak evidence and earn no points.
    """
    score = 0
    reasons: list[str] = []
    scored_fields: set[str] = set()

    anc = _strong_spec(candidate, "anc_support")
    if anc and str(anc.value).casefold() == "supported":
        score += 20
        reasons.append("+20: manufacturer evidence verifies ANC")
        scored_fields.add("anc_support")
    elif anc and str(anc.value).casefold() == "unsupported":
        reasons.append("ANC unsupported on manufacturer page (no ANC points)")
        scored_fields.add("anc_support")

    htype = _strong_spec(candidate, "headphone_type")
    if htype:
        score += 10
        reasons.append("+10: manufacturer evidence verifies headphone type")
        scored_fields.add("headphone_type")

    port = _strong_spec(candidate, "charging_port")
    if port:
        score += 5
        reasons.append("+5: manufacturer evidence verifies charging port")
        scored_fields.add("charging_port")

    if candidate.condition_status == VerificationStatus.VERIFIED and candidate.condition:
        condition = candidate.condition.casefold()
        if any(token in condition for token in ("refurbished", "used", "pre-owned", "renewed")):
            score -= 5
            reasons.append("-5: verified used/refurbished condition")
        elif condition in {"new", "brand new"}:
            score += 3
            reasons.append("+3: verified new condition")

    weak_claims = [
        field_name
        for field_name, record in candidate.specifications.items()
        if field_name not in scored_fields
        and record.status == VerificationStatus.VERIFIED
        and record.evidence_strength == EvidenceStrength.WEAK
        and record.value not in (None, "")
    ]
    if weak_claims:
        reasons.append(
            "No points awarded for weakly supported claims: " + ", ".join(sorted(set(weak_claims)))
        )

    # Strong manufacturer evidence on the scored feature set (battery excluded).
    strong_scored = sum(
        1 for field_name in ("anc_support", "headphone_type", "charging_port") if _strong_spec(candidate, field_name)
    )
    provisional = strong_scored < 2
    if not reasons:
        reasons.append(
            "No strongly supported scored feature claims; ranked by price and model tie-breakers"
        )
    reasons.append("Battery life not scored: normalization is still under review")
    if candidate.delivered_total_status != VerificationStatus.VERIFIED:
        reasons.append("Delivered total (shipping + tax) is not verified and is not scored")
    return score, reasons, provisional


def _extra_limitations(live: bool) -> list[str]:
    del live
    return [
        "Scores are fixed evidence points (ANC +20, type +10, charging port +5, new +3 / used-refurb -5), not personalized “best battery / best sound / best value” ranking.",
        "Profile focus areas (battery, comfort, sound, value) are descriptive only; they do not reweight scores. Earbuds queries apply prefer_true_wireless as a hard form-factor filter.",
        "Only strong manufacturer evidence scores; listing-title claims stay non-scoring weak evidence.",
        "Battery life is recorded when found and is not scored until normalization is reliable.",
        "Manufacturer family claims only score when compatible with the listing's stated ANC/type; conflicts stay non-scoring context.",
    ]


_CLAIM_TERMS = {
    "headphone_type": re.compile(
        r"\b(?:over[- ]ear|on[- ]ear|in[- ]ear|true wireless|earbuds?|headphones?)\b",
        re.I,
    ),
    "anc_support": re.compile(r"\b(?:ANC|noise cancell|active noise)\b", re.I),
    "battery_life": re.compile(r"\b(?:hours?|battery|playtime|playback)\b", re.I),
    "charging_port": re.compile(r"\b(?:USB[- ]?C|Type-C|Micro-USB|charging port)\b", re.I),
}


def build_profile():
    from shopping_agent.profiles.base import CategoryProfile

    return CategoryProfile(
        id="headphones",
        priorities=HEADPHONE_PRIORITIES,
        spec_fields=SPEC_FIELDS,
        accessory_terms=ACCESSORY_TERMS,
        known_retailer_domains=KNOWN_RETAILER_DOMAINS,
        manufacturer_domains=MANUFACTURER_DOMAINS,
        listing_fixture_path=_FIXTURE_DIR / "headphones_listings.json",
        spec_fixture_path=_FIXTURE_DIR / "headphones_specs.json",
        claim_term_patterns=_CLAIM_TERMS,
        accessory_reject_reason="likely_accessory_not_headphones",
        category_missing_reason="title_lacks_headphones_category_term",
        matches_category=matches_headphones_category,
        discovery_queries=discovery_queries,
        discovery_search_query=discovery_search_query,
        extract_identity=extract_identity,
        looks_like_rejected_fake=looks_like_rejected_fake,
        looks_like_incomplete_offer=looks_like_incomplete_offer,
        incomplete_offer_reject_reason="likely_incomplete_or_replacement_offer",
        page_hints_for_model=page_hints_for_model,
        extract_specs=_extract_specs,
        score_page_fit=_score_page_fit,
        apply_consistency=apply_consistency,
        apply_fallback=apply_fallback,
        score_candidate=score_candidate,
        extra_limitations=_extra_limitations,
        request_fit=request_fit,
    )


PROFILE = build_profile()
