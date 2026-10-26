from shopping_agent.profiles.headphones import page_hints_for_model as headphone_hints
from shopping_agent.profiles.laptops import page_hints_for_model
from shopping_agent.spec_extract import page_mentions_model


def test_soundcore_p30i_hints_use_current_product_slug():
    hints = headphone_hints("Soundcore P30i")
    assert hints
    assert "soundcore-p30i" in hints[0]
    assert not any(url.rstrip("/").endswith("/p30i") for url in hints)
    assert not any("a3957" in url for url in hints)


def test_dynamic_dell_latitude_hints():
    hints = page_hints_for_model("Dell Latitude 3500")
    assert any("latitude-3500-laptop" in url for url in hints)
    assert all(url.startswith("https://") for url in hints)


def test_dynamic_hp_probook_hints():
    hints = page_hints_for_model("HP ProBook 640 G5")
    assert any("probook-640-g5" in url for url in hints)


def test_ideapad_slim_3_prefers_psref_pdf_before_storefront():
    hints = page_hints_for_model("Lenovo IdeaPad Slim 3")
    assert hints
    assert hints[0].casefold().endswith(".pdf")
    assert "psref.lenovo.com" in hints[0]


def test_ideapad_ryzen_listing_prefers_amd_psref():
    hints = page_hints_for_model(
        "Lenovo IdeaPad Slim 3",
        "Lenovo IdeaPad Slim 3 Laptop Ryzen 7 5825U / 16GB / 512GB",
    )
    assert hints
    assert any("15ABR8" in url or "15ABA7" in url or "15AMN8" in url for url in hints[:3])


def test_inspiron_15_includes_dell_manual_pdf():
    hints = page_hints_for_model("Dell Inspiron 15")
    assert any(url.casefold().endswith(".pdf") or "manual" in url.casefold() for url in hints)


def test_inspiron_chassis_hints_are_sku_specific():
    hints = page_hints_for_model("Dell Inspiron 15 3535")
    assert hints
    assert all("3535" in url for url in hints)
    assert not any("3530" in url for url in hints)


def test_page_mentions_model_without_brand_prefix():
    text = "Support for Latitude 3500 laptop. Processor Intel Core i5."
    assert page_mentions_model(text, "Dell Latitude 3500")


def test_page_mentions_model_in_psref_style_title():
    text = "IdeaPad Slim 3 15IRH10 Product Specifications Reference"
    assert page_mentions_model(text, "Lenovo IdeaPad Slim 3")


def test_page_mentions_model_rejects_wrong_inspiron_chassis():
    text = "Inspiron 15 3530 Owner's Manual. Processor Intel Core i3-1305U."
    assert page_mentions_model(text, "Dell Inspiron 15")
    assert not page_mentions_model(text, "Dell Inspiron 15 3535")
    assert page_mentions_model(
        "Inspiron 15 3535 Owner's Manual. AMD Ryzen 7 7730U.",
        "Dell Inspiron 15 3535",
    )
