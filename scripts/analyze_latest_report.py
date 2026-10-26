"""Summarize output/latest_report.json for quick post-run checks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def main() -> None:
    path = Path("output/latest_report.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    print("mtime", path.stat().st_mtime)
    print("stages", data.get("stages_run"))
    print("request", data.get("request"))
    print("source_errors", data.get("source_errors"))
    print("recs", len(data.get("recommendations", [])))
    print("excluded", len(data.get("excluded", [])))
    print("dups", len(data.get("duplicate_offers", [])))
    print()
    print("=== RECOMMENDATIONS ===")
    for index, rec in enumerate(data.get("recommendations", []), 1):
        print(
            f"#{index} score={rec.get('score')} prov={rec.get('provisional')} | "
            f"{rec.get('listed_price')} | {rec.get('condition')} | "
            f"{rec.get('model')} | {rec.get('configuration')}"
        )
        print("  title:", (rec.get("name") or "")[:110])
        print(
            "  source:",
            rec.get("source"),
            "price_status",
            rec.get("price_status"),
            "delivered",
            rec.get("delivered_total_status"),
        )
        for key in ("cpu", "ram_gb", "storage", "display", "gpu", "battery"):
            value = (rec.get("specifications") or {}).get(key) or {}
            print(
                f"  {key}: {value.get('status')}/{value.get('evidence_strength')} = {value.get('value')}"
            )
            reason = value.get("reason") or ""
            if any(token in reason.lower() for token in ("conflict", "family", "listing")):
                print("    note:", reason[-200:])
        for evidence in rec.get("evidence", []):
            if evidence.get("field_name") == "manufacturer_page_accessibility":
                print(
                    "  mfr:",
                    evidence.get("status"),
                    (evidence.get("source_url") or "")[:85],
                )
        for reason in (rec.get("reasons") or [])[:10]:
            print("  reason:", reason)
        print()

    print("=== DUP REASONS ===")
    for item in data.get("duplicate_offers", [])[:8]:
        print(item.get("model"), "|", item.get("configuration"), "|", (item.get("reason") or "")[:120])

    print()
    print("=== EXCLUDED ===")
    counts = Counter(item.get("reason") for item in data.get("excluded", []))
    print(dict(counts))
    for item in data.get("excluded", [])[:10]:
        print(item.get("model"), item.get("reason"))

    print()
    print("=== LIMITATIONS (gate-related) ===")
    for line in data.get("limitations", []):
        if "compatible" in line.lower() or "datasheet" in line.lower() or "family" in line.lower():
            print("-", line)


if __name__ == "__main__":
    main()
