from shopping_agent.spec_extract import extract_laptop_specs, page_mentions_model


SAMPLE = (
    "Lenovo IdeaPad Slim 3 laptop. Processor: Intel Core i5-1335U. "
    "Memory: 16 GB RAM. Storage: 512 GB SSD. "
    "Display: 15.6-inch FHD (1920 x 1080). Graphics: Intel Iris Xe. "
    "Battery life up to 12 hours."
)


def test_extracts_explicit_laptop_specs():
    found = extract_laptop_specs(SAMPLE)
    assert found["cpu"][0] == "Intel Core i5-1335U"
    assert found["ram_gb"][0] == "16"
    assert found["storage"][0] == "512GB SSD"
    assert found["display"][0].startswith("15.6-inch")
    assert "Iris Xe" in found["gpu"][0]
    assert found["battery"][0] == "12 hours"
    assert page_mentions_model(SAMPLE, "Lenovo IdeaPad Slim 3")


def test_hours_without_battery_word_stay_unknown():
    found = extract_laptop_specs("Lenovo IdeaPad Slim 3. Charge time 2 hours.")
    assert found["battery"][0] is None


def test_prefers_listing_compatible_cpu_and_ram_from_manual():
    text = (
        "Specifications of Inspiron 15 3530. "
        "Processor type Intel Core i3-1305U Intel Core i5-1334U Intel Core i7-1355U. "
        "Memory 8 GB 16 GB DDR4. Storage 512 GB SSD 1 TB SSD."
    )
    found = extract_laptop_specs(
        text,
        prefer_cpu_tokens=("i5-1334u",),
        prefer_ram_gb=16,
        prefer_storage_gb=512,
    )
    assert "i5-1334u" in found["cpu"][0].casefold()
    assert found["ram_gb"][0] == "16"
    assert found["storage"][0] == "512GB SSD"


def test_does_not_join_ssd_capacity_to_emmc_token():
    text = (
        "Dell Inspiron 15 3530. Storage type Interface type Capacity "
        "M.2 2280, Solid-state drive PCIe NVMe Gen4 x4 Up to 2 TB M.2 eMMC "
        "PCIe 128 GB 2.5-inch hard-disk drive SATA 1 TB"
    )
    found = extract_laptop_specs(text)
    assert found["storage"][0] == "2TB SSD"


def test_extracts_psref_style_memory_and_battery():
    text = (
        "IdeaPad Slim 3 15IRH10. Processor Family Core i5 / i7 Processor. "
        "Processor Name Core i5-13420H. "
        "Memory Max Memory Up to 16GB DDR5-5600 offering. "
        "Storage M.2 2242 SSD up to 1TB. Display 15.6\" FHD (1920x1080). "
        "Graphics Intel® UHD Graphics. "
        "supports Rapid Charge Boost (get 2 hours of runtime with a 15-minute charge). "
        "Max Battery Life Local video playback: 12 hr."
    )
    found = extract_laptop_specs(text)
    assert found["cpu"][0] == "Core i5-13420H"
    assert found["ram_gb"][0] == "16"
    assert found["storage"][0] == "1TB SSD"
    assert found["display"][0].startswith("15.6-inch")
    assert "UHD" in (found["gpu"][0] or "").upper()
    assert found["battery"][0] == "12 hours"
