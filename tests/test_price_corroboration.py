from decimal import Decimal

from shopping_agent.http_fetch import PageFetch
from shopping_agent.models import ProductCandidate, VerificationStatus
from shopping_agent.retailer_pages import corroborate_listed_price, delivered_total_from_text


def _page(url, html, text):
    return PageFetch(url, "ok", 200, text, "Page text retrieved", html=html)


def test_matching_jsonld_price_verifies_listed_price_only():
    html = """
    <html><script type="application/ld+json">
    {"@type":"Product","offers":{"@type":"Offer","price":"429.00","priceCurrency":"USD"}}
    </script><p>Shipping calculated at checkout</p></html>
    """
    candidate = ProductCandidate(
        name="Dell Inspiron 15 Laptop",
        model="Dell Inspiron 15",
        product_url="https://www.walmart.com/ip/example",
        source="serpapi",
        listed_price=Decimal("429.00"),
        price_status=VerificationStatus.UNKNOWN,
    )

    def fetch(url, timeout=12):
        return _page(url, html, "Dell Inspiron 15 Laptop. Shipping calculated at checkout.")

    corroborate_listed_price(candidate, fetch=fetch)
    assert candidate.price_status == VerificationStatus.VERIFIED
    assert candidate.delivered_total_status == VerificationStatus.UNKNOWN


def test_different_jsonld_price_is_conflicting():
    html = """
    <html><script type="application/ld+json">
    {"offers":{"price":"499.00","priceCurrency":"USD"}}
    </script></html>
    """
    candidate = ProductCandidate(
        name="Dell Inspiron 15 Laptop",
        model="Dell Inspiron 15",
        product_url="https://www.walmart.com/ip/example",
        source="serpapi",
        listed_price=Decimal("429.00"),
        price_status=VerificationStatus.UNKNOWN,
    )

    def fetch(url, timeout=12):
        return _page(url, html, "Dell Inspiron 15")

    corroborate_listed_price(candidate, fetch=fetch)
    assert candidate.price_status == VerificationStatus.CONFLICTING
    assert candidate.listed_price == Decimal("429.00")


def test_order_total_wording_sets_delivered_total():
    assert delivered_total_from_text("Shipping $20. Order total $449.00 today") == Decimal("449.00")
    assert delivered_total_from_text("Free shipping on this laptop") is None


def test_blocked_retailer_page_stays_inaccessible():
    candidate = ProductCandidate(
        name="Dell Inspiron 15 Laptop",
        model="Dell Inspiron 15",
        product_url="https://www.walmart.com/ip/example",
        source="serpapi",
        listed_price=Decimal("429.00"),
        price_status=VerificationStatus.UNKNOWN,
    )

    def fetch(url, timeout=12):
        return PageFetch(url, "blocked", 403, "", "HTTP 403: page refused automated access; not retried")

    corroborate_listed_price(candidate, fetch=fetch)
    assert candidate.price_status == VerificationStatus.UNKNOWN
    access = [item for item in candidate.evidence if item.field_name == "retailer_page_accessibility"]
    assert access[-1].status == VerificationStatus.INACCESSIBLE
