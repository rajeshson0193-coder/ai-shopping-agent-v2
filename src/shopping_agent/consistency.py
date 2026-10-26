"""Gate manufacturer datasheet claims against the listing's stated configuration.

Family pages often list "up to 16GB" / multiple CPU options. Those must not earn
ranking points for an offer that clearly states a different config in its title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    VerificationStatus,
)

_RAM_RE = re.compile(r"\b(\d{1,3})\s*GB\s*(?:RAM|ddr\d|lpddr\d|memory)?\b", re.I)
_STORAGE_RE = re.compile(
    r"\b(\d+)\s*(GB|TB)\s*(?:PCIe\s+)?(?:NVMe\s+)?(?:M\.2\s+)?(SSD|HDD|eMMC|UFS|STORAGE|HD)\b",
    re.I,
)
# Common listing shorthand: "16GB / 512GB" or "16GB RAM / 512GB" without SSD/HDD keyword.
_RAM_SLASH_STORAGE_RE = re.compile(
    r"\b(\d{1,3})\s*GB(?:\s*(?:RAM|ddr\d|lpddr\d|memory))?\s*[\/\|]\s*(\d+)\s*(GB|TB)\b",
    re.I,
)
_BARE_RAM_STORAGE_RE = re.compile(
    r"\b(\d{1,2})\s*GB\s+(\d+)\s*(GB|TB)\s*(SSD|HDD|eMMC|UFS|STORAGE|HD)\b",
    re.I,
)
_CPU_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(core\s+ultra\s+[3579](?:-\d{3,5}\w*)?)\b", re.I),
    re.compile(r"\b(core\s*i[3579](?:-\d{3,5}\w*)?)\b", re.I),
    re.compile(r"\b(i[3579]-\d{3,5}\w*)\b", re.I),  # bare title form: i5-1334U
    re.compile(r"\b(ryzen\s*[3579](?:\s+\d{3,5}\w*)?)\b", re.I),
    re.compile(r"\b(pentium(?:\s+(?:silver|gold))?(?:\s+[a-z]?\d{4,}\w*)?)\b", re.I),
    re.compile(r"\b(celeron(?:\s+[a-z]?\d{4,}\w*)?)\b", re.I),
    re.compile(r"\b(athlon(?:\s+[a-z]?\d{4,}\w*)?)\b", re.I),
    re.compile(r"\b(a(?:10|8|6|4)-\d{4}[a-z]?)\b", re.I),  # older AMD A-series
    re.compile(r"\b(apple\s+m[1-4](?:\s+pro|\s+max)?)\b", re.I),
    re.compile(r"\b(n\d{4}[a-z]?)\b", re.I),  # Pentium/Celeron N5030-style ids
)


@dataclass(frozen=True)
class ListingClaims:
    ram_gb: int | None = None
    storage_gb: int | None = None
    storage_kind: str | None = None
    cpu_tokens: tuple[str, ...] = ()


def _listing_text(candidate: ProductCandidate) -> str:
    parts = [candidate.name or "", candidate.configuration or ""]
    return " ".join(part for part in parts if part).strip()


def _to_gb(amount: int, unit: str) -> int:
    return amount * 1024 if unit.upper() == "TB" else amount


def extract_listing_claims(candidate: ProductCandidate) -> ListingClaims:
    text = _listing_text(candidate)
    if not text:
        return ListingClaims()

    ram_gb = None
    ram_match = _RAM_RE.search(text)
    if ram_match:
        ram_gb = int(ram_match.group(1))

    storage_gb = None
    storage_kind = None
    storage_match = _STORAGE_RE.search(text)
    if storage_match:
        storage_gb = _to_gb(int(storage_match.group(1)), storage_match.group(2))
        kind = storage_match.group(3).upper()
        if kind in {"STORAGE"}:
            storage_kind = "SSD"
        elif kind == "HD":
            storage_kind = "HDD"
        else:
            storage_kind = kind
    else:
        slash_match = _RAM_SLASH_STORAGE_RE.search(text)
        bare_match = _BARE_RAM_STORAGE_RE.search(text)
        if slash_match:
            if ram_gb is None:
                ram_gb = int(slash_match.group(1))
            storage_gb = _to_gb(int(slash_match.group(2)), slash_match.group(3))
            storage_kind = "SSD"
        elif bare_match:
            if ram_gb is None:
                ram_gb = int(bare_match.group(1))
            storage_gb = _to_gb(int(bare_match.group(2)), bare_match.group(3))
            kind = bare_match.group(4).upper()
            if kind in {"STORAGE"}:
                storage_kind = "SSD"
            elif kind == "HD":
                storage_kind = "HDD"
            else:
                storage_kind = kind

    tokens: list[str] = []
    for pattern in _CPU_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        token = re.sub(r"\s+", " ", match.group(1)).casefold().strip()
        if token and token not in tokens:
            tokens.append(token)
    return ListingClaims(
        ram_gb=ram_gb,
        storage_gb=storage_gb,
        storage_kind=storage_kind,
        cpu_tokens=tuple(tokens),
    )


def _parse_manufacturer_ram(value: object) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"(\d{1,3})", str(value))
    return int(match.group(1)) if match else None


def _parse_manufacturer_storage(value: object) -> tuple[int | None, str | None]:
    if value in (None, ""):
        return None, None
    match = re.search(r"(\d+)\s*(GB|TB)\s*(SSD|HDD|eMMC|UFS)?", str(value), re.I)
    if not match:
        return None, None
    gb = _to_gb(int(match.group(1)), match.group(2))
    kind = match.group(3).upper() if match.group(3) else None
    return gb, kind


def cpu_compatible(listing_tokens: tuple[str, ...], manufacturer_value: object) -> bool:
    if not listing_tokens:
        return False
    mfr = re.sub(r"\s+", " ", str(manufacturer_value or "")).casefold()
    if not mfr:
        return False
    mfr_compact = re.sub(r"[^a-z0-9]", "", mfr)
    for token in listing_tokens:
        compact = re.sub(r"[^a-z0-9]", "", token)
        if token in mfr or compact in mfr_compact:
            return True
        # Bare i5-1334u should match "Intel Core i5-1334U".
        bare = re.fullmatch(r"i([3579]\d{3,5}[a-z]*)", compact)
        if bare and f"corei{bare.group(1)}" in mfr_compact:
            return True
        # Same Core i5 / Ryzen 5 family even when SKU digits differ.
        family = re.match(
            r"(core i[3579]|core ultra [3579]|ryzen [3579]|pentium|celeron|athlon|apple m[1-4])",
            token,
        )
        if family and family.group(1) in mfr:
            sku = re.search(r"(\d{4,5}[a-z]*)$", compact)
            if sku is None:
                return True
            if sku.group(1) in mfr_compact:
                return True
    return False


def _mark_conflict(record: Evidence, detail: str) -> None:
    record.status = VerificationStatus.CONFLICTING
    record.evidence_strength = EvidenceStrength.INSUFFICIENT
    note = f"Conflicts with listing configuration: {detail}"
    record.reason = note if not record.reason else f"{record.reason}. {note}"


def _mark_family_only(record: Evidence, detail: str) -> None:
    """Keep retrieved family context, but do not allow strong scoring."""
    if record.status != VerificationStatus.VERIFIED or record.value in (None, ""):
        return
    record.evidence_strength = EvidenceStrength.WEAK
    note = f"Family datasheet claim is not tied to this offer's configuration: {detail}"
    record.reason = note if not record.reason else f"{record.reason}. {note}"


def apply_listing_consistency(candidate: ProductCandidate) -> ListingClaims:
    claims = extract_listing_claims(candidate)

    cpu = candidate.specifications.get("cpu")
    cpu_conflict = False
    if cpu and cpu.status == VerificationStatus.VERIFIED and cpu.value not in (None, ""):
        if claims.cpu_tokens:
            if not cpu_compatible(claims.cpu_tokens, cpu.value):
                _mark_conflict(
                    cpu,
                    f"listing CPU {', '.join(claims.cpu_tokens)} vs manufacturer {cpu.value}",
                )
                cpu_conflict = True
        else:
            _mark_family_only(cpu, "listing does not state CPU")

    ram = candidate.specifications.get("ram_gb")
    if ram and ram.status == VerificationStatus.VERIFIED and ram.value not in (None, ""):
        mfr_ram = _parse_manufacturer_ram(ram.value)
        if claims.ram_gb is not None and mfr_ram is not None and claims.ram_gb != mfr_ram:
            _mark_conflict(ram, f"listing {claims.ram_gb}GB RAM vs manufacturer {mfr_ram}GB")
        elif cpu_conflict:
            _mark_family_only(
                ram,
                "manufacturer page CPU conflicts with listing, so RAM from that page is not scored",
            )
        elif claims.ram_gb is None:
            _mark_family_only(ram, "listing does not state RAM")

    storage = candidate.specifications.get("storage")
    if storage and storage.status == VerificationStatus.VERIFIED and storage.value not in (None, ""):
        mfr_gb, mfr_kind = _parse_manufacturer_storage(storage.value)
        if claims.storage_gb is not None and mfr_gb is not None and claims.storage_gb != mfr_gb:
            _mark_conflict(
                storage,
                f"listing {claims.storage_gb}GB vs manufacturer {mfr_gb}GB",
            )
        elif (
            claims.storage_kind
            and mfr_kind
            and claims.storage_kind != mfr_kind
            and {claims.storage_kind, mfr_kind} != {"SSD", "UFS"}
        ):
            _mark_conflict(
                storage,
                f"listing {claims.storage_kind} vs manufacturer {mfr_kind}",
            )
        elif cpu_conflict:
            _mark_family_only(
                storage,
                "manufacturer page CPU conflicts with listing, so storage from that page is not scored",
            )
        elif claims.storage_gb is None:
            _mark_family_only(storage, "listing does not state storage")

    # When the datasheet CPU is the wrong chip for this offer, display/GPU/battery
    # from that same page are family context only.
    if cpu_conflict:
        for field_name in ("display", "gpu", "battery"):
            record = candidate.specifications.get(field_name)
            if record is not None:
                _mark_family_only(
                    record,
                    "manufacturer page CPU conflicts with listing, so other specs from that page are not scored",
                )

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


def apply_listing_fallback(candidate: ProductCandidate, claims: ListingClaims | None = None) -> ListingClaims:
    """Use explicit listing title/config when manufacturer evidence is unusable.

    Listing claims stay weak: they are seller-stated, not manufacturer-verified.
    """
    claims = claims or extract_listing_claims(candidate)
    source_url = candidate.product_url
    listing_text = _listing_text(candidate)

    def _replace(field_name: str, value: str, supporting: str) -> None:
        previous = candidate.specifications.get(field_name)
        if previous is not None and previous.value not in (None, ""):
            candidate.evidence.append(previous)
        candidate.specifications[field_name] = Evidence(
            field_name=field_name,
            status=VerificationStatus.VERIFIED,
            value=value,
            source_url=source_url,
            source_type="listing_title",
            supporting_text=supporting,
            evidence_strength=EvidenceStrength.WEAK,
            reason="Explicit listing title/configuration claim used because manufacturer evidence was missing or conflicting",
        )

    if claims.cpu_tokens and _needs_listing_fallback(candidate.specifications.get("cpu")):
        cpu_value = claims.cpu_tokens[0]
        _replace("cpu", cpu_value, f"Listing states CPU: {cpu_value}. Title: {listing_text[:180]}")

    if claims.ram_gb is not None and _needs_listing_fallback(candidate.specifications.get("ram_gb")):
        _replace(
            "ram_gb",
            str(claims.ram_gb),
            f"Listing states {claims.ram_gb}GB RAM. Title: {listing_text[:180]}",
        )

    if claims.storage_gb is not None and _needs_listing_fallback(candidate.specifications.get("storage")):
        if claims.storage_gb % 1024 == 0:
            storage_value = f"{claims.storage_gb // 1024}TB {claims.storage_kind or 'SSD'}"
        else:
            storage_value = f"{claims.storage_gb}GB {claims.storage_kind or 'SSD'}"
        _replace(
            "storage",
            storage_value,
            f"Listing states {storage_value}. Title: {listing_text[:180]}",
        )
    return claims
