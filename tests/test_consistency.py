from decimal import Decimal

from shopping_agent.consistency import apply_listing_consistency, extract_listing_claims
from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    QualityStatus,
    ShoppingRequest,
    VerificationStatus,
)
from shopping_agent.rank import rank_candidates
from shopping_agent.validate import validate_candidates


def _candidate(
    name: str,
    *,
    model: str,
    configuration: str | None,
    ram: str,
    storage: str,
    cpu: str,
    price: str = "299.00",
) -> ProductCandidate:
    return ProductCandidate(
        name=name,
        model=model,
        configuration=configuration,
        product_url="https://www.ebay.com/itm/consistency-example",
        source="ebay",
        listed_price=Decimal(price),
        price_status=VerificationStatus.VERIFIED,
        condition="New",
        condition_status=VerificationStatus.VERIFIED,
        quality_status=QualityStatus.ELIGIBLE,
        specifications={
            "ram_gb": Evidence(
                field_name="ram_gb",
                status=VerificationStatus.VERIFIED,
                value=ram,
                source_url="https://psref.lenovo.com/example.pdf",
                supporting_text=f"{ram} GB RAM memory",
                evidence_strength=EvidenceStrength.STRONG,
            ),
            "storage": Evidence(
                field_name="storage",
                status=VerificationStatus.VERIFIED,
                value=storage,
                source_url="https://psref.lenovo.com/example.pdf",
                supporting_text=f"{storage} storage",
                evidence_strength=EvidenceStrength.STRONG,
            ),
            "cpu": Evidence(
                field_name="cpu",
                status=VerificationStatus.VERIFIED,
                value=cpu,
                source_url="https://psref.lenovo.com/example.pdf",
                supporting_text=f"Processor {cpu}",
                evidence_strength=EvidenceStrength.STRONG,
            ),
        },
    )


def test_extracts_listing_ram_storage_cpu():
    candidate = ProductCandidate(
        name='Lenovo IdeaPad 3 Laptop 15.6" FHD Intel Pentium N5030 4GB RAM 128GB SSD Win 11',
        model="Lenovo IdeaPad Slim 3",
        configuration="4GB RAM / 128GB SSD",
        product_url="https://www.ebay.com/itm/1",
        source="ebay",
    )
    claims = extract_listing_claims(candidate)
    assert claims.ram_gb == 4
    assert claims.storage_gb == 128
    assert claims.storage_kind == "SSD"
    assert any("pentium" in token for token in claims.cpu_tokens)


def test_extracts_slash_storage_without_ssd_keyword():
    candidate = ProductCandidate(
        name='Lenovo IdeaPad Slim 3 Laptop 15.6" FHD Touch / Ryzen 7 5825U / 16GB / 512GB NEW',
        model="Lenovo IdeaPad Slim 3",
        product_url="https://www.ebay.com/itm/slash-storage",
        source="ebay",
    )
    claims = extract_listing_claims(candidate)
    assert claims.ram_gb == 16
    assert claims.storage_gb == 512
    assert claims.storage_kind == "SSD"
    assert any("ryzen" in token for token in claims.cpu_tokens)


def test_extracts_bare_ram_storage_pair():
    candidate = ProductCandidate(
        name="Dell Inspiron 14 7425 2-in-1 Ryzen 7 5825U  16GB 512GB SSD Windows 11 Home",
        model="Dell Inspiron 14 7425",
        product_url="https://www.ebay.com/itm/bare-ram-storage",
        source="ebay",
    )
    claims = extract_listing_claims(candidate)
    assert claims.ram_gb == 16
    assert claims.storage_gb == 512
    assert claims.storage_kind == "SSD"


def test_mismatched_family_ram_becomes_conflicting():
    candidate = _candidate(
        'Lenovo IdeaPad 3 Laptop Intel Pentium N5030 4GB RAM 128GB SSD',
        model="Lenovo IdeaPad Slim 3",
        configuration="4GB RAM / 128GB SSD",
        ram="16",
        storage="1TB SSD",
        cpu="Core i5-13420H",
    )
    apply_listing_consistency(candidate)
    assert candidate.specifications["ram_gb"].status == VerificationStatus.CONFLICTING
    assert candidate.specifications["storage"].status == VerificationStatus.CONFLICTING
    assert candidate.specifications["cpu"].status == VerificationStatus.CONFLICTING
    assert candidate.specifications["ram_gb"].evidence_strength == EvidenceStrength.INSUFFICIENT


def test_compatible_claims_remain_strong_after_validate():
    candidate = _candidate(
        "Dell Inspiron 15 i5-1334U 16GB RAM 512GB SSD",
        model="Dell Inspiron 15",
        configuration="16GB RAM / 512GB SSD",
        ram="16",
        storage="512GB SSD",
        cpu="Intel Core i5-1334U",
    )
    validate_candidates([candidate], category="laptop")
    assert candidate.specifications["ram_gb"].status == VerificationStatus.VERIFIED
    assert candidate.specifications["ram_gb"].evidence_strength == EvidenceStrength.STRONG
    assert candidate.specifications["storage"].evidence_strength == EvidenceStrength.STRONG
    assert candidate.specifications["cpu"].evidence_strength == EvidenceStrength.STRONG


def test_family_only_ram_does_not_score_when_listing_omits_ram():
    request = ShoppingRequest(
        raw_text="best laptop under $1000",
        category="laptop",
        budget=Decimal("1000"),
    )
    candidate = _candidate(
        "HP Pavilion 15 Laptop",
        model="HP Pavilion 15",
        configuration=None,
        ram="16",
        storage="512GB SSD",
        cpu="Intel Core i5-1235U",
        price="400.00",
    )
    # No RAM/storage/CPU in title/configuration beyond model name.
    candidate.name = "HP Pavilion 15 Laptop"
    validate_candidates([candidate], category="laptop")
    assert candidate.specifications["ram_gb"].evidence_strength == EvidenceStrength.WEAK
    result = rank_candidates(request, [candidate], limit=5)
    assert result.ranked[0].score < 15
    assert not any("16GB or more RAM" in reason for reason in result.ranked[0].reasons)


def test_cpu_conflict_blocks_coincidental_ram_match():
    candidate = _candidate(
        "HP Pavilion 15 Notebook AMD A10-5745M 8GB 1TB HD",
        model="HP Pavilion 15",
        configuration=None,
        ram="8",
        storage="256GB SSD",
        cpu="Intel Pentium Gold 7505",
    )
    apply_listing_consistency(candidate)
    assert candidate.specifications["cpu"].status == VerificationStatus.CONFLICTING
    assert candidate.specifications["ram_gb"].evidence_strength == EvidenceStrength.WEAK
    assert candidate.specifications["storage"].status == VerificationStatus.CONFLICTING


def test_listing_fallback_scores_when_manufacturer_conflicts():
    request = ShoppingRequest(
        raw_text="best laptop under $1000",
        category="laptop",
        budget=Decimal("1000"),
    )
    candidate = _candidate(
        "Lenovo IdeaPad Slim 3 Pentium N5030 4GB RAM 128GB SSD",
        model="Lenovo IdeaPad Slim 3",
        configuration="4GB RAM / 128GB SSD",
        ram="16",
        storage="1TB SSD",
        cpu="Core i5-13420H",
        price="259.00",
    )
    validate_candidates([candidate], category="laptop")
    assert candidate.specifications["ram_gb"].source_type == "listing_title"
    assert candidate.specifications["ram_gb"].value == "4"
    assert candidate.specifications["cpu"].source_type == "listing_title"
    result = rank_candidates(request, [candidate], limit=5)
    assert result.ranked[0].score >= 5  # listing CPU/RAM/storage + new condition
    assert any("listing title" in reason for reason in result.ranked[0].reasons)


def test_mismatched_offer_loses_to_compatible_offer():
    request = ShoppingRequest(
        raw_text="best laptop under $1000",
        category="laptop",
        budget=Decimal("1000"),
    )
    mismatched = _candidate(
        "Lenovo IdeaPad Slim 3 Pentium N5030 4GB RAM 128GB SSD",
        model="Lenovo IdeaPad Slim 3",
        configuration="4GB RAM / 128GB SSD",
        ram="16",
        storage="1TB SSD",
        cpu="Core i5-13420H",
        price="259.00",
    )
    compatible = _candidate(
        "Dell Inspiron 15 Core i5-1334U 16GB RAM 512GB SSD",
        model="Dell Inspiron 15",
        configuration="16GB RAM / 512GB SSD",
        ram="16",
        storage="512GB SSD",
        cpu="Intel Core i5-1334U",
        price="500.00",
    )
    compatible.product_url = "https://www.ebay.com/itm/compatible"
    validate_candidates([mismatched, compatible], category="laptop")
    result = rank_candidates(request, [mismatched, compatible], limit=5)
    assert result.ranked[0].candidate.model == "Dell Inspiron 15"
    assert result.ranked[0].score > result.ranked[1].score
