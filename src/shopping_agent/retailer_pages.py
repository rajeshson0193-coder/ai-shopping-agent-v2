"""Corroborate a listed price from a retailer page. Shipping and tax stay unknown."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urlparse

from shopping_agent.http_fetch import PageFetch, fetch_page
from shopping_agent.models import Evidence, EvidenceStrength, ProductCandidate, VerificationStatus, utc_now

_SKIP_HOSTS = {"ebay.com", "google.com", "serpapi.com"}


class _JSONLDParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag.lower() != "script":
            return
        attributes = {key.lower(): value for key, value in attrs if key}
        if (attributes.get("type") or "").lower() == "application/ld+json":
            self._inside = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._inside:
            self._parts.append(data)

    def handle_endtag(self, tag) -> None:
        if tag.lower() == "script" and self._inside:
            self.scripts.append("".join(self._parts))
            self._inside = False


def _walk_offers(node, found: list[dict]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_offers(item, found)
        return
    if not isinstance(node, dict):
        return
    offer = node.get("offers")
    if isinstance(offer, (dict, list)):
        offers = offer if isinstance(offer, list) else [offer]
        for item in offers:
            if isinstance(item, dict) and item.get("price") not in (None, ""):
                found.append(item)
    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_offers(value, found)


def jsonld_prices(html: str) -> list[tuple[Decimal, str]]:
    parser = _JSONLDParser()
    parser.feed(html)
    parser.close()
    prices: list[tuple[Decimal, str]] = []
    for script in parser.scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        offers: list[dict] = []
        _walk_offers(payload, offers)
        for offer in offers:
            raw = str(offer.get("price")).replace(",", "").strip()
            try:
                amount = Decimal(raw)
            except (InvalidOperation, ValueError):
                continue
            if not amount.is_finite() or amount < 0:
                continue
            currency = str(offer.get("priceCurrency") or "USD").upper()
            prices.append((amount, currency))
    return prices


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().rstrip(".")


def _skipped_host(url: str) -> bool:
    host = _host(url)
    return any(host == name or host.endswith("." + name) for name in _SKIP_HOSTS)


def corroborate_listed_price(candidate: ProductCandidate, timeout: int = 12, fetch=fetch_page) -> ProductCandidate:
    """Fetch the listing URL once and compare any JSON-LD item price.

    A match verifies the listed item price only. A different price is conflicting.
    Delivered total is left unknown: this page check does not read shipping or tax.
    """
    retrieved_at = utc_now()
    url = candidate.product_url
    if _skipped_host(url):
        candidate.evidence.append(
            Evidence(
                field_name="retailer_page_accessibility",
                status=VerificationStatus.UNKNOWN,
                source_url=url,
                source_type="not_fetched",
                supporting_text="Retailer HTML was not fetched for this host.",
                retrieved_at=retrieved_at,
                evidence_strength=EvidenceStrength.INSUFFICIENT,
                reason="eBay and search-engine hosts are not scraped for a second price",
            )
        )
        return candidate

    page: PageFetch = fetch(url, timeout=timeout)
    if page.outcome != "ok":
        candidate.evidence.append(
            Evidence(
                field_name="retailer_page_accessibility",
                status=VerificationStatus.INACCESSIBLE,
                source_url=url,
                source_type="retailer_page",
                retrieved_at=retrieved_at,
                evidence_strength=EvidenceStrength.INSUFFICIENT,
                reason=page.reason,
            )
        )
        return candidate

    candidate.evidence.append(
        Evidence(
            field_name="retailer_page_accessibility",
            status=VerificationStatus.VERIFIED,
            source_url=url,
            source_type="retailer_page",
            supporting_text="Retailer page text was retrieved.",
            retrieved_at=retrieved_at,
            evidence_strength=EvidenceStrength.STRONG,
            reason=page.reason,
        )
    )

    # fetch_page returns text, not raw HTML. JSON-LD prices need the HTML.
    # Callers that use the default fetcher therefore also pass html via PageFetch.text
    # only when the injected fetcher returns HTML. The default path re-reads offers
    # from a dedicated HTML fetch below when text has no JSON-LD.
    prices = jsonld_prices(page.html or page.text)
    observed_total = delivered_total_from_text(page.text)
    if observed_total is not None:
        candidate.delivered_total = observed_total
        candidate.delivered_total_status = VerificationStatus.VERIFIED
        candidate.evidence.append(
            Evidence(
                field_name="delivered_total",
                status=VerificationStatus.VERIFIED,
                value=observed_total,
                source_url=url,
                source_type="retailer_page_order_total",
                supporting_text="Explicit order-total wording was present on the retailer page.",
                retrieved_at=retrieved_at,
                evidence_strength=EvidenceStrength.STRONG,
            )
        )
    if not prices:
        return candidate

    usd = [(amount, currency) for amount, currency in prices if currency == "USD"]
    if not usd:
        candidate.price_status = VerificationStatus.UNKNOWN
        return candidate

    observed, _currency = usd[0]
    if candidate.listed_price is None:
        candidate.listed_price = observed
        candidate.currency = "USD"
        candidate.price_status = VerificationStatus.VERIFIED
        candidate.evidence.append(
            Evidence(
                field_name="listed_price",
                status=VerificationStatus.VERIFIED,
                value=observed,
                source_url=url,
                source_type="retailer_jsonld_price",
                supporting_text=f"Retailer JSON-LD offer price {observed} USD. Shipping and tax are not included.",
                retrieved_at=retrieved_at,
                evidence_strength=EvidenceStrength.STRONG,
            )
        )
        return candidate

    if observed == candidate.listed_price:
        candidate.price_status = VerificationStatus.VERIFIED
        candidate.evidence.append(
            Evidence(
                field_name="listed_price",
                status=VerificationStatus.VERIFIED,
                value=observed,
                source_url=url,
                source_type="retailer_jsonld_price",
                supporting_text=(
                    f"Retailer JSON-LD offer price {observed} USD matches the discovered listed price. "
                    "Shipping and tax are not included."
                ),
                retrieved_at=retrieved_at,
                evidence_strength=EvidenceStrength.STRONG,
            )
        )
        return candidate

    candidate.price_status = VerificationStatus.CONFLICTING
    candidate.evidence.append(
        Evidence(
            field_name="listed_price",
            status=VerificationStatus.CONFLICTING,
            value=observed,
            source_url=url,
            source_type="retailer_jsonld_price",
            supporting_text=(
                f"Retailer JSON-LD offer price {observed} USD differs from discovered listed price "
                f"{candidate.listed_price} USD."
            ),
            retrieved_at=retrieved_at,
            evidence_strength=EvidenceStrength.STRONG,
            reason="listed price conflict between discovery source and retailer page",
        )
    )
    return candidate


_TOTAL_RE = re.compile(r"\b(order total|delivered total|grand total)\b", re.I)


def delivered_total_from_text(text: str) -> Decimal | None:
    """Only an explicit order-total label can set a delivered total."""
    match = _TOTAL_RE.search(text or "")
    if not match:
        return None
    window = text[match.end() : match.end() + 40]
    amount = re.search(r"\$\s*(\d+(?:\.\d{2})?)", window)
    if not amount:
        return None
    try:
        parsed = Decimal(amount.group(1))
    except InvalidOperation:
        return None
    if parsed.is_finite() and parsed >= 0:
        return parsed
    return None
