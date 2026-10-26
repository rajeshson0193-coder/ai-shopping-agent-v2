import json
from urllib.error import URLError

from shopping_agent.explain import (
    ExplanationResult,
    explain_report,
    list_ollama_models,
    model_choices,
    slim_report_for_llm,
    _parse_explanation_payload,
)


def test_slim_report_keeps_rank_price_and_spec_strength():
    report = {
        "request": {"raw_text": "best wireless earbuds under 100", "budget": "100"},
        "recommendations": [
            {
                "rank": 1,
                "model": "Soundcore P30i",
                "listed_price": "27.99",
                "score": 33,
                "reasons": ["+20: manufacturer evidence verifies ANC"],
                "specifications": {
                    "anc_support": {
                        "value": "supported",
                        "status": "verified",
                        "evidence_strength": "strong",
                        "source_type": "manufacturer_page",
                        "supporting_text": "long text that should be dropped",
                    }
                },
            }
        ],
        "limitations": ["a", "b", "c"],
        "source_errors": {},
    }
    slim = slim_report_for_llm(report)
    pick = slim["recommendations"][0]
    assert pick["model"] == "Soundcore P30i"
    assert pick["listed_price"] == "27.99"
    assert "supporting_text" not in pick["specifications"]["anc_support"]
    assert pick["specifications"]["anc_support"]["evidence_strength"] == "strong"


def test_parse_explanation_payload_orders_by_report_ranks():
    recommendations = [
        {"rank": 1, "model": "A"},
        {"rank": 2, "model": "B"},
    ]
    raw = json.dumps(
        {
            "overview_bullets": ["Shortlist overview."],
            "picks": [
                {"rank": 2, "model": "B", "bullets": ["Second pick."]},
                {"rank": 1, "model": "A", "bullets": ["First pick."]},
            ],
        }
    )
    overview, picks = _parse_explanation_payload(raw, recommendations)
    assert overview == "- Shortlist overview."
    assert [item["rank"] for item in picks] == [1, 2]
    assert picks[0]["explanation"] == "- First pick."


def test_parse_matches_by_model_when_rank_missing():
    recommendations = [
        {"rank": 1, "model": "Skullcandy SESH ANC"},
        {"rank": 2, "model": "JBL Vibe Beam 2"},
    ]
    raw = json.dumps(
        {
            "overview": "Overview",
            "picks": [
                {
                    "model": "JBL Vibe Beam 2",
                    "bullets": ["Strong manufacturer type and ANC."],
                }
            ],
        }
    )
    _, picks = _parse_explanation_payload(raw, recommendations)
    assert picks[0]["explanation"] is None
    assert "- Strong manufacturer" in (picks[1]["explanation"] or "")


def test_list_ollama_models_soft_skips_when_unreachable(monkeypatch):
    def boom(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("shopping_agent.explain._get_json", boom)
    assert list_ollama_models() == []


def test_model_choices_falls_back_when_ollama_down(monkeypatch):
    monkeypatch.setattr("shopping_agent.explain.list_ollama_models", lambda **_: [])
    options, reachable = model_choices(preferred="qwen3:4b-instruct")
    assert reachable is False
    assert options[0] == "qwen3:4b-instruct"
    assert "gemma3:4b" in options


def test_explain_report_degrades_when_ollama_unreachable(monkeypatch):
    def boom(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("shopping_agent.explain._post_json", boom)
    result = explain_report(
        {
            "recommendations": [
                {
                    "rank": 1,
                    "model": "JBL Vibe Beam 2",
                    "score": 33,
                    "listed_price": "27.99",
                    "reasons": ["+20: manufacturer evidence verifies ANC"],
                },
                {
                    "rank": 2,
                    "model": "Soundcore P30i",
                    "score": 33,
                    "listed_price": "27.99",
                    "reasons": ["+10: manufacturer evidence verifies headphone type"],
                },
            ]
        },
        model="qwen3:4b-instruct",
    )
    assert isinstance(result, ExplanationResult)
    assert result.available is True
    assert result.error and "degraded" in result.error.casefold()
    assert len(result.pick_explanations) == 2
    assert all(item.get("explanation") for item in result.pick_explanations)
    assert all(
        (item.get("explanation") or "").lstrip().startswith("-")
        for item in result.pick_explanations
    )


def test_explain_report_fills_missing_picks_after_partial_llm(monkeypatch):
    calls = {"n": 0}

    def fake_post(_url, payload, timeout):
        del timeout
        calls["n"] += 1
        prompt = payload.get("prompt") or ""
        if calls["n"] == 1:
            return {
                "response": json.dumps(
                    {
                        "overview_bullets": ["Four true-wireless picks under budget."],
                        "picks": [
                            {
                                "rank": 1,
                                "model": "Skullcandy SESH ANC",
                                "bullets": ["Only the first pick was narrated."],
                            }
                        ],
                    }
                )
            }
        # Second call should request the missing ranks.
        assert "Missing picks" in prompt or "missing" in prompt.casefold()
        return {
            "response": json.dumps(
                {
                    "picks": [
                        {
                            "rank": 2,
                            "model": "JBL Vibe Beam 2",
                            "bullets": ["Manufacturer ANC and type evidence."],
                        },
                        {
                            "rank": 3,
                            "model": "Soundcore P30i",
                            "bullets": ["Strong type and ANC from Soundcore page."],
                        },
                    ]
                }
            )
        }

    monkeypatch.setattr("shopping_agent.explain._post_json", fake_post)
    result = explain_report(
        {
            "recommendations": [
                {"rank": 1, "model": "Skullcandy SESH ANC", "score": 38, "reasons": []},
                {
                    "rank": 2,
                    "model": "JBL Vibe Beam 2",
                    "score": 33,
                    "reasons": ["+20: manufacturer evidence verifies ANC"],
                },
                {
                    "rank": 3,
                    "model": "Soundcore P30i",
                    "score": 33,
                    "reasons": ["+10: manufacturer evidence verifies headphone type"],
                },
            ]
        }
    )
    assert result.available is True
    assert calls["n"] == 2
    assert len(result.pick_explanations) == 3
    assert all(item.get("explanation") for item in result.pick_explanations)
    assert "first pick" in result.pick_explanations[0]["explanation"].casefold()
    assert "manufacturer anc" in result.pick_explanations[1]["explanation"].casefold()


def test_explain_report_parses_successful_generate(monkeypatch):
    def fake_post(_url, _payload, timeout):
        del timeout
        return {
            "response": json.dumps(
                {
                    "overview_bullets": ["Three true-wireless picks under budget."],
                    "picks": [
                        {
                            "rank": 1,
                            "model": "JBL Vibe Beam 2",
                            "bullets": [
                                "Strong manufacturer ANC evidence.",
                                "Type verified on manufacturer page.",
                            ],
                        }
                    ],
                }
            )
        }

    monkeypatch.setattr("shopping_agent.explain._post_json", fake_post)
    result = explain_report(
        {
            "recommendations": [
                {
                    "rank": 1,
                    "model": "JBL Vibe Beam 2",
                    "score": 33,
                    "reasons": ["+20: manufacturer evidence verifies ANC"],
                }
            ]
        }
    )
    assert result.available is True
    assert "true-wireless" in (result.overview or "").casefold()
    assert "- Strong manufacturer ANC evidence." in (
        result.pick_explanations[0]["explanation"] or ""
    )
