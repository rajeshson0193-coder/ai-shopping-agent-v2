"""ShopBuddy landing helpers — visual mirror of shopbuddy-discovery index.tsx."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
BRANDS = ASSETS / "brands"
LANDING_CSS = ROOT / "landing.css"
HERO_IMAGE = ASSETS / "hero-products.jpg"
LOGO_IMAGE = ASSETS / "logo.svg"

# Labels match shopbuddy-discovery; queries map to supported categories.
EXAMPLE_CHIPS: tuple[tuple[str, str], ...] = (
    ("Headphones under $60", "best wireless headphones under $60"),
    ("Laptops under $500", "best laptop under $500"),
    ("Smartwatches", "best wireless earbuds under $100"),
)

BRAND_FILES: tuple[tuple[str, str, str], ...] = (
    ("Amazon", "amazon.svg", "h7"),
    ("eBay", "ebay.svg", "h8"),
    ("Walmart", "walmart.svg", "h9"),
    ("Best Buy", "bestbuy.svg", "h8"),
    ("Target", "target.svg", "h9"),
    ("Newegg", "newegg.svg", "h10"),
)

_BAG_ICON = """
<svg viewBox="0 0 24 24" aria-hidden="true">
  <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/>
  <path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>
</svg>
"""

_SEARCH_ICON = """
<svg viewBox="0 0 24 24" aria-hidden="true">
  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
</svg>
"""


@lru_cache(maxsize=32)
def _data_uri(path: str, mime: str, mtime: float = 0.0) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def data_uri(path: Path, mime: str) -> str | None:
    if not path.exists():
        return None
    return _data_uri(str(path), mime, path.stat().st_mtime)


def inject_landing_styles(*, busy: bool = False) -> None:
    if LANDING_CSS.exists():
        st.html(LANDING_CSS)
    script = (
        "document.body.classList.add('sb-busy');"
        if busy
        else "document.body.classList.remove('sb-busy');"
    )
    st.html(f"<script>{script}</script>", unsafe_allow_javascript=True)


def render_header(*, ollama_up: bool) -> None:
    label = "Powered by Local AI" if ollama_up else "Local AI offline"
    st.html(
        f"""
        <div class="sb-header">
          <div class="sb-brand">
            <span class="sb-brand-mark">{_BAG_ICON}</span>
            <span class="sb-brand-name">ShopBuddy</span>
          </div>
          <span class="sb-local-ai"><i></i> {label}</span>
        </div>
        """
    )


def render_hero_title() -> None:
    hero = data_uri(HERO_IMAGE, "image/jpeg")
    img = (
        f'<img class="sb-hero-img" src="{hero}" width="1200" height="800" '
        'alt="Headphones, earbuds, laptop and smartwatch"/>'
        if hero
        else ""
    )
    # Self-contained centered block: Streamlit does not nest later widgets
    # inside open HTML wrappers, so centering must live on this element.
    st.html(
        f"""
        <div class="sb-hero-block">
          {img}
          <p class="sb-eyebrow">Shopping Research AI Agent</p>
          <h1 class="sb-title">Shop Smarter with AI<span>.</span></h1>
        </div>
        """
    )


def render_brand_footer() -> None:
    logos: list[str] = []
    for name, filename, height_class in BRAND_FILES:
        uri = data_uri(BRANDS / filename, "image/svg+xml")
        if not uri:
            continue
        logos.append(
            f'<img class="{height_class}" src="{uri}" alt="{name} logo" title="{name}"/>'
        )
    st.html(
        f"""
        <div class="sb-footer">
          <div class="sb-brands">
            {"".join(logos)}
          </div>
        </div>
        """
    )


def search_icon_html() -> str:
    return f'<span class="sb-search-icon">{_SEARCH_ICON}</span>'



def render_search_progress(message: str = "Researching…") -> None:
    """Show an in-view spinner under the Search button (no scroll needed)."""
    st.html(
        f"""
        <div class="sb-progress">
          <span class="sb-spinner" aria-hidden="true"></span>
          <div class="sb-progress-copy">
            <strong>Searching</strong>
            <span>{message}</span>
          </div>
        </div>
        """
    )
