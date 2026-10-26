from decimal import Decimal
from unittest.mock import patch

from shopping_agent.discover import serpapi
from shopping_agent.models import ShoppingRequest


def test_resolves_google_shell_to_retailer_offer():
    shopping_payload = {
        "shopping_results": [
            {
                "title": "Acer Nitro V 16 Gaming Laptop Intel Core 7",
                "product_id": "12345",
                "immersive_product_page_token": "token-abc",
                "product_link": "https://www.google.com/search?ibp=oshop&q=acer",
                "extracted_price": 899.0,
            }
        ]
    }
    immersive_payload = {
        "product_results": {
            "stores": [
                {
                    "name": "Best Buy",
                    "link": "https://www.bestbuy.com/site/acer-nitro-v/123",
                    "extracted_price": 899.0,
                    "price": "$899.00",
                },
                {
                    "name": "Random Shop",
                    "link": "https://unknown-shop.example/item/1",
                    "extracted_price": 850.0,
                },
            ]
        }
    }

    def fake_get(params, timeout):
        if params.get("engine") == "google_shopping":
            return shopping_payload
        if params.get("engine") == "google_immersive_product":
            return immersive_payload
        raise RuntimeError("unexpected engine")

    request = ShoppingRequest(
        raw_text="best laptop under 1000",
        category="laptop",
        budget=Decimal("1000"),
    )
    with patch.dict(
        "os.environ",
        {
            "SERPAPI_API_KEY": "test-key",
            "SERPAPI_MAX_SHOPPING_QUERIES": "1",
            "SERPAPI_MAX_DETAIL_CALLS": "3",
        },
    ):
        with patch.object(serpapi, "_get_json", side_effect=fake_get) as mocked:
            candidates = serpapi.search_products(request, max_results=5, timeout=5)
            # 1 shopping + 1 immersive detail
            assert mocked.call_count == 2

    assert len(candidates) == 1
    assert candidates[0].product_url.startswith("https://www.bestbuy.com/")
    assert candidates[0].listed_price == Decimal("899.0")
    assert "google.com" not in candidates[0].product_url


def test_skips_hits_without_known_retailer_offers():
    shopping_payload = {
        "shopping_results": [
            {
                "title": "Mystery Laptop",
                "product_id": "999",
                "product_link": "https://www.google.com/search?q=mystery",
                "extracted_price": 400,
            }
        ]
    }
    product_payload = {"product_results": {"stores": [{"name": "X", "link": "https://weird.example/a", "extracted_price": 400}]}}

    def fake_get(params, timeout):
        if params.get("engine") == "google_shopping":
            return shopping_payload
        return product_payload

    request = ShoppingRequest(raw_text="best laptop under 1000", category="laptop", budget=Decimal("1000"))
    with patch.dict(
        "os.environ",
        {
            "SERPAPI_API_KEY": "test-key",
            "SERPAPI_MAX_SHOPPING_QUERIES": "1",
            "SERPAPI_MAX_DETAIL_CALLS": "3",
        },
    ):
        with patch.object(serpapi, "_get_json", side_effect=fake_get):
            assert serpapi.search_products(request, max_results=5, timeout=5) == []


def test_zero_shopping_queries_spends_nothing():
    request = ShoppingRequest(raw_text="best laptop under 1000", category="laptop", budget=Decimal("1000"))
    with patch.dict(
        "os.environ",
        {"SERPAPI_API_KEY": "test-key", "SERPAPI_MAX_SHOPPING_QUERIES": "0"},
    ):
        with patch.object(serpapi, "_get_json") as mocked:
            assert serpapi.search_products(request, max_results=5, timeout=5) == []
            mocked.assert_not_called()


def test_default_budget_is_five_calls_split_one_plus_four():
    with patch.dict("os.environ", {}, clear=True):
        shopping, detail, total = serpapi.allocate_call_budget()
    assert total == 5
    assert shopping == 1
    assert detail == 4


def test_hard_cap_never_exceeds_max_calls():
    shopping_payload = {
        "shopping_results": [
            {
                "title": f"Laptop {i}",
                "product_id": str(1000 + i),
                "immersive_product_page_token": f"token-{i}",
                "extracted_price": 500 + i,
            }
            for i in range(20)
        ]
    }
    immersive_payload = {
        "product_results": {
            "stores": [
                {
                    "name": "Best Buy",
                    "link": "https://www.bestbuy.com/site/item/1",
                    "extracted_price": 520.0,
                }
            ]
        }
    }

    def fake_get(params, timeout):
        if params.get("engine") == "google_shopping":
            return shopping_payload
        return immersive_payload

    request = ShoppingRequest(
        raw_text="best laptop under 1000",
        category="laptop",
        budget=Decimal("1000"),
    )
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"}, clear=True):
        with patch.object(serpapi, "_get_json", side_effect=fake_get) as mocked:
            candidates = serpapi.search_products(
                request, max_results=20, timeout=5, max_calls_override=5
            )
            assert mocked.call_count <= 5
    assert len(candidates) <= 4  # 1 shopping + up to 4 detail slots
