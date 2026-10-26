"""Claim↔model binding for extraction windows and evidence audit."""

from __future__ import annotations

from shopping_agent.evidence_context import (
    claim_near_model,
    looks_like_cable_not_port,
    model_local_text,
    preparation_text_for_extraction,
    supporting_text_tied_to_model,
)
from shopping_agent.models import (
    Evidence,
    EvidenceStrength,
    ProductCandidate,
    VerificationStatus,
)
from shopping_agent.profiles.headphones import extract_headphone_specs
from shopping_agent.profiles.registry import get_profile
from shopping_agent.validate import audit_evidence


def test_model_local_text_drops_distant_footer_categories():
    text = (
        "Skullcandy SESH ANC product help. Active Noise Cancellation for SESH ANC. "
        + ("unrelated padding " * 80)
        + "Footer Over Ear Headphones True Wireless Earbuds Waterproof Earbuds"
    )
    local = model_local_text(text, "Skullcandy SESH ANC", radius=200)
    assert "SESH ANC" in local
    assert "Over Ear Headphones" not in local


def test_footer_type_not_extracted_when_model_is_known():
    text = (
        "Soundcore P30i Wireless Earbuds with ANC. "
        + ("x " * 400)
        + "Footer Over Ear Headphones Workout Headphones"
    )
    candidate = ProductCandidate(
        name="Soundcore P30i",
        model="Soundcore P30i",
        product_url="https://www.ebay.com/itm/p30i",
        source="ebay",
    )
    specs = extract_headphone_specs(text, candidate)
    assert specs["headphone_type"][0] == "true wireless earbuds"
    # Distant over-ear footer must not win when model context is available.
    assert specs["headphone_type"][0] != "over-ear headphones"


def test_cable_snippet_is_not_strong_port_evidence():
    profile = get_profile("headphones")
    record = Evidence(
        field_name="charging_port",
        status=VerificationStatus.VERIFIED,
        value="USB-C",
        source_url="https://www.skullcandy.com/blogs/product-help/sesh-anc",
        source_type="manufacturer_page",
        supporting_text="CASE : Plug in the USB-C Rapid Charge cable and connect to a computer.",
    )
    assert looks_like_cable_not_port(record.supporting_text)
    audited = audit_evidence(record, profile, model="Skullcandy SESH ANC")
    assert audited.evidence_strength == EvidenceStrength.WEAK
    assert "cable" in (audited.reason or "").casefold()


def test_manufacturer_snippet_without_model_is_weak():
    profile = get_profile("headphones")
    record = Evidence(
        field_name="anc_support",
        status=VerificationStatus.VERIFIED,
        value="supported",
        source_url="https://www.example.com/support",
        source_type="manufacturer_page",
        supporting_text="Active Noise Cancellation and Stay-Aware Mode.",
    )
    assert not supporting_text_tied_to_model(record.supporting_text, "Skullcandy SESH ANC")
    audited = audit_evidence(record, profile, model="Skullcandy SESH ANC")
    assert audited.evidence_strength == EvidenceStrength.WEAK
    assert "not clearly tied" in (audited.reason or "").casefold()


def test_manufacturer_snippet_with_model_can_be_strong():
    profile = get_profile("headphones")
    record = Evidence(
        field_name="anc_support",
        status=VerificationStatus.VERIFIED,
        value="supported",
        source_url="https://www.skullcandy.com/blogs/product-help/sesh-anc",
        source_type="manufacturer_page",
        supporting_text="Sesh ANC features both Active Noise Cancellation and Stay-Aware Mode.",
    )
    audited = audit_evidence(record, profile, model="Skullcandy SESH ANC")
    assert audited.evidence_strength == EvidenceStrength.STRONG


def test_claim_near_model_and_preparation_text():
    text = "Intro. Soundcore P30i earbuds. USB-C charging port on the case."
    assert claim_near_model(text, text.index("USB-C"), text.index("USB-C") + 5, "Soundcore P30i")
    prepared = preparation_text_for_extraction(text + (" pad" * 300) + " distant Over Ear", "Soundcore P30i")
    assert "P30i" in prepared
    assert "distant Over Ear" not in prepared
