from decimal import Decimal

from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    QualityStatus,
    ShoppingRequest,
    VerificationStatus,
)
from shopping_agent.profiles.headphones import PROFILE as HEADPHONES
from shopping_agent.profiles.laptops import PROFILE as LAPTOPS
from shopping_agent.rank import limitations, rank_candidates


def _laptop(model: str, price: str, ram: str = "16", *, weak_display: bool = False) -> ProductCandidate:
    display_strength = EvidenceStrength.WEAK if weak_display else EvidenceStrength.STRONG
    display_text = "Skip to content Menu Related products" if weak_display else "15.6-inch FHD display"
    return ProductCandidate(
        name=f"{model} Laptop",
        model=model,
        product_url=f"https://www.ebay.com/itm/{model.casefold().replace(' ', '-')}",
        source="ebay",
        listed_price=Decimal(price),
        price_status=VerificationStatus.VERIFIED,
        condition="new",
        condition_status=VerificationStatus.VERIFIED,
        quality_status=QualityStatus.ELIGIBLE,
        specifications={
            "ram_gb": Evidence(
                field_name="ram_gb",
                status=VerificationStatus.VERIFIED,
                value=ram,
                source_url="https://www.lenovo.com/example",
                supporting_text=f"{ram} GB RAM memory",
                evidence_strength=EvidenceStrength.STRONG,
            ),
            "display": Evidence(
                field_name="display",
                status=VerificationStatus.VERIFIED,
                value="15.6-inch FHD",
                source_url="https://www.lenovo.com/example",
                supporting_text=display_text,
                evidence_strength=display_strength,
            ),
        },
    )


def test_limitations_state_priorities_are_descriptive_not_personalized():
    headphone_lines = limitations(HEADPHONES, live=False)
    laptop_lines = limitations(LAPTOPS, live=False)
    joined_h = " ".join(headphone_lines).casefold()
    joined_l = " ".join(laptop_lines).casefold()
    assert "descriptive" in joined_h
    assert "personalized" in joined_h or "do not reweight" in joined_h
    assert "fixed evidence" in joined_h
    assert "descriptive" in joined_l
    assert "do not reweight" in joined_l


def test_weak_display_does_not_receive_points():
    request = ShoppingRequest(raw_text="best laptop under $1000", category="laptop", budget=Decimal("1000"))
    strong = _laptop("Lenovo IdeaPad Slim 3", "649.00")
    weak = _laptop("Samsung Galaxy Book4", "899.00", weak_display=True)
    result = rank_candidates(request, [strong, weak], limit=5)
    by_model = {item.candidate.model: item for item in result.ranked}
    assert by_model["Lenovo IdeaPad Slim 3"].score > by_model["Samsung Galaxy Book4"].score
    assert any("weakly supported" in reason for reason in by_model["Samsung Galaxy Book4"].reasons)


def test_unverified_price_is_excluded():
    request = ShoppingRequest(raw_text="best laptop under $1000", category="laptop", budget=Decimal("1000"))
    candidate = _laptop("Dell Inspiron 15", "429.00")
    candidate.price_status = VerificationStatus.UNKNOWN
    result = rank_candidates(request, [candidate], limit=5)
    assert result.ranked == []
    assert result.excluded[0]["reason"] == "price_status_unknown"


def test_same_model_family_dedupes_even_when_configuration_differs():
    request = ShoppingRequest(raw_text="best laptop under $1000", category="laptop", budget=Decimal("1000"))
    cheap = _laptop("Lenovo IdeaPad Slim 3", "259.00", "16")
    cheap.configuration = "16GB RAM / 512GB SSD"
    expensive = _laptop("Lenovo IdeaPad Slim 3", "529.00", "16")
    expensive.configuration = None
    expensive.product_url = "https://www.ebay.com/itm/ideapad-slim-3-b"
    result = rank_candidates(request, [cheap, expensive], limit=5)
    assert len(result.ranked) == 1
    assert result.ranked[0].candidate.product_url == cheap.product_url
    assert result.duplicate_offers
    assert "same model family" in result.duplicate_offers[0]["reason"]
