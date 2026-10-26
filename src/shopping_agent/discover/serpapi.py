"""SerpApi Google Shopping discovery with strict monthly-quota controls.

Each SerpApi HTTP request counts against the plan. Defaults keep eBay as the
main discovery source and SerpApi as a small supplement:

- SERPAPI_MAX_CALLS=5 total HTTP requests per run (laptop or headphones)
- Default split: 1 shopping search + up to 4 product-detail lookups

Optional overrides:
- SERPAPI_MAX_SHOPPING_QUERIES
- SERPAPI_MAX_DETAIL_CALLS
Both are clamped so shopping + detail never exceeds SERPAPI_MAX_CALLS.
"""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from shopping_agent.models import (
    Evidence,
    ProductCandidate,
    ShoppingRequest,
    VerificationStatus,
    utc_now,
)
from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.registry import get_profile

SEARCH_URL = "https://serpapi.com/search.json"
DEFAULT_MAX_CALLS = 5


class SerpapiBudgetExhausted(RuntimeError):
    """Raised when the per-run SerpApi HTTP call cap is reached."""


def credentials_configured() -> bool:
    return bool(os.environ.get("SERPAPI_API_KEY", "").strip())


def _api_key() -> str:
    return os.environ["SERPAPI_API_KEY"].strip()


def _positive_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def max_calls(override: int | None = None) -> int:
    if override is not None:
        return max(0, int(override))
    return _positive_env("SERPAPI_MAX_CALLS", DEFAULT_MAX_CALLS)


def allocate_call_budget(max_calls_override: int | None = None) -> tuple[int, int, int]:
    """Return (shopping_queries, detail_calls, total_cap).

    Default for total=5: 1 shopping + 4 detail. eBay should supply the rest of
    the candidate pool.
    """
    total = max_calls(max_calls_override)
    if total <= 0:
        return 0, 0, 0

    shopping_raw = os.environ.get("SERPAPI_MAX_SHOPPING_QUERIES", "").strip()
    detail_raw = os.environ.get("SERPAPI_MAX_DETAIL_CALLS", "").strip()

    if shopping_raw != "" or detail_raw != "":
        shopping = _positive_env("SERPAPI_MAX_SHOPPING_QUERIES", 1)
        detail = _positive_env("SERPAPI_MAX_DETAIL_CALLS", max(0, total - 1))
    else:
        shopping = 1
        detail = max(0, total - shopping)

    shopping = min(shopping, total)
    detail = min(detail, max(0, total - shopping))
    return shopping, detail, total


def max_shopping_queries() -> int:
    shopping, _detail, _total = allocate_call_budget()
    return shopping


def max_detail_calls() -> int:
    _shopping, detail, _total = allocate_call_budget()
    return detail


def _get_json(params: dict, timeout: int) -> dict:
    request = Request(
        f"{SEARCH_URL}?{urlencode(params)}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"SerpApi returned HTTP {exc.code}: {detail}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not complete SerpApi request: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise RuntimeError("SerpApi returned an unexpected response.")
    if data.get("error"):
        raise RuntimeError(f"SerpApi error: {data['error']}")
    return data


def _price(value) -> Decimal | None:
    if value in (None, "", True, False):
        return None
    if isinstance(value, (int, float, Decimal)):
        parsed = Decimal(str(value))
    elif isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d{1,2})?)", cleaned)
        if not match:
            return None
        try:
            parsed = Decimal(match.group(1))
        except InvalidOperation:
            return None
    else:
        return None
    if parsed.is_finite() and parsed >= 0:
        return parsed
    return None


def _product_id(item: dict) -> str | None:
    direct = item.get("product_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    for key in ("product_link", "link"):
        link = item.get(key)
        if isinstance(link, str):
            match = re.search(r"(?:catalogid|productid):(\d+)", link)
            if match:
                return match.group(1)
    return None


def _known_retailer(url: str, domains: frozenset[str]) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _is_google_shell(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return host.endswith("google.com") or host.endswith("serpapi.com")


def _stores_from_payload(payload: dict) -> list[dict]:
    product = payload.get("product_results")
    if not isinstance(product, dict):
        product = payload
    stores = product.get("stores")
    if isinstance(stores, list):
        return [store for store in stores if isinstance(store, dict)]
    return []


def _resolve_offers(
    item: dict,
    timeout: int,
    retailer_domains: frozenset[str],
    get_json=_get_json,
) -> list[tuple[Decimal, str, str, dict]]:
    """One detail API call only: Immersive token preferred, else product_id."""
    offers: list[tuple[Decimal, str, str, dict]] = []
    token = item.get("immersive_product_page_token")
    product_id = _product_id(item)
    payload: dict | None = None

    if isinstance(token, str) and token.strip():
        try:
            payload = get_json(
                {
                    "engine": "google_immersive_product",
                    "page_token": token.strip(),
                    "more_stores": "true",
                    "api_key": _api_key(),
                },
                timeout,
            )
        except SerpapiBudgetExhausted:
            raise
        except RuntimeError:
            payload = None
    elif product_id:
        try:
            payload = get_json(
                {
                    "engine": "google_product",
                    "product_id": product_id,
                    "offers": "1",
                    "gl": "us",
                    "hl": "en",
                    "api_key": _api_key(),
                },
                timeout,
            )
        except SerpapiBudgetExhausted:
            raise
        except RuntimeError:
            payload = None

    if payload is None:
        return offers

    for store in _stores_from_payload(payload):
        url = store.get("link")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        if _is_google_shell(url) or not _known_retailer(url, retailer_domains):
            continue
        price = _price(store.get("extracted_price") or store.get("price"))
        if price is None:
            continue
        merchant = str(store.get("name") or urlparse(url).hostname or "retailer")
        offers.append((price, url, merchant, store))
    return offers


def search_products(
    request: ShoppingRequest,
    max_results: int = 10,
    timeout: int = 30,
    profile: CategoryProfile | None = None,
    max_calls_override: int | None = None,
) -> list[ProductCandidate]:
    if not credentials_configured():
        raise RuntimeError("Set SERPAPI_API_KEY to enable live SerpApi discovery.")

    if profile is None:
        profile = get_profile(request.category)

    query_limit, detail_limit, total_cap = allocate_call_budget(max_calls_override)
    if query_limit == 0 or total_cap == 0:
        return []

    # Hard stop: never spend more than total_cap HTTP requests in one run.
    calls_used = 0

    def budgeted_get(params: dict, request_timeout: int) -> dict:
        nonlocal calls_used
        if calls_used >= total_cap:
            raise SerpapiBudgetExhausted(f"SerpApi call budget exhausted ({total_cap} max).")
        calls_used += 1
        return _get_json(params, request_timeout)

    all_queries = profile.discovery_queries(request) or [profile.discovery_search_query(request)]
    # Keep the SerpApi query list short for monthly quota.
    queries = all_queries[:query_limit]

    shopping_hits: list[dict] = []
    seen_keys: set[str] = set()

    for query in queries:
        if calls_used >= total_cap:
            break
        try:
            data = budgeted_get(
                {
                    "engine": "google_shopping",
                    "q": query,
                    "max_price": str(int(request.budget)),
                    "api_key": _api_key(),
                    "gl": "us",
                    "hl": "en",
                    "num": str(min(10, max(max_results, 5))),
                },
                timeout,
            )
        except SerpapiBudgetExhausted:
            break
        results = data.get("shopping_results", [])
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            key = _product_id(item) or str(item.get("immersive_product_page_token") or item.get("title"))
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            shopping_hits.append(item)

    retrieved_at = utc_now()
    candidates: list[ProductCandidate] = []
    seen_urls: set[str] = set()
    details_used = 0
    # Cap offer resolution by remaining budget and requested result count.
    effective_detail_limit = min(detail_limit, max(0, total_cap - calls_used), max_results)

    for item in shopping_hits:
        if len(candidates) >= max_results:
            break
        if details_used >= effective_detail_limit or calls_used >= total_cap:
            break
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            continue

        details_used += 1
        try:
            offers = _resolve_offers(
                item,
                timeout,
                profile.known_retailer_domains,
                get_json=budgeted_get,
            )
        except SerpapiBudgetExhausted:
            break

        under_budget = [offer for offer in offers if offer[0] <= request.budget]
        if not under_budget:
            continue
        price, url, merchant, store = min(under_budget, key=lambda row: row[0])
        if url in seen_urls:
            continue
        seen_urls.add(url)

        condition = None
        condition_status = VerificationStatus.UNKNOWN
        second_hand = item.get("second_hand_condition") or store.get("tag")
        if isinstance(second_hand, str) and second_hand.strip():
            condition = second_hand.strip()
            condition_status = VerificationStatus.UNKNOWN

        evidence = [
            Evidence(
                field_name="discovery",
                status=VerificationStatus.UNKNOWN,
                value=title.strip(),
                source_url=url,
                source_type="serpapi_google_product_offer",
                supporting_text=(
                    f"SerpApi Google Shopping title: {title.strip()} — offer from {merchant}. "
                    f"Quota mode: max_calls={total_cap}, shopping<={query_limit}, "
                    f"detail_used={details_used}/{effective_detail_limit}, http_used={calls_used}."
                ),
                retrieved_at=retrieved_at,
            ),
            Evidence(
                field_name="listed_price",
                status=VerificationStatus.UNKNOWN,
                value=price,
                source_url=url,
                source_type="serpapi_google_product_offer_price",
                supporting_text=(
                    f"SerpApi reports {price} USD from {merchant}. "
                    "This is an unverified search-result price until the retailer page corroborates it."
                ),
                retrieved_at=retrieved_at,
            ),
        ]
        candidates.append(
            ProductCandidate(
                name=title.strip(),
                product_url=url,
                source="serpapi",
                listed_price=price,
                currency="USD",
                price_status=VerificationStatus.UNKNOWN,
                condition=condition,
                condition_status=condition_status,
                evidence=evidence,
            )
        )
    return candidates
