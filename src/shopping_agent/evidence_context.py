"""Claim↔model context helpers for research extraction and evidence audit.

Manufacturer pages often mention many products (footers, related items). These
helpers keep extraction near the allow-listed model and stop the auditor from
labeling STRONG when the snippet is not about that model (or is cable≠port).
"""

from __future__ import annotations

import re

# Chars kept on each side of a model mention when building extraction windows.
MODEL_WINDOW_RADIUS = 700
# Max distance between a claim match and a model mention to treat them as linked.
CLAIM_MODEL_MAX_GAP = 500

_CABLE_NOT_PORT_RE = re.compile(
    r"\bUSB[- ]?C\b[^.]{0,40}\b(?:charging\s+)?cable\b"
    r"|\b(?:charging\s+)?cable\b[^.]{0,40}\bUSB[- ]?C\b",
    re.I,
)
_EXPLICIT_PORT_RE = re.compile(
    r"(?:charging\s+)?port\s*(?:is|:|of)?\s*(?:USB[- ]?C|USB Type-C|Type-C|Micro-USB|Micro USB)"
    r"|(?:USB[- ]?C|USB Type-C|Type-C|Micro-USB|Micro USB)\s+(?:charging\s+)?port",
    re.I,
)


def model_aliases(model: str) -> tuple[str, ...]:
    """Longest-first aliases used to locate a model in page text."""
    key = " ".join((model or "").casefold().split())
    if not key:
        return ()
    aliases = [key]
    parts = key.split(None, 1)
    if len(parts) == 2 and parts[1] not in aliases:
        aliases.append(parts[1])
    # Compact PDF / URL style: "IdeaPad_Slim_3"
    underscored = key.replace(" ", "_")
    if underscored not in aliases:
        aliases.append(underscored)
    if len(parts) == 2:
        brandless_us = parts[1].replace(" ", "_")
        if brandless_us not in aliases:
            aliases.append(brandless_us)
    # Stable unique, longest first for span search.
    uniq = sorted(set(aliases), key=len, reverse=True)
    return tuple(uniq)


def find_model_spans(text: str, model: str) -> list[tuple[int, int]]:
    """Return case-insensitive [start, end) spans for model aliases in text."""
    if not text or not model:
        return []
    lowered = text.casefold()
    spans: list[tuple[int, int]] = []
    for alias in model_aliases(model):
        start = 0
        while True:
            idx = lowered.find(alias, start)
            if idx < 0:
                break
            end = idx + len(alias)
            spans.append((idx, end))
            start = idx + 1
    spans.sort()
    # Drop spans fully contained in a longer earlier span.
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start >= merged[-1][0] and end <= merged[-1][1]:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def model_local_text(
    text: str,
    model: str | None,
    *,
    radius: int = MODEL_WINDOW_RADIUS,
) -> str:
    """Concatenate windows around each model mention. Empty if none found."""
    if not text or not model:
        return ""
    spans = find_model_spans(text, model)
    if not spans:
        return ""
    pieces: list[str] = []
    last_end = -1
    for start, end in spans:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        if left <= last_end:
            # Extend previous piece instead of duplicating overlap.
            pieces[-1] = pieces[-1] + text[last_end:right]
        else:
            pieces.append(text[left:right])
        last_end = right
    return "\n\n".join(pieces)


def claim_near_model(
    text: str,
    claim_start: int,
    claim_end: int,
    model: str | None,
    *,
    max_gap: int = CLAIM_MODEL_MAX_GAP,
) -> bool:
    """True when a model mention is within max_gap of the claim span."""
    if not model or claim_start < 0 or claim_end < claim_start:
        return False
    spans = find_model_spans(text, model)
    if not spans:
        return False
    for m_start, m_end in spans:
        if m_end < claim_start:
            gap = claim_start - m_end
        elif claim_end < m_start:
            gap = m_start - claim_end
        else:
            return True  # overlapping / nested
        if gap <= max_gap:
            return True
    return False


def supporting_text_tied_to_model(supporting_text: str | None, model: str | None) -> bool:
    """True when the snippet itself mentions the model (or brandless alias)."""
    if not supporting_text or not model:
        return False
    collapsed = " ".join(supporting_text.split()).casefold()
    return any(alias in collapsed for alias in model_aliases(model) if " " in alias or len(alias) >= 4)


def model_linked_snippet(
    text: str,
    match: re.Match[str],
    model: str | None,
    *,
    radius: int = 90,
) -> str:
    """Snippet around a claim that also includes a nearby model mention when possible."""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    if model:
        spans = find_model_spans(text, model)
        nearest = None
        best_gap = None
        for m_start, m_end in spans:
            if m_end < match.start():
                gap = match.start() - m_end
            elif match.end() < m_start:
                gap = m_start - match.end()
            else:
                gap = 0
            if best_gap is None or gap < best_gap:
                best_gap = gap
                nearest = (m_start, m_end)
        if nearest is not None and best_gap is not None and best_gap <= CLAIM_MODEL_MAX_GAP:
            start = min(start, max(0, nearest[0] - 20))
            end = max(end, min(len(text), nearest[1] + 20))
            # Keep snippets readable for the UI / auditor.
            if end - start > 320:
                # Prefer keeping the claim; trim the far side.
                claim_mid = (match.start() + match.end()) // 2
                start = max(0, claim_mid - 160)
                end = min(len(text), claim_mid + 160)
                # Re-include model if still nearby after trim.
                if nearest[0] >= start - 40 and nearest[1] <= end + 40:
                    start = min(start, nearest[0])
                    end = max(end, nearest[1])
    return re.sub(r"\s+", " ", text[start:end]).strip()


def looks_like_cable_not_port(text: str | None) -> bool:
    """USB-C cable wording without an explicit charging-port claim."""
    if not text or not text.strip():
        return False
    if _EXPLICIT_PORT_RE.search(text):
        return False
    return bool(_CABLE_NOT_PORT_RE.search(text))


def preparation_text_for_extraction(text: str, model: str | None) -> str:
    """Prefer model-local windows; fall back to full page if model is absent."""
    local = model_local_text(text, model)
    return local if local.strip() else text
