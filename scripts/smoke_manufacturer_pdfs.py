"""One-off smoke check for manufacturer PDF research paths."""

from shopping_agent.http_fetch import fetch_page
from shopping_agent.spec_extract import extract_laptop_specs, page_mentions_model

URLS = [
    (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_Slim_3_15IRH10/IdeaPad_Slim_3_15IRH10_Spec.pdf",
        "Lenovo IdeaPad Slim 3",
    ),
    (
        "https://dl.dell.com/content/manual77626568-inspiron-15-3530-with-usb-type-c-owner-s-manual.pdf?language=en-us",
        "Dell Inspiron 15",
    ),
    (
        "https://pcb.inc.hp.com/dc/api/spec-sheet/ww-en/2100700561/pdf/3V2M6EA.pdf",
        "HP Pavilion 15",
    ),
    (
        "https://psref.lenovo.com/syspool/Sys/PDF/IdeaPad/IdeaPad_1_15IGL7/IdeaPad_1_15IGL7_Spec.PDF",
        "Lenovo IdeaPad 1",
    ),
]


def main() -> None:
    for url, model in URLS:
        page = fetch_page(url, timeout=30)
        print("==", model, page.outcome, "chars", len(page.text), page.reason[:80])
        if page.outcome != "ok":
            continue
        print(" mentions", page_mentions_model(page.text, model))
        specs = extract_laptop_specs(page.text)
        for key, (value, _, _) in specs.items():
            if value:
                print(" ", key, "=", value)


if __name__ == "__main__":
    main()
