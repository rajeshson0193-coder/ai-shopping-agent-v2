from shopping_agent.http_fetch import PageFetch
from shopping_agent.models import ProductCandidate, VerificationStatus
from shopping_agent.research import research_candidates

MANUFACTURER_HTML = """
<html><body>
<h1>Lenovo IdeaPad Slim 3</h1>
<p>Processor: Intel Core i5. Memory: 16 GB RAM. Storage: 512 GB SSD.</p>
<p>Display: 15.6-inch FHD. Graphics: Integrated Intel graphics.</p>
<p>Battery life up to 14 hours.</p>
</body></html>
"""

PSREF_PDF_TEXT = (
    "IdeaPad Slim 3 15IRH10 Product Specifications Reference. "
    "Processor: Intel Core i5-13420H. Memory: Up to 16GB DDR5. "
    "Storage: 512GB M.2 SSD. Display: 15.6\" FHD. "
    "Graphics: Intel UHD Graphics. Max Battery Life Local video playback: 12 hr."
)


def _fetch(url, timeout=12):
    if "IdeaPad_Slim_3" in url and url.casefold().endswith(".pdf"):
        return PageFetch(url, "ok", 200, PSREF_PDF_TEXT, "Manufacturer PDF text retrieved")
    if "ideapad-slim-3" in url:
        return PageFetch(url, "blocked", 403, "", "HTTP 403: page refused automated access; not retried")
    if "pavilion" in url or "3V2M6EA" in url:
        return PageFetch(url, "blocked", 403, "", "HTTP 403: page refused automated access; not retried")
    if "inspiron-15" in url or "inspiron_3530" in url or "manual77626568" in url:
        return PageFetch(
            url,
            "ok",
            200,
            "Welcome to Dell laptops. Shop related products.",
            "Page text retrieved",
            html="<html>Welcome</html>",
        )
    return PageFetch(url, "http_error", 404, "", "HTTP 404")


def test_live_research_extracts_when_page_names_the_model():
    candidate = ProductCandidate(
        name="Lenovo IdeaPad Slim 3 Laptop 16GB RAM 512GB SSD",
        model="Lenovo IdeaPad Slim 3",
        product_url="https://www.ebay.com/itm/example",
        source="ebay",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=_fetch)
    assert candidate.specifications["ram_gb"].status == VerificationStatus.VERIFIED
    assert candidate.specifications["ram_gb"].value == "16"
    assert candidate.specifications["battery"].value == "12 hours"
    assert candidate.specifications["ram_gb"].source_type == "manufacturer_page"
    assert ".pdf" in (candidate.specifications["ram_gb"].source_url or "").casefold()


def test_live_research_falls_back_when_storefront_blocked():
    """Shop HTML 403 should not stop research if a later PDF hint succeeds."""

    def fetch(url, timeout=12):
        if "lenovo.com/us/en/p/" in url:
            return PageFetch(url, "blocked", 403, "", "HTTP 403: page refused automated access; not retried")
        if url.casefold().endswith(".pdf") and "IdeaPad_Slim_3" in url:
            return PageFetch(url, "ok", 200, PSREF_PDF_TEXT, "Manufacturer PDF text retrieved")
        return PageFetch(url, "http_error", 404, "", "HTTP 404")

    candidate = ProductCandidate(
        name="Lenovo IdeaPad Slim 3",
        model="Lenovo IdeaPad Slim 3",
        product_url="https://www.ebay.com/itm/example-fallback",
        source="ebay",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=fetch)
    assert candidate.specifications["cpu"].status == VerificationStatus.VERIFIED
    assert "i5" in (candidate.specifications["cpu"].value or "").casefold()


def test_dynamic_latitude_hint_is_fetched():
    html = (
        "<html><body><h1>Latitude 3500</h1>"
        "<p>Processor: Intel Core i5. Memory: 8 GB RAM. Storage: 256 GB SSD.</p>"
        "<p>Display: 15.6-inch FHD. Graphics: Intel UHD Graphics.</p></body></html>"
    )

    def fetch(url, timeout=12):
        if "latitude-3500" in url or "latitude-15-3500" in url or "latitude-14-3500" in url:
            return PageFetch(url, "ok", 200, html, "Page text retrieved", html=html)
        return PageFetch(url, "http_error", 404, "", "HTTP 404")

    candidate = ProductCandidate(
        name="Dell Latitude 3500 Laptop 8GB RAM 256GB SSD",
        model="Dell Latitude 3500",
        product_url="https://www.ebay.com/itm/example-latitude",
        source="ebay",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=fetch)
    assert candidate.specifications["cpu"].status == VerificationStatus.VERIFIED
    assert candidate.specifications["ram_gb"].value == "8"


def test_blocked_manufacturer_page_is_inaccessible_not_invented():
    candidate = ProductCandidate(
        name="HP Pavilion 15 Laptop",
        model="HP Pavilion 15",
        product_url="https://www.bestbuy.com/site/example",
        source="bestbuy",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=_fetch)
    assert candidate.specifications["cpu"].status == VerificationStatus.INACCESSIBLE
    assert candidate.specifications["cpu"].value is None
    assert "403" in (candidate.specifications["cpu"].reason or "")


def test_retrieved_page_without_model_does_not_supply_specs():
    candidate = ProductCandidate(
        name="Dell Inspiron 15 Laptop",
        model="Dell Inspiron 15",
        product_url="https://www.dell.com/example",
        source="dell",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=_fetch)
    assert candidate.specifications["cpu"].status == VerificationStatus.UNKNOWN
    assert "does not mention the exact model" in (candidate.specifications["cpu"].reason or "")


def test_research_prefers_manual_option_matching_listing_cpu():
    manual = (
        "Inspiron 15 3530 Owner's Manual. "
        "Processor type 13th Generation Intel Core i3-1305U "
        "13th Generation Intel Core i5-1334U "
        "13th Generation Intel Core i7-1355U. "
        "Memory 8 GB 16 GB DDR4. Storage capacity 512 GB SSD 1 TB SSD. "
        "Display 15.6-inch FHD. Graphics Intel Iris Xe Graphics."
    )

    def fetch(url, timeout=12):
        if "manual77626568" in url or url.casefold().endswith(".pdf"):
            return PageFetch(url, "ok", 200, manual, "Manufacturer PDF text retrieved")
        if "inspiron-15" in url:
            return PageFetch(url, "blocked", 403, "", "HTTP 403")
        return PageFetch(url, "http_error", 404, "", "HTTP 404")

    candidate = ProductCandidate(
        name="Dell Inspiron 15 i5-1334U 16GB RAM 512GB SSD",
        model="Dell Inspiron 15",
        configuration="16GB RAM / 512GB SSD",
        product_url="https://www.ebay.com/itm/inspiron-match",
        source="ebay",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=fetch)
    assert "i5-1334u" in (candidate.specifications["cpu"].value or "").casefold()
    assert candidate.specifications["ram_gb"].value == "16"
    assert candidate.specifications["storage"].value == "512GB SSD"


def test_wrong_chassis_manual_is_not_used_for_sku_identity():
    wrong = (
        "Inspiron 15 3530 Owner's Manual. "
        "Processor Intel Core i3-1305U. Memory 16 GB. Storage 512 GB SSD."
    )
    # Family page text that would previously have been accepted for any Inspiron 15.
    family_ok = wrong

    def fetch(url, timeout=12):
        if "3535" in url:
            # Simulate retrieving a page that only documents the sibling chassis.
            return PageFetch(url, "ok", 200, family_ok, "Manufacturer PDF text retrieved")
        if "3530" in url or "manual77626568" in url:
            return PageFetch(url, "ok", 200, wrong, "Manufacturer PDF text retrieved")
        return PageFetch(url, "http_error", 404, "", "HTTP 404")

    candidate = ProductCandidate(
        name="Dell Inspiron 15 3535 Ryzen 7 7730U 16GB 512GB SSD",
        model="Dell Inspiron 15 3535",
        configuration="16GB RAM / 512GB SSD",
        product_url="https://www.ebay.com/itm/inspiron-3535",
        source="ebay",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=fetch)
    assert candidate.specifications["cpu"].value is None
    assert candidate.specifications["cpu"].status in {
        VerificationStatus.UNKNOWN,
        VerificationStatus.INACCESSIBLE,
    }
    reason = candidate.specifications["cpu"].reason or ""
    assert "does not mention the exact model" in reason or "not retrieved" in reason.casefold()


def test_ryzen_ideapad_uses_amd_psref_when_available():
    amd_pdf = (
        "IdeaPad Slim 3 15ABR8 Product Specifications Reference. "
        "Processor AMD Ryzen 7 5825U. Memory Up to 16GB. "
        "Storage 512GB SSD. Display 15.6-inch FHD. "
        "Graphics AMD Radeon Graphics."
    )
    intel_pdf = PSREF_PDF_TEXT

    def fetch(url, timeout=12):
        if "15ABR8" in url:
            return PageFetch(url, "ok", 200, amd_pdf, "Manufacturer PDF text retrieved")
        if "IdeaPad_Slim_3" in url and url.casefold().endswith(".pdf"):
            return PageFetch(url, "ok", 200, intel_pdf, "Manufacturer PDF text retrieved")
        return PageFetch(url, "http_error", 404, "", "HTTP 404")

    candidate = ProductCandidate(
        name="Lenovo IdeaPad Slim 3 Laptop Ryzen 7 5825U / 16GB / 512GB NEW",
        model="Lenovo IdeaPad Slim 3",
        configuration="16GB RAM / 512GB SSD",
        product_url="https://www.ebay.com/itm/ideapad-ryzen",
        source="ebay",
    )
    research_candidates([candidate], category="laptop", live=True, fetch=fetch)
    assert "5825" in (candidate.specifications["cpu"].value or "").casefold()
    assert "15ABR8" in (candidate.specifications["cpu"].source_url or "")
