"""Conservative laptop-spec extraction from manufacturer page or PDF text."""

from __future__ import annotations

import re
from typing import Iterable

_CPU_SKU_RE = re.compile(
    r"\b((?:Intel\s*[®*]?\s*)?Core\s+(?:Ultra\s+)?[iI][3579]-\d{3,5}[A-Z]{0,3}"
    r"|(?:AMD\s*[®*]?\s*)?Ryzen\s+[3579]\s+\d{3,5}[A-Z]{0,3}"
    r"|Intel\s*[®*]?\s*Processor\s+U\d{3}"
    r"|Intel\s*[®*]?\s*(?:Pentium|Celeron)(?:\s*[®*]?\s*(?:Silver|Gold))?\s*[®*]?\s*[A-Z]?\d{4,}[A-Z]?"
    r"|Apple\s+M[1-4](?:\s+Pro|\s+Max)?)\b",
    re.I,
)
_CPU_RE = re.compile(
    r"\b((?:Intel\s*[®*]?\s*)?Core\s+(?:Ultra\s+)?[iI][3579](?:[-\s]\d{3,5}[A-Z]{0,3})?"
    r"|(?:Intel\s*[®*]?\s*)?Core\s+[357](?:\s+\d{3,5})?"
    r"|(?:AMD\s*[®*]?\s*)?Ryzen\s+[3579](?:\s+\d{3,5}[A-Z]{0,3})?"
    r"|Intel\s*[®*]?\s*Processor\s+U\d{3}"
    r"|Intel\s*[®*]?\s*(?:Pentium|Celeron)(?:\s+(?:Silver|Gold))?(?:\s+[A-Z]?\d{4,}[A-Z]?)?"
    r"|Apple\s+M[1-4](?:\s+Pro|\s+Max)?)\b",
    re.I,
)
_RAM_RE = re.compile(
    r"\b(\d{1,3})\s*GB\s*(?:RAM|DDR\d|LPDDR\d|SO-DIMM|soldered|memory)\b",
    re.I,
)
_RAM_UP_TO_RE = re.compile(
    r"\b(?:Max(?:imum)?\s+Memory|Memory)\b[^.]{0,80}?\b(?:Up to\s+)?(\d{1,3})\s*GB\b",
    re.I,
)
# M.2 is only valid before SSD/HDD. "2 TB M.2 eMMC" is a PDF line-join false positive.
_STORAGE_RE = re.compile(
    r"\b(\d+)\s*(GB|TB)\s*(?:PCIe\s+)?(?:NVMe\s+)?(?:(?:M\.2\s+)?(SSD|HDD)|(eMMC|UFS))\b",
    re.I,
)
_STORAGE_OFFERING_RE = re.compile(
    r"\b(\d+)\s*(GB|TB)\s*/\s*(?:\d+\s*(?:GB|TB)\s*/\s*)*(?:\d+\s*(?:GB|TB)\s+)?(?:M\.2\s+)?SSD\b",
    re.I,
)
_STORAGE_UP_TO_RE = re.compile(
    r"\b(?:M\.2\s+)?SSD\s+up to\s+(\d+)\s*(GB|TB)\b"
    r"|\bup to\s+(\d+)\s*(GB|TB)\s+(?:M\.2\s+)?SSD\b"
    r"|\bSolid-state drive\b.{0,60}?\bUp to\s+(\d+)\s*(GB|TB)\b",
    re.I,
)
_STORAGE_REJECT_RE = re.compile(
    r"\b(?:microsd|sd\s*card|card reader|media[- ]card|memory card)\b",
    re.I,
)
_DISPLAY_RE = re.compile(
    r"\b(\d{2}(?:\.\d)?)\s*(?:-?inch|\"|'')\b(?:[^.]{0,80})\b(FHD|QHD|OLED|WUXGA|UHD|HD|1920\s*x\s*1080|1366\s*x\s*768)\b",
    re.I,
)
_DISPLAY_SIZE_FHD_RE = re.compile(
    r"\b(\d{2}(?:\.\d)?)\"\s*(?:diagonal[^,]{0,40})?(?:FHD|1920\s*x\s*1080)\b",
    re.I,
)
_GPU_RE = re.compile(
    r"\b(NVIDIA\s+GeForce\s+RTX\s+\d{3,4}(?:\s*Ti)?"
    r"|GeForce\s+RTX\s+\d{3,4}"
    r"|RTX\s+\d{3,4}"
    r"|AMD\s*[®*]?\s*Radeon(?:\s+[A-Za-z0-9]+)*"
    r"|Intel\s*[®*]?\s*(?:UHD|Iris\s*X[eé]|Graphics)(?:\s+\w+)?"
    r"|Integrated Intel graphics)\b",
    re.I,
)
_BATTERY_LIFE_RE = re.compile(
    r"\b(?:Max(?:imum)?\s+Battery\s+Life|Battery\s+life(?:video)?|video\s+playback)"
    r"[^.]{0,120}?\b(\d{1,3}(?:\.\d)?)\s*(?:hours|hrs|hr)\b",
    re.I,
)
_BATTERY_RE = re.compile(r"\b(\d{1,3}(?:\.\d)?)\s*(?:hours|hrs|hr)\b", re.I)
_BATTERY_CONTEXT_RE = re.compile(r"\b(?:battery\s+life|Max Battery Life|video\s+playback)\b", re.I)
_BATTERY_REJECT_RE = re.compile(
    r"\b(?:charge|charging|recharge|rapid charge|15-minute|minutes?)\b",
    re.I,
)


def _snippet(
    text: str,
    match: re.Match[str],
    radius: int = 90,
    *,
    model: str | None = None,
) -> str:
    if model:
        from shopping_agent.evidence_context import model_linked_snippet

        return model_linked_snippet(text, match, model, radius=radius)
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return " ".join(text[start:end].split())


def _identity_sku_tokens(model_key: str) -> tuple[str, ...]:
    """Chassis / machine-type / product tokens that must appear when identity includes them."""
    tokens: list[str] = []
    if "inspiron" in model_key:
        chassis = re.search(r"\b(\d{4})$", model_key)
        if chassis:
            tokens.append(chassis.group(1))
    mt = re.search(r"\b(15[a-z]{2,4}\d{1,2})$", model_key)
    if mt:
        tokens.append(mt.group(1))
    product = re.search(r"\b(\d{2}-[a-z]\d{3,4}[a-z]{0,2})$", model_key)
    if product:
        tokens.append(product.group(1))
    return tuple(tokens)


def page_mentions_model(text: str, model: str) -> bool:
    collapsed = " ".join(text.split()).casefold()
    model_key = model.casefold().strip()
    if not model_key:
        return False

    family_hit = False
    if model_key in collapsed:
        family_hit = True
    else:
        # Manufacturer pages/PDFs often omit the brand token ("Latitude 3500",
        # "IdeaPad Slim 3 15IRH10").
        parts = model_key.split(None, 1)
        if len(parts) == 2 and parts[1] in collapsed:
            family_hit = True
        else:
            # Compact PDF titles: "IdeaPad_Slim_3_15IRH10" / "Inspiron 15 3530".
            underscored = parts[1].replace(" ", "_") if len(parts) == 2 else ""
            family_hit = bool(underscored and underscored in collapsed.replace(" ", "_"))

    if not family_hit:
        return False

    # When identity includes a chassis/SKU, reject sibling manuals (3530 ≠ 3535).
    sku_tokens = _identity_sku_tokens(model_key)
    if not sku_tokens:
        return True
    return any(token in collapsed for token in sku_tokens)


def _count_extracted(extracted: dict[str, tuple[str | None, str | None, str]]) -> int:
    return sum(1 for value, _, _ in extracted.values() if value)


def _cpu_token_hit(value: str, prefer_cpu_tokens: Iterable[str]) -> bool:
    compact_value = re.sub(r"[^a-z0-9]", "", value.casefold())
    for token in prefer_cpu_tokens:
        compact = re.sub(r"[^a-z0-9]", "", token.casefold())
        if not compact:
            continue
        if compact in compact_value or token.casefold() in value.casefold():
            return True
        bare = re.fullmatch(r"i([3579]\d{3,5}[a-z]*)", compact)
        if bare and f"corei{bare.group(1)}" in compact_value:
            return True
    return False


def _pick_cpu(text: str, prefer_cpu_tokens: tuple[str, ...] = ()):
    matches = list(_CPU_SKU_RE.finditer(text)) + list(_CPU_RE.finditer(text))
    if not matches:
        return None
    if prefer_cpu_tokens:
        for match in matches:
            if _cpu_token_hit(match.group(1), prefer_cpu_tokens):
                return match
    return matches[0]


def _pick_ram(text: str, prefer_ram_gb: int | None):
    matches = list(_RAM_RE.finditer(text))
    if prefer_ram_gb is not None:
        for match in matches:
            if int(match.group(1)) == prefer_ram_gb:
                return match
        # Exact installed memory beats a larger "up to" family ceiling.
        for match in _RAM_UP_TO_RE.finditer(text):
            if int(match.group(1)) == prefer_ram_gb:
                return match
    if matches:
        return matches[0]
    return _RAM_UP_TO_RE.search(text)


def _storage_gb(amount: int, unit: str) -> int:
    return amount * 1024 if unit.upper() == "TB" else amount


def _pick_storage(text: str, prefer_storage_gb: int | None):
    candidates: list[tuple[re.Match[str], str]] = []
    for match in _STORAGE_RE.finditer(text):
        window = text[max(0, match.start() - 50) : match.end() + 50]
        if _STORAGE_REJECT_RE.search(window):
            continue
        kind = (match.group(3) or match.group(4) or "").upper()
        value = f"{match.group(1)}{match.group(2).upper()} {kind}"
        candidates.append((match, value))
    for match in _STORAGE_OFFERING_RE.finditer(text):
        value = f"{match.group(1)}{match.group(2).upper()} SSD"
        candidates.append((match, value))
    for match in _STORAGE_UP_TO_RE.finditer(text):
        amount = next((g for g in match.groups()[0::2] if g), None)
        unit = next((g for g in match.groups()[1::2] if g), "GB")
        if amount is None:
            continue
        value = f"{amount}{unit.upper()} SSD"
        candidates.append((match, value))

    if not candidates:
        return None, None
    if prefer_storage_gb is not None:
        for match, value in candidates:
            parsed = re.search(r"(\d+)\s*(GB|TB)", value, re.I)
            if not parsed:
                continue
            if _storage_gb(int(parsed.group(1)), parsed.group(2)) == prefer_storage_gb:
                return match, value
    match, value = candidates[0]
    return match, value


def extract_laptop_specs(
    text: str,
    *,
    prefer_cpu_tokens: tuple[str, ...] = (),
    prefer_ram_gb: int | None = None,
    prefer_storage_gb: int | None = None,
    model: str | None = None,
) -> dict[str, tuple[str | None, str | None, str]]:
    """Return field -> (value, supporting_text, reason).

    When prefer_* values are provided (from the listing), choose matching options
    from multi-config manufacturer manuals instead of the first family option.
    """
    found: dict[str, tuple[str | None, str | None, str]] = {}

    cpu = _pick_cpu(text, prefer_cpu_tokens)
    found["cpu"] = (
        (cpu.group(1), _snippet(text, cpu, model=model), "explicit processor wording")
        if cpu
        else (None, None, "No explicit matching specification found in retrieved manufacturer text")
    )

    ram = _pick_ram(text, prefer_ram_gb)
    found["ram_gb"] = (
        (ram.group(1), _snippet(text, ram, model=model), "explicit memory wording")
        if ram
        else (None, None, "No explicit matching specification found in retrieved manufacturer text")
    )

    storage_match, storage_value = _pick_storage(text, prefer_storage_gb)
    if storage_match and storage_value:
        found["storage"] = (
            storage_value,
            _snippet(text, storage_match, model=model),
            "explicit storage wording",
        )
    else:
        found["storage"] = (
            None,
            None,
            "No explicit matching specification found in retrieved manufacturer text",
        )

    display = _DISPLAY_RE.search(text)
    if display:
        panel = display.group(2).upper()
        if "1920" in panel:
            panel = "FHD"
        elif "1366" in panel:
            panel = "HD"
        value = f"{display.group(1)}-inch {panel}"
        found["display"] = (value, _snippet(text, display, model=model), "explicit display wording")
    else:
        sized = _DISPLAY_SIZE_FHD_RE.search(text)
        if sized:
            value = f"{sized.group(1)}-inch FHD"
            found["display"] = (value, _snippet(text, sized, model=model), "explicit display wording")
        else:
            found["display"] = (
                None,
                None,
                "No explicit matching specification found in retrieved manufacturer text",
            )

    gpu = _GPU_RE.search(text)
    found["gpu"] = (
        (gpu.group(1), _snippet(text, gpu, model=model), "explicit graphics wording")
        if gpu
        else (None, None, "No explicit matching specification found in retrieved manufacturer text")
    )

    battery = _BATTERY_LIFE_RE.search(text)
    if battery is None:
        for match in _BATTERY_RE.finditer(text):
            window = text[max(0, match.start() - 100) : match.end() + 40]
            if _BATTERY_REJECT_RE.search(window):
                continue
            if _BATTERY_CONTEXT_RE.search(window):
                battery = match
                break
    found["battery"] = (
        (f"{battery.group(1)} hours", _snippet(text, battery, model=model), "explicit battery-life wording")
        if battery
        else (None, None, "No explicit battery-life claim linked to the word battery")
    )
    return found


def extracted_spec_count(
    text: str,
    *,
    prefer_cpu_tokens: tuple[str, ...] = (),
    prefer_ram_gb: int | None = None,
    prefer_storage_gb: int | None = None,
) -> int:
    return _count_extracted(
        extract_laptop_specs(
            text,
            prefer_cpu_tokens=prefer_cpu_tokens,
            prefer_ram_gb=prefer_ram_gb,
            prefer_storage_gb=prefer_storage_gb,
        )
    )
