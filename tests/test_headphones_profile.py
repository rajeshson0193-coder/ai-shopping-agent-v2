from shopping_agent.identify import identify_candidates
from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    QualityStatus,
    VerificationStatus,
)
from shopping_agent.profiles.headphones import (
    extract_headphone_specs,
    extract_identity,
    score_candidate,
)
from shopping_agent.profiles.registry import get_profile, match_profile, supported_category_ids


def test_registry_lists_laptop_and_headphones():
    assert "laptop" in supported_category_ids()
    assert "headphones" in supported_category_ids()
    assert match_profile("wireless earbuds").id == "headphones"
    assert get_profile("headphones").id == "headphones"


def test_earbud_discovery_queries_prefer_true_wireless():
    from shopping_agent.models import ShoppingRequest
    from shopping_agent.profiles.headphones import discovery_queries
    from decimal import Decimal

    request = ShoppingRequest(
        raw_text="best wireless earbuds under 100",
        category="headphones",
        budget=Decimal("100"),
        constraints=["prefer_true_wireless"],
    )
    queries = discovery_queries(request)
    joined = " ".join(queries).casefold()
    assert "earbuds" in joined or "buds" in joined
    assert "q20i" not in joined
    assert "ch520" not in joined


def test_request_fit_rejects_over_ear_for_earbuds_query():
    from shopping_agent.models import ShoppingRequest
    from shopping_agent.profiles.headphones import request_fit
    from decimal import Decimal

    request = ShoppingRequest(
        raw_text="best wireless earbuds under 100",
        category="headphones",
        budget=Decimal("100"),
        constraints=["prefer_true_wireless"],
    )
    over_ear = ProductCandidate(
        name="Soundcore Q20i Wireless Noise Cancelling Over-Ear Headphones",
        model="Soundcore Q20i",
        configuration="over-ear headphones / ANC",
        product_url="https://www.ebay.com/itm/q20i",
        source="ebay",
    )
    buds = ProductCandidate(
        name="JBL Vibe Beam 2 True Wireless Earbuds ANC",
        model="JBL Vibe Beam 2",
        configuration="true wireless earbuds / ANC",
        product_url="https://www.ebay.com/itm/vibe-beam-2",
        source="ebay",
    )
    assert request_fit(over_ear, request) == "form_factor_mismatch_for_earbuds_query"
    assert request_fit(buds, request) is None


def test_extracts_headphone_identity():
    brand, model, configuration = extract_identity(
        "Soundcore by Anker Q20i Hybrid Active Noise Cancelling Headphones, 40H Playtime"
    )
    assert brand == "Soundcore"
    assert model == "Soundcore Q20i"
    assert configuration is not None
    assert "ANC" in configuration


def test_does_not_canonicalize_unsupported_model_variants():
    """Exact SKU variants must not inherit a shorter allow-listed model's identity."""
    # SESH ANC Active is a different SKU (page hints warn about this).
    assert extract_identity("Skullcandy Sesh ANC Active True Wireless Earbuds") == (
        None,
        None,
        "true wireless earbuds / ANC",
    )
    assert extract_identity("Skullcandy SESH ANC Active")[1] is None

    # Base SESH ANC still matches, including "Active Noise Cancelling" wording.
    assert extract_identity("Skullcandy SESH ANC True Wireless Earbuds")[1] == (
        "Skullcandy SESH ANC"
    )
    assert extract_identity(
        "Skullcandy SESH ANC Active Noise Cancelling True Wireless Earbuds"
    )[1] == "Skullcandy SESH ANC"

    # Tune Beam 2 must not collapse to Tune Beam (Vibe Beam 2 is intentionally listed).
    assert extract_identity("JBL Tune Beam 2 True Wireless Earbuds ANC")[1] is None
    assert extract_identity("JBL Tune Beam True Wireless Earbuds")[1] == "JBL Tune Beam"
    assert extract_identity("JBL Vibe Beam 2 True Wireless Earbuds")[1] == (
        "JBL Vibe Beam 2"
    )

    # Longer allow-listed stems still win (Q20i Plus before Q20i).
    assert extract_identity("Soundcore Q20i Plus Wireless Headphones")[1] == (
        "Soundcore Q20i Plus"
    )

    # Unlisted edition suffix on an allow-listed stem → no model (no wrong hints).
    assert extract_identity("Sony WH-CH520 Pro Wireless Headphones")[1] is None


def test_rejects_headphone_accessories():
    profile = get_profile("headphones")
    candidates = identify_candidates(
        [
            ProductCandidate(
                name="Replacement ear tips for wireless earbuds silicone 3 sizes",
                product_url="https://www.ebay.com/itm/fixture-ear-tips",
                source="ebay",
            )
        ],
        profile=profile,
    )
    assert candidates[0].quality_status == QualityStatus.REJECTED
    assert profile.accessory_reject_reason in candidates[0].quality_reasons


def test_rejects_single_earbud_replacement_even_with_recognized_model():
    """Model recognition alone must not make a parts-only listing eligible."""
    from shopping_agent.profiles.headphones import looks_like_incomplete_offer

    title = (
        "Sony WF-C700N Earbud Replacement RIGHT Side Wireless WFC700N Ear Bud Black - New"
    )
    assert looks_like_incomplete_offer(title)

    profile = get_profile("headphones")
    brand, model, _ = extract_identity(title)
    assert brand == "Sony"
    assert model == "Sony WF-C700N"

    candidates = identify_candidates(
        [
            ProductCandidate(
                name=title,
                product_url="https://www.ebay.com/itm/sony-wf-c700n-right-replacement",
                source="ebay",
            )
        ],
        profile=profile,
    )
    assert candidates[0].quality_status == QualityStatus.REJECTED
    assert profile.incomplete_offer_reject_reason in candidates[0].quality_reasons
    # Identity kept for diagnostics; offer stays rejected.
    assert candidates[0].model == "Sony WF-C700N"


def test_incomplete_offer_patterns_cover_common_parts_listings():
    from shopping_agent.profiles.headphones import looks_like_incomplete_offer

    reject = [
        "JBL Tune Beam single left earbud only Black",
        "Skullcandy SESH ANC replacement left bud",
        "Soundcore P30i parts only charging board",
        "Sony WF-C700N Left Side earbud replacement",
    ]
    keep = [
        "Sony WF-C700N True Wireless Noise Cancelling Earbuds Black - New",
        "JBL Vibe Beam 2 left and right earbuds with charging case",
        "Samsung Galaxy Buds FE wireless earbuds complete pair",
    ]
    for title in reject:
        assert looks_like_incomplete_offer(title), title
    for title in keep:
        assert not looks_like_incomplete_offer(title), title

    profile = get_profile("headphones")
    complete = identify_candidates(
        [
            ProductCandidate(
                name=keep[0],
                product_url="https://www.ebay.com/itm/sony-wf-c700n-complete",
                source="ebay",
            )
        ],
        profile=profile,
    )
    assert complete[0].quality_status == QualityStatus.ELIGIBLE
    assert complete[0].model == "Sony WF-C700N"


def test_extracts_headphone_specs_from_page_text():
    text = (
        "Soundcore Q20i over-ear headphones with Hybrid Active Noise Cancelling. "
        "Up to 40 hours of playtime battery life. USB-C charging port."
    )
    specs = extract_headphone_specs(text)
    assert specs["headphone_type"][0] == "over-ear headphones"
    assert specs["anc_support"][0] == "supported"
    assert specs["battery_life"][0] == "40 hours"
    assert specs["charging_port"][0] == "USB-C"


def test_p30i_page_hints_use_live_product_urls():
    from shopping_agent.profiles.headphones import MODEL_PAGE_HINTS

    hints = MODEL_PAGE_HINTS["soundcore p30i"]
    assert hints[0] == "https://www.soundcore.com/products/soundcore-p30i"
    assert "a3959" in hints[1]
    assert "a3957" not in " ".join(hints)
    assert "/products/p30i" not in " ".join(hints)


def test_type_extraction_prefers_product_title_over_footer_categories():
    text = (
        "soundcore P30i Wireless Earbuds - soundcore US "
        "Strong and Smart Noise Cancelling: Reduce noise by up to 42dB with an "
        "advanced active noise cancelling system. "
        "Long Playtime: Enjoy 10 hours of listening from a single charge. "
        "Footer Headphones Over Ear Headphones Workout Headphones "
        "True Wireless Earbuds Waterproof Earbuds"
    )
    specs = extract_headphone_specs(text)
    assert specs["headphone_type"][0] == "true wireless earbuds"
    assert specs["anc_support"][0] == "supported"


def test_sesh_anc_support_page_type_anc_and_usb_c():
    """Cable-only USB-C wording must not verify charging_port (type/ANC still can)."""
    text = (
        "SESH® ANC product help. To identify your True Wireless product, the product "
        "name will be printed inside the charging case. "
        "Sesh ANC features both Active Noise Cancellation and Stay-Aware Mode. "
        "CASE : Plug in the USB-C Rapid Charge cable and connect to a computer."
    )
    specs = extract_headphone_specs(text)
    assert specs["headphone_type"][0] == "true wireless earbuds"
    assert specs["anc_support"][0] == "supported"
    assert specs["charging_port"][0] is None


def test_sesh_anc_hints_avoid_active_sku():
    from shopping_agent.profiles.headphones import MODEL_PAGE_HINTS

    hints = MODEL_PAGE_HINTS["skullcandy sesh anc"]
    assert hints
    assert "sesh-anc" in hints[0]
    assert not any("active" in url.casefold() for url in hints)


def test_scoring_matches_v1_strong_manufacturer_weights():
    candidate = ProductCandidate(
        name="JBL Vibe Beam 2 True Wireless Earbuds ANC",
        model="JBL Vibe Beam 2",
        product_url="https://www.ebay.com/itm/fixture-jbl",
        source="ebay",
        condition="New",
        condition_status=VerificationStatus.VERIFIED,
        quality_status=QualityStatus.ELIGIBLE,
        specifications={
            "anc_support": Evidence(
                field_name="anc_support",
                status=VerificationStatus.VERIFIED,
                value="supported",
                source_url="https://www.jbl.com/example",
                supporting_text="Active Noise Cancelling (ANC) supported",
                evidence_strength=EvidenceStrength.STRONG,
            ),
            "headphone_type": Evidence(
                field_name="headphone_type",
                status=VerificationStatus.VERIFIED,
                value="true wireless earbuds",
                source_url="https://www.jbl.com/example",
                supporting_text="True wireless earbuds",
                evidence_strength=EvidenceStrength.STRONG,
            ),
            "charging_port": Evidence(
                field_name="charging_port",
                status=VerificationStatus.VERIFIED,
                value="USB-C",
                source_url="https://www.jbl.com/example",
                supporting_text="USB-C charging port",
                evidence_strength=EvidenceStrength.STRONG,
            ),
            "battery_life": Evidence(
                field_name="battery_life",
                status=VerificationStatus.VERIFIED,
                value="32 hours",
                source_url="https://www.jbl.com/example",
                supporting_text="Up to 32 hours battery playback",
                evidence_strength=EvidenceStrength.STRONG,
            ),
        },
    )
    score, reasons, provisional = score_candidate(candidate)
    assert score == 38  # 20 ANC + 10 type + 5 port + 3 new
    assert provisional is False
    assert any("+20:" in reason for reason in reasons)
    assert any("+10:" in reason for reason in reasons)
    assert any("+5:" in reason for reason in reasons)
    assert any("Battery life not scored" in reason for reason in reasons)


def test_listing_title_claims_do_not_score():
    candidate = ProductCandidate(
        name="Sony WH-CH520 Wireless On-Ear Bluetooth Headphones",
        model="Sony WH-CH520",
        product_url="https://www.ebay.com/itm/fixture-sony",
        source="ebay",
        condition="New",
        condition_status=VerificationStatus.VERIFIED,
        quality_status=QualityStatus.ELIGIBLE,
        specifications={
            "headphone_type": Evidence(
                field_name="headphone_type",
                status=VerificationStatus.VERIFIED,
                value="on-ear headphones",
                source_url="https://www.ebay.com/itm/fixture-sony",
                source_type="listing_title",
                supporting_text="Listing states on-ear headphones",
                evidence_strength=EvidenceStrength.WEAK,
            ),
            "anc_support": Evidence(
                field_name="anc_support",
                status=VerificationStatus.VERIFIED,
                value="supported",
                source_url="https://www.ebay.com/itm/fixture-sony",
                source_type="listing_title",
                supporting_text="Listing states ANC",
                evidence_strength=EvidenceStrength.WEAK,
            ),
        },
    )
    score, reasons, provisional = score_candidate(candidate)
    assert score == 3  # new condition only
    assert provisional is True
    assert any("weakly supported claims" in reason for reason in reasons)
