from decimal import Decimal

import pytest

from shopping_agent.parse import default_budget_for_category, parse_budget_arg, parse_request


def test_parses_best_laptop_under_1000():
    request = parse_request("best laptop under $1000")
    assert request.category == "laptop"
    assert request.budget == Decimal("1000")
    assert request.market == "US"
    assert "performance" in request.priorities


def test_parses_notebook_phrasing():
    request = parse_request("Find the best notebook below $899.99")
    assert request.category == "laptop"
    assert request.budget == Decimal("899.99")


def test_budget_override_fixes_powershell_truncation():
    request = parse_request("best laptop under", budget=Decimal("1000"))
    assert request.category == "laptop"
    assert request.budget == Decimal("1000")


def test_truncated_budget_without_override_raises():
    with pytest.raises(ValueError, match="Budget amount is missing"):
        parse_request("best laptop under")


def test_rejects_empty_request():
    with pytest.raises(ValueError):
        parse_request("  ")


def test_headphones_category_normalizes():
    request = parse_request("best wireless headphones under $60")
    assert request.category == "headphones"
    assert request.budget == Decimal("60")
    assert "noise cancellation" in request.priorities
    assert "prefer_true_wireless" not in request.constraints


def test_earbuds_query_sets_true_wireless_preference():
    request = parse_request("best wireless earbuds under $100", budget=Decimal("100"))
    assert request.category == "headphones"
    assert "prefer_true_wireless" in request.constraints


def test_unknown_category_parses_but_is_not_normalized():
    request = parse_request("best smartphone under $600")
    assert request.category == "smartphone"
    assert request.budget == Decimal("600")


def test_category_aware_default_budget_when_query_omits_amount():
    laptop = parse_request("best laptop")
    assert laptop.category == "laptop"
    assert laptop.budget == Decimal("1000.00")

    buds = parse_request("best wireless earbuds")
    assert buds.category == "headphones"
    assert buds.budget == Decimal("100.00")
    assert default_budget_for_category("headphones") == Decimal("100.00")


def test_parse_budget_arg_accepts_dollar_prefix():
    assert parse_budget_arg("$99.50") == Decimal("99.50")
    assert parse_budget_arg("1,200") == Decimal("1200")
