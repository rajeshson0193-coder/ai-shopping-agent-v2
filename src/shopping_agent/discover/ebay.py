"""Read-only eBay Browse API discovery. Used only when credentials are set."""

from __future__ import annotations

import base64
import json
import os
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
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

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


def credentials_configured() -> bool:
    return bool(os.environ.get("EBAY_CLIENT_ID", "").strip() and os.environ.get("EBAY_CLIENT_SECRET", "").strip())


def _request_json(request: Request, timeout: int) -> dict:
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"eBay API returned HTTP {exc.code}: {detail}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not complete eBay request: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise RuntimeError("eBay API returned an unexpected response.")
    return data


def _access_token(timeout: int) -> str:
    client_id = os.environ["EBAY_CLIENT_ID"].strip()
    client_secret = os.environ["EBAY_CLIENT_SECRET"].strip()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
    body = urlencode({"grant_type": "client_credentials", "scope": OAUTH_SCOPE}).encode("ascii")
    request = Request(
        TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    data = _request_json(request, timeout)
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("eBay OAuth response contained no access token.")
    return token


def _item_to_candidate(item: dict, retrieved_at) -> ProductCandidate | None:
    title = item.get("title")
    url = item.get("itemWebUrl")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(url, str) or not url.startswith("https://"):
        return None

    price_info = item.get("price") if isinstance(item.get("price"), dict) else {}
    price = None
    raw_price = price_info.get("value")
    if raw_price not in (None, ""):
        try:
            parsed = Decimal(str(raw_price))
        except (InvalidOperation, ValueError):
            parsed = None
        if parsed is not None and parsed.is_finite() and parsed >= 0:
            price = parsed
    currency = str(price_info.get("currency") or "USD")
    condition = item.get("condition") if isinstance(item.get("condition"), str) else None
    evidence = [
        Evidence(
            field_name="discovery",
            status=VerificationStatus.UNKNOWN,
            value=title.strip(),
            source_url=url,
            source_type="ebay_browse_api",
            supporting_text=f"eBay Browse API listing title: {title.strip()}",
            retrieved_at=retrieved_at,
        )
    ]
    if price is not None:
        evidence.append(
            Evidence(
                field_name="listed_price",
                status=VerificationStatus.UNKNOWN,
                value=price,
                source_url=url,
                source_type="ebay_browse_api_offer_price",
                supporting_text=(
                    f"eBay Browse API reports {price} {currency} for this listing. "
                    "This is the API-reported item price, not shipping, tax, or checkout total."
                ),
                retrieved_at=retrieved_at,
            )
        )
    if condition:
        evidence.append(
            Evidence(
                field_name="condition",
                status=VerificationStatus.VERIFIED,
                value=condition,
                source_url=url,
                source_type="ebay_browse_api_condition",
                supporting_text=f"eBay Browse API condition: {condition}",
                retrieved_at=retrieved_at,
            )
        )
    return ProductCandidate(
        name=title.strip(),
        product_url=url,
        source="ebay",
        listed_price=price,
        currency=currency,
        price_status=VerificationStatus.UNKNOWN,
        condition=condition,
        condition_status=VerificationStatus.VERIFIED if condition else VerificationStatus.UNKNOWN,
        evidence=evidence,
    )


def search_products(
    request: ShoppingRequest,
    max_results: int = 10,
    timeout: int = 30,
    profile: CategoryProfile | None = None,
) -> list[ProductCandidate]:
    if not credentials_configured():
        raise RuntimeError("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to enable live eBay discovery.")
    if request.market.upper() != "US" or request.currency != "USD":
        raise ValueError("eBay adapter currently supports US/USD only.")

    if profile is None:
        profile = get_profile(request.category)

    token = _access_token(timeout)
    queries = profile.discovery_queries(request)
    retrieved_at = utc_now()
    by_url: dict[str, ProductCandidate] = {}
    recognizable: list[ProductCandidate] = []
    fallback: list[ProductCandidate] = []
    # Pull enough per query that multi-query earbud/laptop discovery can fill a shortlist.
    per_query = max(3, min(12, max_results))

    for query in queries:
        params = urlencode(
            {
                "q": query,
                "filter": f"price:[0..{request.budget}],priceCurrency:USD",
                "limit": str(per_query),
            }
        )
        http_request = Request(
            f"{SEARCH_URL}?{params}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            data = _request_json(http_request, timeout)
        except RuntimeError:
            continue
        items = data.get("itemSummaries", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = _item_to_candidate(item, retrieved_at)
            if candidate is None or candidate.product_url in by_url:
                continue
            by_url[candidate.product_url] = candidate
            _brand, model, _configuration = profile.extract_identity(candidate.name)
            if model:
                recognizable.append(candidate)
            else:
                fallback.append(candidate)

    # Prefer listings with an extractable model so ranking has something to work with.
    ordered = recognizable + fallback
    return ordered[:max_results]
