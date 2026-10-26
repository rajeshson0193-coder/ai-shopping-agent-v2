"""UI helper recovery paths (no Streamlit server required)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from shopping_agent.pipeline import run_research
from ui.helpers import (
    SCORING_DISCLAIMER,
    format_evidence_points,
    format_pipeline_error,
    parse_budget,
    run_pipeline,
    scoring_disclaimer_lines,
)


def test_format_evidence_points_labels_fixed_heuristic():
    assert format_evidence_points(33) == "evidence points 33"
    assert "score" not in format_evidence_points(10).casefold()


def test_scoring_disclaimer_prefers_report_limitations():
    assert "fixed evidence" in SCORING_DISCLAIMER.casefold()
    assert "personalized" in SCORING_DISCLAIMER.casefold()
    lines = scoring_disclaimer_lines(
        {
            "limitations": [
                "Scores are fixed evidence points, not personalized ranking.",
                "SerpApi is capped at 5 HTTP calls per run.",
            ]
        }
    )
    assert any("fixed evidence" in line.casefold() for line in lines)
    assert all("SerpApi" not in line for line in lines)


def test_scoring_disclaimer_falls_back_when_report_silent():
    assert scoring_disclaimer_lines(None) == [SCORING_DISCLAIMER]
    assert scoring_disclaimer_lines({"limitations": []}) == [SCORING_DISCLAIMER]


def test_parse_budget_blank_means_use_query():
    assert parse_budget("") is None
    assert parse_budget("   ") is None
    assert parse_budget(None) is None


def test_parse_budget_valid_override():
    assert parse_budget("100") == Decimal("100")
    assert parse_budget("$75.50") == Decimal("75.50")


def test_parse_budget_invalid_override_raises():
    with pytest.raises(ValueError, match="Invalid budget override"):
        parse_budget("abc")
    with pytest.raises(ValueError, match="Invalid budget override"):
        parse_budget("-5")


def test_format_pipeline_error_live_discovery_failure_suggests_ebay_or_fixtures():
    exc = RuntimeError(
        "No discovery sources available. Use fixtures (default) or set API keys with --live."
    )
    message = format_pipeline_error(exc, live=True)
    assert "Live discovery has no usable sources" in message
    assert "EBAY_CLIENT_ID" in message
    assert "Fixtures" in message


def test_format_pipeline_error_passes_through_value_error():
    message = format_pipeline_error(ValueError("Unsupported category 'phone'."), live=True)
    assert message == "Unsupported category 'phone'."


def test_live_pipeline_without_credentials_raises_runtime_error(monkeypatch):
    """Matches ShopBuddy Live defaults: live=True, use_fixtures=False."""
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="No discovery sources available"):
        run_research(
            "best wireless earbuds under 100",
            live=True,
            use_fixtures=False,
            skip_serpapi=True,
        )

    with pytest.raises(RuntimeError, match="No discovery sources available"):
        run_pipeline(
            "best wireless earbuds under 100",
            budget=None,
            live=True,
            include_serpapi=False,
        )

    # UI layer turns that into a controlled recovery string (home.py catches it).
    try:
        run_pipeline(
            "best wireless earbuds under 100",
            budget=None,
            live=True,
            include_serpapi=False,
        )
    except RuntimeError as exc:
        message = format_pipeline_error(exc, live=True)
    else:
        raise AssertionError("expected RuntimeError from live discovery")

    assert "switch Mode to Fixtures" in message
    assert "EBAY_CLIENT_ID" in message
