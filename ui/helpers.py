"""Shared helpers for the ShopBuddy Streamlit UI."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import streamlit as st

from collections.abc import Callable

from shopping_agent.parse import parse_budget_arg
from shopping_agent.pipeline import run_research

OUTPUT_PATH = Path("output/latest_report.json")
APP_NAME = "ShopBuddy"
ProgressCallback = Callable[[str], None]


LIMIT_CHOICES = (3, 5, 10)

# Scores are a fixed evidence heuristic — not personalized to battery/comfort/sound/value.
SCORING_DISCLAIMER = (
    "Scores are fixed evidence points for the category (verified manufacturer specs + "
    "listing condition), not a personalized “best battery / best sound” ranking. "
    "Profile focus areas in the report are descriptive only."
)


def format_evidence_points(score: object) -> str:
    """Label a recommendation score so the UI cannot read as a quality rating."""
    return f"evidence points {score}"


def scoring_disclaimer_lines(report: dict | None) -> list[str]:
    """Prefer report limitations that explain scoring; fall back to the shared caption."""
    lines: list[str] = []
    for item in (report or {}).get("limitations") or []:
        text = str(item).strip()
        if not text:
            continue
        lowered = text.casefold()
        if any(
            token in lowered
            for token in (
                "evidence",
                "score",
                "priorit",
                "focus area",
                "battery",
                "personalized",
                "descriptive",
            )
        ):
            lines.append(text)
    if lines:
        return lines
    return [SCORING_DISCLAIMER]


def init_state() -> None:
    defaults = {
        "report": None,
        "explanation": None,
        "last_error": None,
        "ran": False,
        "query_text": "best wireless earbuds under $100",
        "selected_model": None,
        "top_n": 5,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def parse_budget(raw: str | None) -> Decimal | None:
    """Parse an optional UI budget override.

    Blank → ``None`` (use the budget from the shopping request / category default).
    Invalid → ``ValueError`` (do not silently fall back).
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        return parse_budget_arg(str(raw).strip())
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(
            f"Invalid budget override {str(raw).strip()!r}. "
            "Enter a USD amount (e.g. 100), or leave blank to use the budget "
            "from your shopping request."
        ) from exc


def format_pipeline_error(exc: BaseException, *, live: bool) -> str:
    """Turn pipeline failures into a short UI recovery message."""
    message = str(exc).strip() or type(exc).__name__
    if isinstance(exc, RuntimeError) and "No discovery sources available" in message:
        if live:
            return (
                "Live discovery has no usable sources. "
                "Add EBAY_CLIENT_ID / EBAY_CLIENT_SECRET to your environment, "
                "or switch Mode to Fixtures for offline rehearsal."
            )
        return (
            "No discovery sources available. "
            "Switch Mode to Fixtures, or configure API keys for Live mode."
        )
    return message


def run_pipeline(
    query: str,
    *,
    budget: Decimal | None,
    live: bool,
    include_serpapi: bool,
    limit: int = 5,
    on_progress: ProgressCallback | None = None,
) -> dict:
    # Wider discovery pool when the user asks for a longer shortlist.
    max_results = max(20, int(limit) * 4)
    result = run_research(
        query,
        limit=limit,
        budget=budget,
        live=live,
        use_fixtures=not live,
        skip_serpapi=(not live) or (not include_serpapi),
        max_results_per_source=max_results,
        timeout=30,
        on_progress=on_progress,
    )
    payload = result.to_dict()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def explanation_by_rank(explanation: dict | None) -> dict[int, str]:
    if not explanation:
        return {}
    mapping: dict[int, str] = {}
    for item in explanation.get("pick_explanations") or []:
        if not isinstance(item, dict):
            continue
        text = item.get("explanation")
        rank = item.get("rank")
        if isinstance(text, str) and text.strip() and rank is not None:
            try:
                mapping[int(rank)] = text.strip()
            except (TypeError, ValueError):
                continue
    return mapping
