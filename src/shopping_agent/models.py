"""Shared data types for the research pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"
    INACCESSIBLE = "inaccessible"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class QualityStatus(str, Enum):
    ELIGIBLE = "eligible"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ShoppingRequest:
    raw_text: str
    category: str
    budget: Decimal
    market: str = "US"
    currency: str = "USD"
    priorities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("category must not be empty")
        if self.budget < 0:
            raise ValueError("budget cannot be negative")
        if self.market == "US" and self.currency != "USD":
            raise ValueError("US-market requests currently require USD")


@dataclass
class Evidence:
    field_name: str
    status: VerificationStatus
    value: Any = None
    source_url: str | None = None
    source_type: str | None = None
    supporting_text: str | None = None
    retrieved_at: datetime = field(default_factory=utc_now)
    evidence_strength: EvidenceStrength = EvidenceStrength.INSUFFICIENT
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "status": self.status.value,
            "value": str(self.value) if isinstance(self.value, Decimal) else self.value,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "supporting_text": self.supporting_text,
            "retrieved_at": self.retrieved_at.isoformat(),
            "evidence_strength": self.evidence_strength.value,
            "reason": self.reason,
        }


@dataclass
class ProductCandidate:
    name: str
    product_url: str
    source: str
    brand: str | None = None
    model: str | None = None
    configuration: str | None = None
    listed_price: Decimal | None = None
    currency: str = "USD"
    price_status: VerificationStatus = VerificationStatus.UNKNOWN
    delivered_total: Decimal | None = None
    delivered_total_status: VerificationStatus = VerificationStatus.UNKNOWN
    condition: str | None = None
    condition_status: VerificationStatus = VerificationStatus.UNKNOWN
    quality_status: QualityStatus = QualityStatus.NEEDS_REVIEW
    quality_reasons: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    specifications: dict[str, Evidence] = field(default_factory=dict)

    @property
    def identity_key(self) -> str | None:
        if not self.model:
            return None
        parts = [self.model.casefold()]
        if self.configuration:
            parts.append(self.configuration.casefold())
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "configuration": self.configuration,
            "product_url": self.product_url,
            "source": self.source,
            "listed_price": str(self.listed_price) if self.listed_price is not None else None,
            "currency": self.currency,
            "price_status": self.price_status.value,
            "delivered_total": str(self.delivered_total) if self.delivered_total is not None else None,
            "delivered_total_status": self.delivered_total_status.value,
            "condition": self.condition,
            "condition_status": self.condition_status.value,
            "quality_status": self.quality_status.value,
            "quality_reasons": list(self.quality_reasons),
            "evidence": [item.to_dict() for item in self.evidence],
            "specifications": {key: value.to_dict() for key, value in self.specifications.items()},
        }


@dataclass
class RankedProduct:
    candidate: ProductCandidate
    score: int
    reasons: list[str]
    provisional: bool

    def to_dict(self, rank: int) -> dict[str, Any]:
        payload = self.candidate.to_dict()
        payload.update(
            {
                "rank": rank,
                "score": self.score,
                "reasons": list(self.reasons),
                "provisional": self.provisional,
            }
        )
        return payload


@dataclass
class PipelineResult:
    request: ShoppingRequest
    recommendations: list[RankedProduct]
    excluded: list[dict[str, Any]]
    duplicate_offers: list[dict[str, Any]]
    source_errors: dict[str, str]
    limitations: list[str]
    stages_run: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request": {
                "raw_text": self.request.raw_text,
                "category": self.request.category,
                "budget": str(self.request.budget),
                "currency": self.request.currency,
                "market": self.request.market,
                # Descriptive category focus areas — not ranking weights.
                "priorities": list(self.request.priorities),
                "priorities_role": "descriptive_category_focus_only",
            },
            "stages_run": list(self.stages_run),
            "recommendations": [
                item.to_dict(rank) for rank, item in enumerate(self.recommendations, start=1)
            ],
            "excluded": list(self.excluded),
            "duplicate_offers": list(self.duplicate_offers),
            "source_errors": dict(self.source_errors),
            "limitations": list(self.limitations),
        }
