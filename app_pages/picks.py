"""Results page — compact ShopBuddy shortlist (fit desktop viewport)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ui.helpers import (
    OUTPUT_PATH,
    SCORING_DISCLAIMER,
    explanation_by_rank,
    format_evidence_points,
    init_state,
)

PICKS_CSS = Path(__file__).resolve().parents[1] / "ui" / "picks.css"


def _inject_styles() -> None:
    if PICKS_CSS.exists():
        st.html(PICKS_CSS)


def _esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _bullet_lines(text: str | None) -> list[str]:
    """Turn markdown/plain explanation text into clean bullet lines."""
    if not text or not str(text).strip():
        return ["Evidence-ranked pick from this run."]
    lines: list[str] = []
    for raw in str(text).splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        lines.append(stripped.lstrip("-•* ").strip())
    if lines:
        return lines[:5]
    # Single paragraph → split on sentences so cards stay point-wise.
    sentences = [
        part.strip()
        for part in str(text).replace("\n", " ").split(". ")
        if part.strip()
    ]
    if len(sentences) >= 2:
        return [
            (s if s.endswith((".", "!", "?")) else f"{s}.")
            for s in sentences[:4]
        ]
    return [str(text).strip()]


def _bullets_html(text: str | None) -> str:
    items = "".join(f"<li>{_esc(line)}</li>" for line in _bullet_lines(text))
    return f'<ul class="pk-why">{items}</ul>'


def _evidence_html(reasons: list[str]) -> str:
    if not reasons:
        return ""
    items = "".join(f"<li>{_esc(reason)}</li>" for reason in reasons)
    return (
        '<details class="pk-evidence">'
        "<summary>Evidence</summary>"
        f"<ul>{items}</ul>"
        "</details>"
    )


def _pick_card_html(rec: dict, why: str) -> str:
    rank = int(rec.get("rank") or 0)
    model_name = _esc(rec.get("model") or rec.get("name") or "Unknown model")
    price = rec.get("listed_price")
    cur = _esc(rec.get("currency") or "USD")
    score = rec.get("score")
    url = rec.get("product_url")
    provisional = bool(rec.get("provisional"))
    condition = rec.get("condition")
    reasons = [str(r) for r in (rec.get("reasons") or []) if str(r).strip()][:4]

    badge = '<span class="pk-badge">provisional</span>' if provisional else ""
    chips: list[str] = []
    if price is not None:
        chips.append(f'<span class="pk-chip price">${_esc(price)} {cur}</span>')
    if score is not None:
        chips.append(
            f'<span class="pk-chip">{_esc(format_evidence_points(score))}</span>'
        )
    if condition:
        chips.append(f'<span class="pk-chip">{_esc(condition)}</span>')

    cta = (
        f'<a class="pk-cta" href="{_esc(url)}" target="_blank" rel="noopener noreferrer">'
        "Open listing"
        "</a>"
        if url
        else '<span class="pk-cta pk-cta-disabled">No listing link</span>'
    )

    return f"""
    <article class="pk-card">
      <div class="pk-card-top">
        <div class="pk-card-head">
          <span class="pk-rank">#{rank}</span>
          {badge}
        </div>
        <p class="pk-model">{model_name}</p>
        <div class="pk-meta">{"".join(chips)}</div>
        {why}
        {_evidence_html(reasons)}
      </div>
      {cta}
    </article>
    """


init_state()
_inject_styles()

# Recover picks after a Home hang: ranking may already be on disk.
if st.session_state.report is None and OUTPUT_PATH.exists():
    try:
        import json as _json

        saved = _json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict) and (saved.get("recommendations") or []):
            st.session_state.report = saved
            if st.session_state.explanation is None:
                st.session_state.explanation = saved.get("explanation")
            st.session_state.ran = True
    except (OSError, ValueError):
        pass

report = st.session_state.report
explanation = st.session_state.explanation

st.html(
    """
    <div class="pk-header">
      <div class="pk-brand">
        <span class="pk-brand-mark">+</span>
        <span class="pk-brand-name">ShopBuddy</span>
      </div>
    </div>
    """
)

if st.session_state.last_error and not report:
    st.error(
        st.session_state.last_error,
        title="Could not run research",
        icon=":material/error:",
    )

if not report:
    st.info(
        "Run a search on the home page to see evidence-ranked picks here.",
        title="No picks yet",
        icon=":material/shopping_bag:",
    )
    if st.button("Back to search", type="primary", icon=":material/arrow_back:"):
        st.switch_page("app_pages/home.py")
    st.stop()

request = report.get("request") or {}
recs = list(report.get("recommendations") or [])
query = request.get("raw_text") or st.session_state.query_text or "your request"
budget = request.get("budget", "?")
currency = request.get("currency", "USD")

head_l, head_r = st.columns([4.2, 1], vertical_alignment="center")
with head_l:
    st.html('<h1 class="pk-title">Your shortlist</h1>')
    st.html(
        f'<p class="pk-sub"><strong>{len(recs)}</strong> evidence-ranked pick'
        f'{"s" if len(recs) != 1 else ""} for “{query}” · '
        f"budget ${budget} {currency}</p>"
    )
with head_r:
    if st.button("New search", icon=":material/arrow_back:", width="stretch"):
        st.switch_page("app_pages/home.py")

if explanation and explanation.get("overview"):
    st.html(f'<div class="pk-overview">{_bullets_html(explanation.get("overview"))}</div>')
if explanation and explanation.get("error"):
    st.caption(str(explanation["error"]))

by_rank = explanation_by_rank(explanation)

if not recs:
    st.info(
        "No eligible recommendations in this run. Try Live mode with API keys, "
        "or a broader query.",
        title="Empty shortlist",
        icon=":material/info:",
    )
else:
    # One CSS grid so every card (and Open listing CTA) stays on one aligned row.
    cards = []
    for rec in recs:
        rank = int(rec.get("rank") or 0)
        cards.append(_pick_card_html(rec, _bullets_html(by_rank.get(rank))))
    st.html(f'<div class="pk-grid">{"".join(cards)}</div>')

with st.expander("Scoring notes", expanded=False):
    st.caption(SCORING_DISCLAIMER)
    if report.get("source_errors"):
        st.markdown("**Source notes**")
        for source, message in (report.get("source_errors") or {}).items():
            st.markdown(f"- **{source}:** {message}")

st.html(
    f'<p class="pk-foot">Saved report: {OUTPUT_PATH.as_posix()}</p>'
)
