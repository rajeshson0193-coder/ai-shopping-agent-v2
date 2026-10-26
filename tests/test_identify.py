from shopping_agent.identify import identify_candidates
from shopping_agent.models import ProductCandidate, QualityStatus
from shopping_agent.profiles.laptops import extract_identity


def test_extracts_model_and_configuration():
    brand, model, configuration = extract_identity(
        "Lenovo IdeaPad Slim 3 15.6 Laptop, Intel Core i5, 16GB RAM, 512GB SSD"
    )
    assert brand == "Lenovo"
    assert model == "Lenovo IdeaPad Slim 3"
    assert configuration == "16GB RAM / 512GB SSD"


def test_extracts_chassis_and_sku_into_identity():
    cases = [
        (
            'Dell Inspiron 14 7425 2-in-1 Ryzen 7 5825U  16GB 512GB SSD Windows 11 Home',
            "Dell",
            "Dell Inspiron 14 7425",
            "16GB RAM / 512GB SSD",
        ),
        (
            'Dell Inspiron 15 3535 15.6" FHD Touch Ryzen 7 7730U 16GB 512GB SSD W11H Laptop',
            "Dell",
            "Dell Inspiron 15 3535",
            "16GB RAM / 512GB SSD",
        ),
        (
            "HP Pavilion 15 Notebook - 15\" 15-p227NR - AMD A10-5745M - 8GB 1TB HD Win 10",
            "HP",
            "HP Pavilion 15 15-P227NR",
            "8GB RAM / 1TB HDD",
        ),
        (
            "Lenovo IdeaPad Slim 3 15AMN8 15.6 Laptop AMD Ryzen 5 8GB 256GB SSD",
            "Lenovo",
            "Lenovo IdeaPad Slim 3 15AMN8",
            "8GB RAM / 256GB SSD",
        ),
    ]
    for title, brand, model, configuration in cases:
        found_brand, found_model, found_config = extract_identity(title)
        assert found_brand == brand, title
        assert found_model == model, title
        assert found_config == configuration, title


def test_extracts_live_business_laptop_titles():
    cases = [
        (
            "HP PROBOOK 640 G5 14\" Windows 11 PRO Laptop i5 8th Gen 8GB RAM 256GB SSD NICE!",
            "HP",
            "HP ProBook 640 G5",
            "8GB RAM / 256GB SSD",
        ),
        (
            "Dell Latitude 3410 14\" Intel Core i3-10110U 8GB DDR4 128GB SSD Windows 11",
            "Dell",
            "Dell Latitude 3410",
            "8GB RAM / 128GB SSD",
        ),
        (
            "HP EliteBook 840 G8 i5-1145G7 16GB RAM 256GB SSD Windows 11 Pro",
            "HP",
            "HP EliteBook 840 G8",
            "16GB RAM / 256GB SSD",
        ),
        (
            "Lenovo ThinkPad X260 12.5\" HD 2.3GHz i5 8GB RAM 256GB SSD Windows 11 Pro",
            "Lenovo",
            "Lenovo ThinkPad X260",
            "8GB RAM / 256GB SSD",
        ),
        (
            "HP OmniBook 5 Laptop Computer 16\" 2K AMD Ryzen 7 16 GB memory;512 GB SSD",
            "HP",
            "HP OmniBook 5",
            "16GB RAM / 512GB SSD",
        ),
        (
            "HP OmniBook 3 16\" AI Laptop | AMD Ryzen 5 processor | 16GB RAM | 1TB SSD",
            "HP",
            "HP OmniBook 3",
            "16GB RAM / 1TB SSD",
        ),
        (
            "Acer Nitro V – 16\" WUXGA 165Hz Gaming Laptop Intel Core 7 240H 2024",
            "Acer",
            "Acer Nitro V",
            None,
        ),
    ]
    for title, brand, model, configuration in cases:
        found_brand, found_model, found_config = extract_identity(title)
        assert found_brand == brand, title
        assert found_model == model, title
        assert found_config == configuration, title


def test_extracts_plus_style_ram_storage():
    brand, model, configuration = extract_identity(
        "15.6\" Laptop PC 12+256GB,Windows 11 Pro,Intel Celeron N4000"
    )
    assert brand is None
    assert model is None
    assert configuration == "12GB RAM / 256GB STORAGE"


def test_rejects_accessories():
    candidates = identify_candidates(
        [
            ProductCandidate(
                name="Laptop sleeve 15.6 inch padded bag",
                product_url="https://www.ebay.com/itm/fixture-laptop-sleeve",
                source="ebay",
            )
        ],
        category="laptop",
    )
    assert candidates[0].quality_status == QualityStatus.REJECTED
    assert "likely_accessory_not_laptop" in candidates[0].quality_reasons


def test_rejects_macbook_neo_and_google_search_urls():
    candidates = identify_candidates(
        [
            ProductCandidate(
                name='Apple Macbook Neo 13"ips 256 512gb Apple A18 Pro 1.23kg By Fedex',
                product_url="https://www.google.com/search?q=macbook+neo",
                source="serpapi",
            ),
            ProductCandidate(
                name="HP PROBOOK 640 G5 Laptop 8GB RAM 256GB SSD",
                product_url="https://www.ebay.com/itm/live-probook-640-g5",
                source="ebay",
            ),
        ],
        category="laptop",
    )
    assert candidates[0].quality_status == QualityStatus.REJECTED
    assert candidates[1].quality_status == QualityStatus.ELIGIBLE
    assert candidates[1].model == "HP ProBook 640 G5"
