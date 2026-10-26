"""Audience-friendly explanations from a ranked report via local Ollama.

Ranking and scoring stay deterministic. This module only narrates the report.

FUTURE (not enabled yet): LLM-assisted discovery like v1 model_discovery
(Tavily/search leads + Ollama name extraction). Keep discovery/ranking
evidence-first; do not let the LLM invent product leads or scores.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:4b-instruct"
# Shown in the UI when /api/tags is unreachable so the dropdown still works.
FALLBACK_MODEL_CHOICES = (
    "qwen3:4b-instruct",
    "gemma3:4b",
    "gemma2:2b",
    "llama3.2:3b",
    "gemma4:12b",
)


@dataclass
class ExplanationResult:
    overview: str | None = None
    pick_explanations: list[dict[str, Any]] = field(default_factory=list)
    model: str | None = None
    available: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "overview": self.overview,
            "pick_explanations": list(self.pick_explanations),
            "model": self.model,
            "available": self.available,
            "error": self.error,
        }


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from Ollama.")
    return data


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from Ollama.")
    return data


def list_ollama_models(
    *,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 5.0,
) -> list[str]:
    """Return installed model names, or [] if Ollama is unreachable (soft-skip)."""
    try:
        data = _get_json(f"{host.rstrip('/')}/api/tags", timeout=timeout)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
        return []
    models = data.get("models") or []
    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def model_choices(
    *,
    host: str = DEFAULT_OLLAMA_HOST,
    preferred: str = DEFAULT_OLLAMA_MODEL,
    timeout: float = 5.0,
) -> tuple[list[str], bool]:
    """Return (dropdown options, ollama_reachable). Preferred model is listed first."""
    installed = list_ollama_models(host=host, timeout=timeout)
    reachable = bool(installed)
    options = list(installed) if installed else list(FALLBACK_MODEL_CHOICES)
    if preferred and preferred not in options:
        options.insert(0, preferred)
    elif preferred in options:
        options = [preferred] + [name for name in options if name != preferred]
    return options, reachable


def slim_report_for_llm(report: dict[str, Any]) -> dict[str, Any]:
    """Shrink the ranked report to evidence the model may narrate (no inventing)."""
    picks: list[dict[str, Any]] = []
    for rec in report.get("recommendations") or []:
        if not isinstance(rec, dict):
            continue
        specs: dict[str, Any] = {}
        for key, value in (rec.get("specifications") or {}).items():
            if not isinstance(value, dict):
                continue
            specs[key] = {
                "value": value.get("value"),
                "status": value.get("status"),
                "evidence_strength": value.get("evidence_strength"),
                "source_type": value.get("source_type"),
            }
        picks.append(
            {
                "rank": rec.get("rank"),
                "model": rec.get("model"),
                "name": rec.get("name"),
                "listed_price": rec.get("listed_price"),
                "currency": rec.get("currency"),
                "score": rec.get("score"),
                "reasons": rec.get("reasons") or [],
                "provisional": rec.get("provisional"),
                "product_url": rec.get("product_url"),
                "source": rec.get("source"),
                "condition": rec.get("condition"),
                "specifications": specs,
            }
        )
    return {
        "request": report.get("request") or {},
        "recommendations": picks,
        "source_errors": report.get("source_errors") or {},
        "limitations": list(report.get("limitations") or [])[:8],
    }


def _as_bullet_markdown(value: Any) -> str | None:
    """Normalize list/string explanations into markdown bullets for the UI."""
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
        if not lines:
            return None
        return "\n".join(f"- {line.lstrip('-• ').strip()}" for line in lines[:5])
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if "\n" in text and any(line.strip().startswith(("-", "•")) for line in text.splitlines()):
        cleaned: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            cleaned.append(f"- {stripped.lstrip('-• ').strip()}")
        return "\n".join(cleaned[:5]) if cleaned else None
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if len(sentences) >= 2:
        return "\n".join(f"- {sentence}" for sentence in sentences[:4])
    return f"- {text}"


def _fallback_pick_explanation(rec: dict[str, Any]) -> str:
    """Deterministic bullet copy when the local model omits a pick."""
    model = rec.get("model") or "This pick"
    price = rec.get("listed_price")
    currency = rec.get("currency") or "USD"
    score = rec.get("score")
    reasons = [str(r) for r in (rec.get("reasons") or []) if str(r).strip()]
    scoring = [r for r in reasons if r.lstrip().startswith("+")]
    caveats = [
        r
        for r in reasons
        if "weakly supported" in r.casefold()
        or "not scored" in r.casefold()
        or "provisional" in r.casefold()
    ]
    bullets: list[str] = []
    headline = f"{model} ranks on evidence-backed specs"
    if price is not None:
        headline += f" at ${price} {currency}"
    if score is not None:
        headline += f" (score {score})"
    bullets.append(headline)
    bullets.extend(scoring[:3])
    if rec.get("provisional") or caveats:
        bullets.append(caveats[0] if caveats else "Some claims are still provisional.")
    return _as_bullet_markdown(bullets) or f"- {headline}"


def _fallback_overview(recommendations: list[dict[str, Any]]) -> str:
    count = len(recommendations)
    models = [str(r.get("model")) for r in recommendations if r.get("model")]
    named = ", ".join(models[:3])
    if count == 0:
        return "- No eligible recommendations were available to explain."
    if count == 1:
        return f"- Shortlist has 1 evidence-backed pick: {named}."
    extra = f" and {count - 3} more" if count > 3 else ""
    return "\n".join(
        [
            f"- Shortlist has {count} evidence-backed picks"
            + (f" led by {named}{extra}" if named else "")
            + ".",
            "- Scores are fixed evidence points from manufacturer-verified specs, not personalized preference ranking.",
        ]
    )


def _build_prompt(slim: dict[str, Any]) -> str:
    n = len(slim.get("recommendations") or [])
    ranks = [str(item.get("rank")) for item in slim.get("recommendations") or []]
    return f"""
You explain a local shopping-research report for a YouTube audience.

Hard rules:
- Use ONLY facts in the JSON below. Do not invent specs, prices, scores, or reviews.
- If a field is unknown, weak, provisional, or inaccessible, say so briefly.
- Do not mention internal pipeline stage names.
- Keep a clear, practical tone (local AI / low-cost research helper), not hype.
- Scores are fixed evidence points for verified specs, not personalized “best battery / best sound” ranking.

Critical output rules:
- Return exactly one JSON object.
- "picks" MUST be an array with exactly {n} objects — one for EVERY recommendation.
- Required ranks: {", ".join(ranks)}.
- Do not stop after the first pick.
- Each pick explanation MUST be a short bullet list (2-4 bullets), not a paragraph.
- Overview MUST also be 2-4 short bullets.

JSON shape:
{{
  "overview_bullets": ["short point", "short point"],
  "picks": [
    {{
      "rank": 1,
      "model": "Exact model string from JSON",
      "bullets": ["Why it ranked", "Key verified evidence", "Caveat if any"]
    }}
  ]
}}

Report JSON:
{json.dumps(slim, ensure_ascii=False)}
""".strip()


def _build_missing_picks_prompt(
    missing: list[dict[str, Any]],
    overview_context: str | None,
) -> str:
    return f"""
Write short bullet explanations for ONLY these missing shopping picks.
Use ONLY facts in the JSON. Do not invent specs.
Return one JSON object:
{{"picks":[{{"rank":1,"model":"...","bullets":["point 1","point 2","point 3"]}}]}}
Include every listed rank. Each pick needs 2-4 short bullets.
Context overview (optional): {overview_context or "n/a"}

Missing picks JSON:
{json.dumps(missing, ensure_ascii=False)}
""".strip()


def _extract_pick_items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize several common local-model JSON shapes into pick dicts."""
    items: list[dict[str, Any]] = []
    for key in ("picks", "recommendations", "items", "explanations"):
        value = parsed.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            # e.g. {"1": "text"} or {"1": {"explanation": "..."}}
            for raw_rank, payload in value.items():
                if isinstance(payload, str):
                    items.append({"rank": raw_rank, "explanation": payload})
                elif isinstance(payload, dict):
                    row = dict(payload)
                    row.setdefault("rank", raw_rank)
                    items.append(row)
    return items


def _parse_explanation_payload(
    raw: str,
    recommendations: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Explanation payload must be a JSON object.")
    overview = _as_bullet_markdown(
        parsed.get("overview_bullets")
        if parsed.get("overview_bullets") is not None
        else parsed.get("overview")
    )

    by_rank: dict[int, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for item in _extract_pick_items(parsed):
        explanation = _as_bullet_markdown(
            item.get("bullets")
            if item.get("bullets") is not None
            else item.get("explanation") or item.get("why") or item.get("text")
        )
        if not explanation:
            continue
        model = item.get("model")
        model_key = model.casefold() if isinstance(model, str) else None
        rank_value = item.get("rank")
        rank: int | None
        try:
            rank = int(rank_value)
        except (TypeError, ValueError):
            rank = None
        row = {
            "rank": rank,
            "model": model if isinstance(model, str) else None,
            "explanation": explanation,
        }
        if rank is not None:
            by_rank[rank] = row
        if model_key:
            by_model[model_key] = row

    ordered: list[dict[str, Any]] = []
    for rec in recommendations:
        rank = int(rec.get("rank") or 0)
        fallback_model = rec.get("model")
        model_key = fallback_model.casefold() if isinstance(fallback_model, str) else None
        hit = by_rank.get(rank)
        if hit is None and model_key:
            hit = by_model.get(model_key)
        if hit:
            ordered.append(
                {
                    "rank": rank,
                    "model": hit.get("model") or fallback_model,
                    "explanation": hit.get("explanation"),
                }
            )
        else:
            ordered.append(
                {
                    "rank": rank,
                    "model": fallback_model if isinstance(fallback_model, str) else None,
                    "explanation": None,
                }
            )
    return overview, ordered


def _generate(
    *,
    host: str,
    model: str,
    prompt: str,
    timeout: float,
) -> str:
    response = _post_json(
        f"{host.rstrip('/')}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "num_predict": 1200,
            },
        },
        timeout=timeout,
    )
    text = response.get("response")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Ollama response did not contain text.")
    # Some models wrap JSON in markdown fences even with format=json.
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.S)
    if fenced:
        return fenced.group(1)
    return cleaned


def _merge_pick_explanations(
    base: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_rank = {
        int(item["rank"]): item
        for item in extra
        if item.get("rank") is not None and item.get("explanation")
    }
    merged: list[dict[str, Any]] = []
    for item in base:
        rank = int(item.get("rank") or 0)
        if item.get("explanation"):
            merged.append(item)
        elif rank in by_rank:
            fill = by_rank[rank]
            merged.append(
                {
                    "rank": rank,
                    "model": fill.get("model") or item.get("model"),
                    "explanation": fill.get("explanation"),
                }
            )
        else:
            merged.append(item)
    return merged


def _fill_missing_with_fallback(
    picks: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_rank = {int(rec.get("rank") or 0): rec for rec in recommendations}
    filled: list[dict[str, Any]] = []
    for item in picks:
        rank = int(item.get("rank") or 0)
        if item.get("explanation"):
            filled.append(item)
            continue
        rec = by_rank.get(rank) or {}
        filled.append(
            {
                "rank": rank,
                "model": item.get("model") or rec.get("model"),
                "explanation": _fallback_pick_explanation(rec or item),
            }
        )
    return filled


def explain_report(
    report: dict[str, Any],
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 60.0,
    use_llm: bool = True,
) -> ExplanationResult:
    """Generate overview + per-pick copy. Soft-skips when Ollama is unavailable.

    When use_llm is False, return deterministic fallback copy immediately
    (used by the UI so Search can navigate to Picks without waiting on Ollama).
    """
    slim = slim_report_for_llm(report)
    recommendations = list(slim.get("recommendations") or [])
    if not recommendations:
        return ExplanationResult(
            overview="No eligible recommendations were available to explain.",
            pick_explanations=[],
            model=model,
            available=True,
            error=None,
        )

    def _fallback_result(*, available: bool, error: str | None) -> ExplanationResult:
        picks = [
            {
                "rank": int(rec.get("rank") or 0),
                "model": rec.get("model") if isinstance(rec.get("model"), str) else None,
                "explanation": _fallback_pick_explanation(rec),
            }
            for rec in recommendations
        ]
        return ExplanationResult(
            overview=_fallback_overview(recommendations),
            pick_explanations=picks,
            model=model,
            available=available,
            error=error,
        )

    if not use_llm:
        return _fallback_result(
            available=False,
            error="LLM explanations skipped for faster UI.",
        )

    try:
        text = _generate(
            host=host,
            model=model,
            prompt=_build_prompt(slim),
            timeout=timeout,
        )
        overview, picks = _parse_explanation_payload(text, recommendations)

        missing = [p for p in picks if not p.get("explanation")]
        if missing:
            missing_recs = [
                rec
                for rec in recommendations
                if int(rec.get("rank") or 0) in {int(m.get("rank") or 0) for m in missing}
            ]
            try:
                refill_text = _generate(
                    host=host,
                    model=model,
                    prompt=_build_missing_picks_prompt(missing_recs, overview),
                    timeout=max(60.0, timeout / 2),
                )
                _, refill_picks = _parse_explanation_payload(refill_text, missing_recs)
                picks = _merge_pick_explanations(picks, refill_picks)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
                # Fall through to deterministic fill below.
                pass

        picks = _fill_missing_with_fallback(picks, recommendations)
        if not overview:
            overview = _fallback_overview(recommendations)

        return ExplanationResult(
            overview=overview,
            pick_explanations=picks,
            model=model,
            available=True,
            error=None,
        )
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
        # Soft-skip LLM, but still show deterministic card copy so the UI is complete.
        picks = [
            {
                "rank": int(rec.get("rank") or 0),
                "model": rec.get("model") if isinstance(rec.get("model"), str) else None,
                "explanation": _fallback_pick_explanation(rec),
            }
            for rec in recommendations
        ]
        return ExplanationResult(
            overview=_fallback_overview(recommendations),
            pick_explanations=picks,
            model=model,
            available=True,
            error=f"Ollama explanation degraded to evidence summary: {exc}",
        )
