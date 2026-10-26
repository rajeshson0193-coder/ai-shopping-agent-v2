"""Re-research + validate + rank the latest report recommendations."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from shopping_agent.http_fetch import fetch_page
from shopping_agent.models import (
    ProductCandidate,
    QualityStatus,
    ShoppingRequest,
    VerificationStatus,
)
from shopping_agent.rank import rank_candidates
from shopping_agent.research import research_candidates
from shopping_agent.validate import validate_candidates


def main() -> None:
    data = json.loads(Path("output/latest_report.json").read_text(encoding="utf-8"))
    candidates = []
    for rec in data["recommendations"]:
        candidates.append(
            ProductCandidate(
                name=rec["name"],
                model=rec.get("model"),
                configuration=rec.get("configuration"),
                product_url=rec["product_url"],
                source=rec.get("source") or "ebay",
                listed_price=Decimal(rec["listed_price"]),
                currency="USD",
                price_status=VerificationStatus.VERIFIED,
                condition=rec.get("condition"),
                condition_status=VerificationStatus(rec.get("condition_status") or "unknown"),
                quality_status=QualityStatus.ELIGIBLE,
            )
        )

    print(f"Re-researching {len(candidates)} offers (live manufacturer fetch)...")
    research_candidates(candidates, live=True, timeout=45, fetch=fetch_page)
    validate_candidates(candidates, live=False)
    request = ShoppingRequest(
        raw_text="best laptop under 1000",
        category="laptop",
        budget=Decimal("1000"),
    )
    result = rank_candidates(request, candidates, limit=5)
    print("=== RE-SCORED ===")
    for index, item in enumerate(result.ranked, 1):
        candidate = item.candidate
        print(f"#{index} score={item.score} prov={item.provisional} | {candidate.listed_price} | {candidate.model}")
        print("  ", (candidate.name or "")[:90])
        for key in ("cpu", "ram_gb", "storage"):
            record = candidate.specifications.get(key)
            if not record:
                continue
            print(f"   {key}: {record.status.value}/{record.evidence_strength.value}/{record.source_type} = {record.value}")
        for reason in item.reasons:
            if reason.startswith("+") or reason.startswith("-"):
                print("  ", reason)


if __name__ == "__main__":
    main()
