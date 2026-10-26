from decimal import Decimal

from shopping_agent.pipeline import run_research


def test_full_pipeline_returns_five_laptops():
    result = run_research("Find the five best laptops under $1000")
    assert result.stages_run == [
        "parse",
        "discover",
        "identify",
        "research",
        "validate",
        "rank",
    ]
    assert len(result.recommendations) == 5
    models = [item.candidate.model for item in result.recommendations]
    assert "Lenovo IdeaPad Slim 3" in models
    assert all(item.candidate.listed_price <= result.request.budget for item in result.recommendations)
    assert all(item.candidate.price_status.value == "verified" for item in result.recommendations)
    sources = {item.candidate.source for item in result.recommendations}
    assert len(sources) >= 2
    assert any(row["reason"] == "likely_accessory_not_laptop" for row in result.excluded)


def test_headphones_pipeline_returns_shortlist():
    result = run_research("best wireless earbuds under $150", budget=Decimal("150"))
    assert result.request.category == "headphones"
    assert "prefer_true_wireless" in result.request.constraints
    assert result.stages_run[-1] == "rank"
    assert len(result.recommendations) >= 3
    models = {item.candidate.model for item in result.recommendations}
    # Earbuds query should prefer true-wireless models, not over-ear cans.
    assert "JBL Vibe Beam 2" in models or "Skullcandy SESH ANC" in models or "Soundcore P30i" in models
    assert "Soundcore Q20i" not in models
    assert "Sony WH-CH520" not in models
    assert all(item.candidate.listed_price <= result.request.budget for item in result.recommendations)
    assert any(row["reason"] == "likely_accessory_not_headphones" for row in result.excluded)
    assert any(row["reason"] == "form_factor_mismatch_for_earbuds_query" for row in result.excluded)
    payload = result.to_dict()
    assert payload["request"]["priorities_role"] == "descriptive_category_focus_only"
    joined_limits = " ".join(payload["limitations"]).casefold()
    assert "descriptive" in joined_limits
    assert "fixed evidence" in joined_limits


def test_rejects_unregistered_category():
    try:
        run_research("best smartphone under $600")
    except ValueError as exc:
        assert "Unsupported category" in str(exc)
        assert "smartphone" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_pipeline_reports_progress_stages():
    messages: list[str] = []
    run_research(
        "best wireless earbuds under $150",
        budget=Decimal("150"),
        on_progress=messages.append,
    )
    joined = " | ".join(messages).casefold()
    assert "parsing" in joined
    assert "using budget $150" in joined
    assert "identifying" in joined
    assert "ranking" in joined
    assert len(messages) >= 5
