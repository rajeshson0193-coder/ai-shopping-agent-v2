"""Laptop category profile: identity patterns, spec schema, and scoring hints."""

from __future__ import annotations

import re
from pathlib import Path

from shopping_agent.models import (
    EvidenceStrength,
    ProductCandidate,
    VerificationStatus,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

# Descriptive category focus areas only — not scoring weights. Ranking uses the
# fixed evidence heuristic in score_candidate (RAM/storage/CPU/display/GPU/condition).
LAPTOP_PRIORITIES = [
    "performance",
    "memory and storage",
    "display",
    "battery",
    "value",
]

SPEC_FIELDS = ("cpu", "ram_gb", "storage", "display", "gpu", "battery")

# Allow-listed manufacturer pages / datasheets. Order matters: prefer PDF/support
# sources that tolerate automated GET, then shop HTML as a last resort.
# A hint is a place to look, not evidence by itself.
# SKU/chassis keys beat family keys — never reuse a wrong-chassis datasheet.
_IDEAPAD_SLIM_3_AMD_PDFS = (
    "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15ABR8/IdeaPad_Slim_3_15ABR8_Spec.pdf",
    "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_3_15ABA7/IdeaPad_3_15ABA7_Spec.pdf",
    "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15AMN8/IdeaPad_Slim_3_15AMN8_Spec.pdf",
)
_IDEAPAD_SLIM_3_INTEL_PDFS = (
    "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15IRH10/IdeaPad_Slim_3_15IRH10_Spec.pdf",
    "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15IWC11/IdeaPad_Slim_3_15IWC11_Spec.PDF",
)

MODEL_PAGE_HINTS: dict[str, tuple[str, ...]] = {
    "lenovo ideapad slim 3": (
        *_IDEAPAD_SLIM_3_AMD_PDFS,
        *_IDEAPAD_SLIM_3_INTEL_PDFS,
        "https://www.lenovo.com/us/en/p/laptops/ideapad/ideapad-slim-3",
    ),
    "lenovo ideapad slim 3 15abr8": (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15ABR8/IdeaPad_Slim_3_15ABR8_Spec.pdf",
        "https://www.lenovo.com/us/en/p/laptops/ideapad/ideapad-slim-3",
    ),
    "lenovo ideapad slim 3 15amn8": (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15AMN8/IdeaPad_Slim_3_15AMN8_Spec.pdf",
        "https://www.lenovo.com/us/en/p/laptops/ideapad/ideapad-slim-3",
    ),
    "lenovo ideapad slim 3 15irh10": (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15IRH10/IdeaPad_Slim_3_15IRH10_Spec.pdf",
        "https://www.lenovo.com/us/en/p/laptops/ideapad/ideapad-slim-3",
    ),
    "lenovo ideapad slim 3 15iwc11": (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15IWC11/IdeaPad_Slim_3_15IWC11_Spec.PDF",
        "https://www.lenovo.com/us/en/p/laptops/ideapad/ideapad-slim-3",
    ),
    "lenovo ideapad 1": (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_1_15IGL7/IdeaPad_1_15IGL7_Spec.PDF",
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_1_15IAU7/IdeaPad_1_15IAU7_Spec.pdf",
        "https://www.lenovo.com/us/en/p/laptops/ideapad/ideapad-1",
    ),
    "lenovo thinkpad e14": (
        "https://psref.lenovo.com/syspool/Sys/PDF/ThinkPad/ThinkPad_E14_Gen_5_Intel/ThinkPad_E14_Gen_5_Intel_Spec.pdf",
        "https://www.lenovo.com/us/en/p/laptops/thinkpad/thinkpad-e-series/thinkpad-e14",
    ),
    # Family Pavilion hint is modern-only; SKU-specific models must not reuse it.
    "hp pavilion 15": (
        "https://pcb.inc.hp.com/dc/api/spec-sheet/ww-en/2100700561/pdf/3V2M6EA.pdf",
        "https://www.hp.com/us-en/shop/mdp/laptops-tablets/pavilion-laptops",
    ),
    "hp 15-fd": (
        "https://www.hp.com/us-en/shop/mdp/laptops/hp-laptop-15",
        "https://support.hp.com/us-en/product/details/hp-laptop-15-fd0000-series",
    ),
    "hp 15": (
        "https://www.hp.com/us-en/shop/mdp/laptops/hp-laptop-15",
        "https://support.hp.com/us-en/product/details/hp-laptop-15",
    ),
    "hp omnibook 5": (
        "https://www.hp.com/us-en/shop/mdp/laptops/omnibook-laptops",
        "https://support.hp.com/us-en/product/details/hp-omnibook-5",
    ),
    "hp omnibook 3": (
        "https://www.hp.com/us-en/shop/mdp/laptops/omnibook-laptops",
        "https://support.hp.com/us-en/product/details/hp-omnibook-3",
    ),
    # Chassis-specific Inspiron keys only — family keys must not point at a single chassis.
    "dell inspiron 15 3530": (
        "https://dl.dell.com/content/manual77626568-inspiron-15-3530-with-usb-type-c-owner-s-manual.pdf?language=en-us",
        "https://www.dell.com/en-us/shop/dell-laptops/inspiron-15-laptop/spd/inspiron-15-3530-laptop",
    ),
    "dell inspiron 15": (
        "https://dl.dell.com/content/manual77626568-inspiron-15-3530-with-usb-type-c-owner-s-manual.pdf?language=en-us",
        "https://www.dell.com/en-us/shop/dell-laptops/inspiron-15-laptop/spd/inspiron-15-3530-laptop",
    ),
    "dell inspiron 14 5440": (
        "https://www.dell.com/support/manuals/en-us/inspiron-14-5440-laptop/inspiron-14-5440-owners-manual/specifications-of-inspiron-14-5440",
        "https://www.dell.com/en-us/shop/dell-laptops/inspiron-14-laptop/spd/inspiron-14-5440-laptop",
    ),
    "dell inspiron 14": (
        "https://www.dell.com/support/manuals/en-us/inspiron-14-5440-laptop/inspiron-14-5440-owners-manual/specifications-of-inspiron-14-5440",
        "https://www.dell.com/en-us/shop/dell-laptops/inspiron-14-laptop/spd/inspiron-14-5440-laptop",
    ),
    "acer aspire 5": (
        "https://www.acer.com/us-en/laptops/aspire/aspire-5",
        "https://www.acer.com/us-en/support",
    ),
    "acer aspire 3": (
        "https://www.acer.com/us-en/laptops/aspire/aspire-3",
    ),
    "acer nitro v": (
        "https://www.acer.com/us-en/laptops/nitro/nitro-v",
    ),
    "asus vivobook 15": (
        "https://www.asus.com/us/laptops/for-home/vivobook/asus-vivobook-15-x1504/techspec/",
        "https://www.asus.com/us/laptops/for-home/vivobook/asus-vivobook-15-x1504/",
    ),
    "asus tuf gaming a15": (
        "https://www.asus.com/us/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-a15/techspec/",
        "https://www.asus.com/us/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-a15/",
    ),
    "samsung galaxy book4": (
        "https://www.samsung.com/us/computers/galaxy-book/galaxy-book4-series/",
        "https://www.samsung.com/us/support/model/",
    ),
    "apple macbook air 13": (
        "https://www.apple.com/macbook-air-13-and-15-m3/specs/",
        "https://www.apple.com/macbook-air/",
    ),
}

MANUFACTURER_DOMAINS: dict[str, tuple[str, ...]] = {
    "lenovo": ("lenovo.com",),
    "hp": ("hp.com",),
    "dell": ("dell.com",),
    "acer": ("acer.com",),
    "asus": ("asus.com",),
    "samsung": ("samsung.com",),
    "apple": ("apple.com",),
}

KNOWN_RETAILER_DOMAINS = {
    "amazon.com",
    "bestbuy.com",
    "bhphotovideo.com",
    "costco.com",
    "dell.com",
    "ebay.com",
    "hp.com",
    "lenovo.com",
    "acer.com",
    "asus.com",
    "samsung.com",
    "apple.com",
    "newegg.com",
    "target.com",
    "walmart.com",
    "adorama.com",
    "microcenter.com",
}

LAPTOP_TERMS = (
    "laptop",
    "notebook",
    "ultrabook",
    "chromebook",
    "macbook",
    "thinkpad",
    "ideapad",
    "inspiron",
    "pavilion",
    "vivobook",
    "zenbook",
    "aspire",
    "galaxy book",
    "probook",
    "elitebook",
    "latitude",
    "omnibook",
    "precision",
    "nitro",
)

ACCESSORY_TERMS = (
    "laptop bag",
    "laptop sleeve",
    "laptop stand",
    "charger only",
    "power adapter",
    "docking station",
    "replacement battery",
    "keyboard cover",
    "screen protector",
)

_REJECT_MODEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bmacbook\s+neo\b", re.I),
    re.compile(r"\bapple\s+a18\s+pro\b", re.I),
)

_MODEL_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\blenovo\s+ideapad\s+(?:slim\s+)?3i?\b", re.I), "Lenovo", "Lenovo IdeaPad Slim 3"),
    (re.compile(r"\blenovo\s+ideapad\s+1\b", re.I), "Lenovo", "Lenovo IdeaPad 1"),
    (re.compile(r"\blenovo\s+thinkpad\s+(e14)\b", re.I), "Lenovo", "Lenovo ThinkPad E14"),
    (re.compile(r"\blenovo\s+thinkpad\s+(x\d{3})\b", re.I), "Lenovo", "Lenovo ThinkPad {0}"),
    (re.compile(r"\blenovo\s+thinkpad\s+(t\d{3})\b", re.I), "Lenovo", "Lenovo ThinkPad {0}"),
    (re.compile(r"\blenovo\s+thinkpad\s+(l\d{2,3})\b", re.I), "Lenovo", "Lenovo ThinkPad {0}"),
    (re.compile(r"\bhp\s+probook\s+(\d{3})\s*g(\d)\b", re.I), "HP", "HP ProBook {0} G{1}"),
    (re.compile(r"\bhp\s+elitebook\s+(\d{3})\s*g(\d)\b", re.I), "HP", "HP EliteBook {0} G{1}"),
    (re.compile(r"\bhp\s+omnibook\s+(\d)\b", re.I), "HP", "HP OmniBook {0}"),
    (re.compile(r"\bhp\s+pavilion\s+15\b", re.I), "HP", "HP Pavilion 15"),
    (re.compile(r"\bhp\s+15[- ]fd\w+\b", re.I), "HP", "HP 15-fd"),
    (re.compile(r"\bhp\s+15\b", re.I), "HP", "HP 15"),
    (re.compile(r"\bdell\s+latitude\s+(\d{4})\b", re.I), "Dell", "Dell Latitude {0}"),
    # Chassis before bare family so "Inspiron 15 3535" keeps 3535.
    (re.compile(r"\bdell\s+inspiron\s+(14|15)\s+(\d{4})\b", re.I), "Dell", "Dell Inspiron {0} {1}"),
    (re.compile(r"\bdell\s+inspiron\s+15\b", re.I), "Dell", "Dell Inspiron 15"),
    (re.compile(r"\bdell\s+inspiron\s+14\b", re.I), "Dell", "Dell Inspiron 14"),
    (re.compile(r"\bacer\s+nitro\s+v\b", re.I), "Acer", "Acer Nitro V"),
    (re.compile(r"\bacer\s+aspire\s+5\b", re.I), "Acer", "Acer Aspire 5"),
    (re.compile(r"\bacer\s+aspire\s+3\b", re.I), "Acer", "Acer Aspire 3"),
    (re.compile(r"\basus\s+vivobook\s+15\b", re.I), "ASUS", "ASUS VivoBook 15"),
    (re.compile(r"\basus\s+tuf\s+gaming\s+a15\b", re.I), "ASUS", "ASUS TUF Gaming A15"),
    (re.compile(r"\bsamsung\s+galaxy\s+book4\b", re.I), "Samsung", "Samsung Galaxy Book4"),
    (re.compile(r"\bapple\s+macbook\s+air\s+13\b", re.I), "Apple", "Apple MacBook Air 13"),
    (re.compile(r"\bmacbook\s+air\s+13\b", re.I), "Apple", "Apple MacBook Air 13"),
)

# Lenovo machine type (15ABR8 / 15IRH10) and HP product number (15-p227NR).
_LENOVO_MT_RE = re.compile(r"\b(15[A-Z]{2,4}\d{1,2})\b", re.I)
_HP_PRODUCT_RE = re.compile(r"\b(\d{2}-[a-z]\d{3,4}[a-z]{0,2})\b", re.I)
_INSPIRON_CHASSIS_RE = re.compile(r"^dell inspiron (14|15) (\d{4})$", re.I)
_RAM_RE = re.compile(r"\b(\d+)\s*GB\s*(?:RAM|ddr\d|memory)\b", re.I)
_RAM_PLUS_STORAGE_RE = re.compile(
    r"\b(\d+)\s*(?:GB\s*)?\+\s*(\d+)\s*(GB|TB)\b",
    re.I,
)
_RAM_SLASH_STORAGE_RE = re.compile(
    r"\b(\d{1,3})\s*GB(?:\s*(?:RAM|ddr\d|memory))?\s*[\/\|]\s*(\d+)\s*(GB|TB)\b",
    re.I,
)
# "16GB 512GB SSD" without an explicit RAM keyword (common on Dell titles).
_BARE_RAM_STORAGE_RE = re.compile(
    r"\b(\d{1,2})\s*GB\s+(\d+)\s*(GB|TB)\s*(SSD|HDD|eMMC|storage|HD)\b",
    re.I,
)
_STORAGE_RE = re.compile(r"\b(\d+)\s*(GB|TB)\s*(SSD|HDD|eMMC|storage|HD)\b", re.I)

_LATITUDE_RE = re.compile(r"^dell latitude (\d{4})$", re.I)
_HP_BUSINESS_RE = re.compile(r"^hp (probook|elitebook) (\d{3}) g(\d)$", re.I)
_THINKPAD_RE = re.compile(r"^lenovo thinkpad ([xtl]\d{2,3}|e14)$", re.I)


def matches_laptop_category(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in LAPTOP_TERMS)


def looks_like_rejected_fake(title: str) -> bool:
    return any(pattern.search(title) for pattern in _REJECT_MODEL_PATTERNS)


def discovery_search_query(category: str) -> str:
    if category.casefold() == "laptop":
        return "laptop notebook computer"
    return category


def discovery_queries(category: str) -> list[str]:
    """Targeted queries that surface identifiable consumer laptop models."""
    if category.casefold() != "laptop":
        return [category]
    return [
        "Lenovo IdeaPad laptop",
        "Dell Inspiron laptop",
        "HP Pavilion laptop",
        "Acer Aspire 5 laptop",
        "ASUS VivoBook 15 laptop",
        "Samsung Galaxy Book4 laptop",
        "HP OmniBook laptop",
        "Acer Nitro V laptop",
        "Dell Latitude laptop",
        "Lenovo ThinkPad laptop",
    ]


def _inspiron_chassis_hints(size: str, chassis: str) -> tuple[str, ...]:
    """Best-effort chassis-specific Dell URLs (many HTML pages 403; PDFs preferred)."""
    base = f"inspiron-{size}-{chassis}"
    return (
        f"https://dl.dell.com/topicspdf/{base}-laptop_owners-manual_en-us.pdf",
        f"https://dl.dell.com/topicspdf/{base}-laptop_setup-and-specifications_en-us.pdf",
        f"https://dl.dell.com/topicspdf/{base}-2-in-1-laptop_setup-and-specifications_en-us.pdf",
        f"https://dl.dell.com/manuals/all-products/esuprt_laptop/esuprt_inspiron_laptop/{base}-laptop_owners-manual_en-us.pdf",
        f"https://dl.dell.com/manuals/all-products/esuprt_laptop/esuprt_inspiron_laptop/{base}-2-in-1-laptop_setup-and-specifications_en-us.pdf",
        f"https://www.dell.com/en-us/shop/dell-laptops/inspiron-{size}-laptop/spd/{base}-laptop",
    )


def _hp_product_hints(product: str) -> tuple[str, ...]:
    slug = product.casefold()
    return (
        f"https://support.hp.com/us-en/product/details/{slug}",
        f"https://support.hp.com/us-en/product/{slug}",
        "https://www.hp.com/us-en/shop/mdp/laptops-tablets/pavilion-laptops",
    )


def _prefer_cpu_platform(hints: tuple[str, ...], listing_text: str) -> tuple[str, ...]:
    """Reorder IdeaPad PDFs so AMD sheets are tried first for Ryzen listings."""
    if not listing_text or not hints:
        return hints
    lowered = listing_text.casefold()
    wants_amd = "ryzen" in lowered or re.search(r"\bamd\b", lowered) is not None
    wants_intel = bool(re.search(r"\b(?:intel|core\s*i[3579]|core\s+ultra)\b", lowered))
    if wants_amd == wants_intel:
        return hints

    def _is_amd_hint(url: str) -> bool:
        u = url.casefold()
        return any(token in u for token in ("15abr", "15aba", "15amn", "15alc", "15aml"))

    def _is_intel_hint(url: str) -> bool:
        u = url.casefold()
        return any(token in u for token in ("15irh", "15iwc", "15iau", "15igl"))

    amd = [url for url in hints if _is_amd_hint(url)]
    intel = [url for url in hints if _is_intel_hint(url)]
    other = [url for url in hints if url not in amd and url not in intel]
    if wants_amd:
        return tuple(amd + intel + other)
    return tuple(intel + amd + other)


def page_hints_for_model(model: str, listing_text: str = "") -> tuple[str, ...]:
    """Return allow-listed manufacturer URLs for a recognized model / SKU."""
    if not model or not model.strip():
        return ()
    key = model.casefold().strip()

    static = MODEL_PAGE_HINTS.get(key)
    if static:
        return _prefer_cpu_platform(static, listing_text)

    inspiron = _INSPIRON_CHASSIS_RE.match(key)
    if inspiron:
        return _inspiron_chassis_hints(inspiron.group(1), inspiron.group(2))

    hp_sku = re.match(r"^hp pavilion 15 (\d{2}-[a-z]\d{3,4}[a-z]{0,2})$", key, re.I)
    if hp_sku:
        return _hp_product_hints(hp_sku.group(1))

    latitude = _LATITUDE_RE.match(key)
    if latitude:
        num = latitude.group(1)
        return (
            f"https://www.dell.com/support/manuals/en-us/latitude-{num}-laptop",
            f"https://dl.dell.com/topicspdf/latitude-{num}-laptop_owners-manual_en-us.pdf",
            f"https://www.dell.com/support/home/en-us/product-support/product/latitude-{num}-laptop",
            f"https://www.dell.com/support/home/en-us/product-support/product/latitude-14-{num}-laptop",
            f"https://www.dell.com/support/home/en-us/product-support/product/latitude-15-{num}-laptop",
        )

    business = _HP_BUSINESS_RE.match(key)
    if business:
        series, num, gen = business.groups()
        return (
            f"https://support.hp.com/us-en/product/details/hp-{series}-{num}-g{gen}-notebook-pc",
            f"https://support.hp.com/us-en/product/hp-{series}-{num}-g{gen}-notebook-pc/model/{series}{num}g{gen}",
            f"https://support.hp.com/us-en/document/c{num}{gen}",
        )

    thinkpad = _THINKPAD_RE.match(key)
    if thinkpad:
        series = thinkpad.group(1).upper()
        family = series[0].lower()
        slug = series.lower()
        return (
            f"https://psref.lenovo.com/syspool/Sys/PDF/ThinkPad/ThinkPad_{series}/ThinkPad_{series}_Spec.pdf",
            f"https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-{family}-series-laptops/thinkpad-{slug}",
        )

    # SKU-bearing identities must not silently fall back to a wrong family datasheet.
    if identity_sku_tokens(model):
        return ()

    return ()


def identity_sku_tokens(model: str) -> tuple[str, ...]:
    """Chassis / machine-type / product tokens that a manufacturer page must mention."""
    if not model:
        return ()
    key = model.casefold().strip()
    tokens: list[str] = []
    inspiron = _INSPIRON_CHASSIS_RE.match(key)
    if inspiron:
        tokens.append(inspiron.group(2))
    mt = _LENOVO_MT_RE.search(model)
    if mt and "ideapad" in key:
        tokens.append(mt.group(1).casefold())
    hp = re.search(r"\b(\d{2}-[a-z]\d{3,4}[a-z]{0,2})\b", key, re.I)
    if hp and "pavilion" in key:
        tokens.append(hp.group(1).casefold())
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return tuple(ordered)


def fixture_family_model(model: str) -> str:
    """Map SKU-enriched identity back to a family fixture key when needed."""
    if not model:
        return model
    # Strip trailing Lenovo MT / HP product / Dell chassis.
    stripped = re.sub(r"\s+15[A-Z]{2,4}\d{1,2}$", "", model, flags=re.I)
    stripped = re.sub(r"\s+\d{2}-[a-z]\d{3,4}[a-z]{0,2}$", "", stripped, flags=re.I)
    stripped = re.sub(r"\s+\d{4}$", "", stripped)
    return stripped.strip() or model


def extract_identity(title: str) -> tuple[str | None, str | None, str | None]:
    """Return (brand, model, configuration) without guessing unknown models."""
    if not isinstance(title, str) or not title.strip():
        return None, None, None
    if looks_like_rejected_fake(title):
        return None, None, None

    brand = None
    model = None
    for pattern, found_brand, template in _MODEL_PATTERNS:
        match = pattern.search(title)
        if not match:
            continue
        brand = found_brand
        groups = match.groups()
        if groups:
            normalized = []
            for group in groups:
                if group is None:
                    continue
                if re.fullmatch(r"[xXtTlL]\d+", group):
                    normalized.append(group.upper())
                else:
                    normalized.append(group)
            try:
                model = template.format(*normalized)
            except (IndexError, ValueError):
                model = template
        else:
            model = template
        break

    if model:
        # Enrich family identity with SKU / machine type when the title states it.
        if model.casefold() == "lenovo ideapad slim 3":
            mt = _LENOVO_MT_RE.search(title)
            if mt:
                model = f"{model} {mt.group(1).upper()}"
        elif model.casefold() == "hp pavilion 15":
            product = _HP_PRODUCT_RE.search(title)
            if product:
                model = f"{model} {product.group(1).upper()}"

    ram = None
    storage = None
    plus_match = _RAM_PLUS_STORAGE_RE.search(title)
    slash_match = _RAM_SLASH_STORAGE_RE.search(title)
    bare_match = _BARE_RAM_STORAGE_RE.search(title)
    if plus_match:
        ram = f"{plus_match.group(1)}GB RAM"
        storage = f"{plus_match.group(2)}{plus_match.group(3).upper()} STORAGE"
    elif slash_match:
        ram = f"{slash_match.group(1)}GB RAM"
        storage = f"{slash_match.group(2)}{slash_match.group(3).upper()} SSD"
    elif bare_match:
        ram = f"{bare_match.group(1)}GB RAM"
        kind = bare_match.group(4).upper()
        if kind == "HD":
            kind = "HDD"
        storage = f"{bare_match.group(2)}{bare_match.group(3).upper()} {kind}"
    else:
        ram_match = _RAM_RE.search(title)
        if ram_match:
            ram = f"{ram_match.group(1)}GB RAM"
        storage_match = _STORAGE_RE.search(title)
        if storage_match:
            kind = storage_match.group(3).upper()
            if kind == "HD":
                kind = "HDD"
            storage = (
                f"{storage_match.group(1)}{storage_match.group(2).upper()} {kind}"
            )

    configuration = None
    if ram and storage:
        configuration = f"{ram} / {storage}"
    elif ram:
        configuration = ram
    elif storage:
        configuration = storage

    return brand, model, configuration


def _extract_specs(text: str, candidate: ProductCandidate):
    from shopping_agent.consistency import extract_listing_claims
    from shopping_agent.spec_extract import extract_laptop_specs

    claims = extract_listing_claims(candidate)
    return extract_laptop_specs(
        text,
        prefer_cpu_tokens=claims.cpu_tokens,
        prefer_ram_gb=claims.ram_gb,
        prefer_storage_gb=claims.storage_gb,
        model=candidate.model,
    )


def _score_page_fit(extracted, candidate: ProductCandidate) -> int:
    from shopping_agent.consistency import cpu_compatible, extract_listing_claims

    claims = extract_listing_claims(candidate)
    score = 0
    cpu_value = extracted.get("cpu", (None, None, None))[0]
    if claims.cpu_tokens and cpu_value and cpu_compatible(claims.cpu_tokens, cpu_value):
        score += 8
    elif claims.cpu_tokens and cpu_value:
        score -= 4

    ram_value = extracted.get("ram_gb", (None, None, None))[0]
    if claims.ram_gb is not None and ram_value is not None:
        try:
            if int(str(ram_value).split()[0]) == claims.ram_gb:
                score += 4
            else:
                score -= 2
        except ValueError:
            pass

    storage_value = extracted.get("storage", (None, None, None))[0]
    if claims.storage_gb is not None and storage_value is not None:
        match = re.search(r"(\d+)\s*(GB|TB)", str(storage_value), re.I)
        if match:
            amount = int(match.group(1))
            gb = amount * 1024 if match.group(2).upper() == "TB" else amount
            if gb == claims.storage_gb:
                score += 4
            else:
                score -= 2

    score += sum(1 for value, _, _ in extracted.values() if value)
    return score


def _strong_spec(candidate: ProductCandidate, field_name: str):
    record = candidate.specifications.get(field_name)
    if record is None:
        return None
    if (
        record.status == VerificationStatus.VERIFIED
        and record.evidence_strength == EvidenceStrength.STRONG
        and record.value not in (None, "")
    ):
        return record
    return None


def _listing_spec(candidate: ProductCandidate, field_name: str):
    record = candidate.specifications.get(field_name)
    if record is None:
        return None
    if (
        record.status == VerificationStatus.VERIFIED
        and record.evidence_strength == EvidenceStrength.WEAK
        and record.source_type in {"listing_title", "listing_configuration"}
        and record.value not in (None, "")
    ):
        return record
    return None


def _has_discrete_gpu(value: str) -> bool:
    lowered = value.casefold()
    return any(token in lowered for token in ("rtx", "geforce", "radeon", "discrete"))


def score_candidate(candidate: ProductCandidate) -> tuple[int, list[str], bool]:
    score = 0
    reasons: list[str] = []
    weak_positive = []
    scored_fields: set[str] = set()

    ram = _strong_spec(candidate, "ram_gb")
    if ram:
        try:
            ram_gb = int(str(ram.value).split()[0])
        except (TypeError, ValueError):
            ram_gb = 0
        if ram_gb >= 16:
            score += 15
            reasons.append("+15: manufacturer evidence verifies 16GB or more RAM")
            scored_fields.add("ram_gb")
        elif ram_gb >= 8:
            score += 8
            reasons.append("+8: manufacturer evidence verifies 8GB RAM")
            scored_fields.add("ram_gb")
    else:
        listing_ram = _listing_spec(candidate, "ram_gb")
        if listing_ram:
            try:
                ram_gb = int(str(listing_ram.value).split()[0])
            except (TypeError, ValueError):
                ram_gb = 0
            if ram_gb >= 16:
                score += 8
                reasons.append("+8: listing title states 16GB or more RAM (not manufacturer-verified)")
                scored_fields.add("ram_gb")
            elif ram_gb >= 8:
                score += 4
                reasons.append("+4: listing title states 8GB RAM (not manufacturer-verified)")
                scored_fields.add("ram_gb")
            elif ram_gb >= 4:
                score += 1
                reasons.append("+1: listing title states 4GB RAM (not manufacturer-verified)")
                scored_fields.add("ram_gb")

    storage = _strong_spec(candidate, "storage")
    if storage:
        value = str(storage.value).casefold()
        if "1tb" in value.replace(" ", "") or "1 tb" in value:
            score += 10
            reasons.append("+10: manufacturer evidence verifies 1TB-class storage")
            scored_fields.add("storage")
        elif "512" in value:
            score += 8
            reasons.append("+8: manufacturer evidence verifies 512GB-class storage")
            scored_fields.add("storage")
        elif "256" in value:
            score += 4
            reasons.append("+4: manufacturer evidence verifies 256GB-class storage")
            scored_fields.add("storage")
        elif "128" in value:
            score += 2
            reasons.append("+2: manufacturer evidence verifies 128GB-class storage")
            scored_fields.add("storage")
    else:
        listing_storage = _listing_spec(candidate, "storage")
        if listing_storage:
            value = str(listing_storage.value).casefold().replace(" ", "")
            if "1tb" in value:
                score += 5
                reasons.append("+5: listing title states 1TB-class storage (not manufacturer-verified)")
                scored_fields.add("storage")
            elif "512" in value:
                score += 4
                reasons.append("+4: listing title states 512GB-class storage (not manufacturer-verified)")
                scored_fields.add("storage")
            elif "256" in value:
                score += 2
                reasons.append("+2: listing title states 256GB-class storage (not manufacturer-verified)")
                scored_fields.add("storage")
            elif "128" in value:
                score += 1
                reasons.append("+1: listing title states 128GB-class storage (not manufacturer-verified)")
                scored_fields.add("storage")

    cpu = _strong_spec(candidate, "cpu")
    if cpu:
        score += 8
        reasons.append("+8: manufacturer evidence verifies CPU")
        scored_fields.add("cpu")
    else:
        listing_cpu = _listing_spec(candidate, "cpu")
        if listing_cpu:
            score += 3
            reasons.append("+3: listing title states CPU (not manufacturer-verified)")
            scored_fields.add("cpu")

    display = _strong_spec(candidate, "display")
    if display:
        score += 5
        reasons.append("+5: manufacturer evidence verifies display")
        scored_fields.add("display")

    gpu = _strong_spec(candidate, "gpu")
    if gpu and _has_discrete_gpu(str(gpu.value)):
        score += 10
        reasons.append("+10: manufacturer evidence verifies a discrete GPU")
        scored_fields.add("gpu")
    elif gpu:
        score += 2
        reasons.append("+2: manufacturer evidence verifies integrated graphics")
        scored_fields.add("gpu")

    if candidate.condition_status == VerificationStatus.VERIFIED and candidate.condition:
        condition = candidate.condition.casefold()
        if any(token in condition for token in ("refurbished", "used", "pre-owned", "renewed")):
            score -= 5
            reasons.append("-5: verified used/refurbished condition")
        elif condition in {"new", "brand new"}:
            score += 3
            reasons.append("+3: verified new condition")

    for field_name, record in candidate.specifications.items():
        if field_name in scored_fields:
            continue
        if (
            record.status == VerificationStatus.VERIFIED
            and record.evidence_strength == EvidenceStrength.WEAK
            and record.value not in (None, "")
        ):
            weak_positive.append(field_name)
    if weak_positive:
        reasons.append(
            "No points awarded for other weakly supported claims: " + ", ".join(sorted(weak_positive))
        )

    strong_count = sum(
        1
        for field_name in ("cpu", "ram_gb", "storage", "display", "gpu")
        if _strong_spec(candidate, field_name)
    )
    listing_count = sum(
        1
        for field_name in ("cpu", "ram_gb", "storage")
        if field_name in scored_fields and _listing_spec(candidate, field_name)
    )
    provisional = strong_count < 3 and (strong_count + listing_count) < 3
    if not reasons:
        reasons.append("No strongly supported scored feature claims; ranked by price tie-breakers")
    reasons.append("Battery life is recorded when found and is not scored")
    if candidate.delivered_total_status != VerificationStatus.VERIFIED:
        reasons.append("Delivered total (shipping + tax) is not verified and is not scored")
    return score, reasons, provisional


def _apply_consistency(candidate: ProductCandidate):
    from shopping_agent.consistency import apply_listing_consistency

    return apply_listing_consistency(candidate)


def _apply_fallback(candidate: ProductCandidate, claims=None):
    from shopping_agent.consistency import apply_listing_fallback

    return apply_listing_fallback(candidate, claims)


def _extra_limitations(live: bool) -> list[str]:
    del live
    return [
        "Scores are fixed evidence points for verified laptop specs (RAM/storage/CPU/display/GPU/condition), not personalized “best battery / best performance” ranking.",
        "Profile focus areas (performance, memory, display, battery, value) are descriptive only; they do not reweight scores.",
        "Battery life is recorded when found and is not scored.",
        "Manufacturer family datasheet claims only score when compatible with the listing's stated RAM/storage/CPU; conflicts stay non-scoring context.",
        "When manufacturer evidence conflicts or is missing, explicit listing title RAM/storage/CPU can score at a reduced weight (seller-stated, not manufacturer-verified).",
    ]


def _discovery_queries(request=None) -> list[str]:
    del request
    return discovery_queries("laptop")


def _discovery_search_query(request=None) -> str:
    del request
    return discovery_search_query("laptop")


_CLAIM_TERMS = {
    "cpu": re.compile(r"\b(?:intel|amd|ryzen|core|processor|cpu)\b", re.I),
    "ram_gb": re.compile(r"\b(?:\d+\s*GB|RAM|memory)\b", re.I),
    "storage": re.compile(r"\b(?:SSD|HDD|eMMC|TB|storage)\b", re.I),
    "display": re.compile(r"\b(?:inch|display|FHD|QHD|OLED|IPS|resolution|Hz)\b", re.I),
    "gpu": re.compile(r"\b(?:GPU|graphics|RTX|GeForce|Radeon|Intel Graphics|Iris|UHD)\b", re.I),
    "battery": re.compile(r"\b(?:hours?|battery)\b", re.I),
}


def build_profile():
    from shopping_agent.profiles.base import CategoryProfile

    return CategoryProfile(
        id="laptop",
        priorities=tuple(LAPTOP_PRIORITIES),
        spec_fields=SPEC_FIELDS,
        accessory_terms=ACCESSORY_TERMS,
        known_retailer_domains=frozenset(KNOWN_RETAILER_DOMAINS),
        manufacturer_domains=MANUFACTURER_DOMAINS,
        listing_fixture_path=_FIXTURE_DIR / "laptop_listings.json",
        spec_fixture_path=_FIXTURE_DIR / "laptop_specs.json",
        claim_term_patterns=_CLAIM_TERMS,
        accessory_reject_reason="likely_accessory_not_laptop",
        category_missing_reason="title_lacks_laptop_category_term",
        matches_category=matches_laptop_category,
        discovery_queries=_discovery_queries,
        discovery_search_query=_discovery_search_query,
        extract_identity=extract_identity,
        looks_like_rejected_fake=looks_like_rejected_fake,
        page_hints_for_model=page_hints_for_model,
        extract_specs=_extract_specs,
        score_page_fit=_score_page_fit,
        apply_consistency=_apply_consistency,
        apply_fallback=_apply_fallback,
        score_candidate=score_candidate,
        extra_limitations=_extra_limitations,
    )


PROFILE = build_profile()
