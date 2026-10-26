"""Turn a shopping sentence into a structured request. No LLM."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from shopping_agent.models import ShoppingRequest
from shopping_agent.profiles.registry import match_profile

_BUDGET_RE = re.compile(
    r"\b(?:under|below|less than|within|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.I,
)
_BARE_DOLLAR_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
_OPENER_RE = re.compile(
    r"^\s*(?:find|search for|show me|recommend|look for|get|what(?:'s| is)|the)\s+",
    re.I,
)
_BEST_RE = re.compile(r"\bbest\b", re.I)
# PowerShell expands $1000 away, leaving phrases like "best laptop under".
_TRUNCATED_BUDGET_RE = re.compile(
    r"\b(?:under|below|less than|within|up to|max(?:imum)?)\s*$",
    re.I,
)
_EARBUD_INTENT_RE = re.compile(
    r"\b(?:earbuds?|earphones?|\btws\b|true\s+wireless|buds)\b",
    re.I,
)

# Used only when the request has no budget phrase and no override.
_DEFAULT_BUDGET_BY_CATEGORY = {
    "laptop": Decimal("1000.00"),
    "headphones": Decimal("100.00"),
}
_FALLBACK_DEFAULT_BUDGET = Decimal("1000.00")


def budget_looks_truncated(text: str) -> bool:
    return bool(_TRUNCATED_BUDGET_RE.search((text or "").strip()))


def default_budget_for_category(category: str) -> Decimal:
    """Category-aware fallback when the user did not state a budget."""
    return _DEFAULT_BUDGET_BY_CATEGORY.get(
        (category or "").casefold().strip(),
        _FALLBACK_DEFAULT_BUDGET,
    )


def parse_request(text: str, budget: Decimal | None = None) -> ShoppingRequest:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Shopping request cannot be empty")

    raw = text.strip()
    query_budget: Decimal | None = None
    budget_match = _BUDGET_RE.search(raw) or _BARE_DOLLAR_RE.search(raw)
    if budget_match:
        query_budget = Decimal(budget_match.group(1))

    category = _BUDGET_RE.sub("", raw)
    category = _BARE_DOLLAR_RE.sub("", category)
    category = _OPENER_RE.sub("", category)
    category = _BEST_RE.sub("", category)
    category = re.sub(r"\s+", " ", category).strip(" .,!?")
    if not category:
        raise ValueError("Could not identify the product category")

    profile = match_profile(category)
    constraints: list[str] = []
    if profile is not None:
        category = profile.id
        # Copied for report context only — ranking does not reweight by these.
        priorities = list(profile.priorities)
        if profile.id == "headphones" and _EARBUD_INTENT_RE.search(raw):
            # "wireless earbuds" should not shortlist over-ear / on-ear cans.
            constraints.append("prefer_true_wireless")
    else:
        # Unknown categories parse but later stages refuse them rather than invent a catalog.
        priorities = ["balanced overall value"]

    if budget is not None:
        if not budget.is_finite() or budget < 0:
            raise ValueError("budget must be a finite non-negative amount")
        parsed_budget = budget
    elif query_budget is not None:
        parsed_budget = query_budget
    elif budget_looks_truncated(raw):
        raise ValueError(
            "Budget amount is missing. PowerShell removes $1000 from double-quoted "
            "strings. Use --budget 1000, or single quotes: 'best laptop under $1000'."
        )
    else:
        parsed_budget = default_budget_for_category(category)

    return ShoppingRequest(
        raw_text=raw,
        category=category,
        budget=parsed_budget,
        market="US",
        currency="USD",
        priorities=priorities,
        constraints=constraints,
    )


def parse_budget_arg(value: str) -> Decimal:
    cleaned = str(value).strip().replace(",", "")
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].strip()
    try:
        parsed = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("budget must be a decimal amount") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("budget must be a finite non-negative amount")
    return parsed
