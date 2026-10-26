"""Bounded HTTPS page retrieval. Failures are data, not retries of the same URL."""

from __future__ import annotations

import io
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_PAGE_BYTES = 1_500_000
# Cap PDFs so live runs skip huge Dell owner manuals (~45 MB) and try the next
# hint (shop HTML / compact datasheet) instead of blocking for minutes.
# Lenovo PSREF / HP spec sheets are typically well under this.
MAX_PDF_BYTES = 8_000_000
MAX_PDF_PAGES = 40
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
ACCEPT = (
    "text/html,application/xhtml+xml,application/pdf;q=0.9,"
    "application/xhtml+xml;q=0.8,*/*;q=0.7"
)


@dataclass
class PageFetch:
    url: str
    outcome: str
    status_code: int | None
    text: str
    reason: str
    html: str = ""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return " ".join(parser.parts)


def _pdf_to_text(payload: bytes, max_pages: int = MAX_PDF_PAGES) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF retrieved but pypdf is not installed") from exc
    reader = PdfReader(io.BytesIO(payload))
    parts: list[str] = []
    for index, page in enumerate(reader.pages):
        if index >= max_pages:
            break
        extracted = page.extract_text() or ""
        if extracted.strip():
            parts.append(extracted)
    text = " ".join(" ".join(parts).split())
    if not text.strip():
        raise ValueError("PDF was retrieved but contains no extractable text")
    return text


def _looks_like_pdf(url: str, content_type: str, payload: bytes) -> bool:
    if payload[:4] == b"%PDF":
        return True
    if "pdf" in content_type:
        return True
    path = urlparse(url).path.casefold()
    return path.endswith(".pdf")


def _content_length(headers) -> int | None:
    raw = headers.get("Content-Length") if headers is not None else None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def fetch_page(url: str, timeout: int = 12, urlopen_fn=urlopen) -> PageFetch:
    """GET one HTTPS page or PDF. Does not follow instructions found in the page."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return PageFetch(url, "invalid_url", None, "", "Only HTTPS URLs are fetched")

    looks_pdf = parsed.path.casefold().endswith(".pdf")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": ACCEPT,
        "Accept-Language": "en-US,en;q=0.9",
    }

    if looks_pdf:
        try:
            head = Request(url, method="HEAD", headers=headers)
            with urlopen_fn(head, timeout=timeout) as response:
                length = _content_length(response.headers)
                if length is not None and length > MAX_PDF_BYTES:
                    return PageFetch(
                        url,
                        "empty",
                        getattr(response, "status", None),
                        "",
                        f"PDF Content-Length {length} exceeds {MAX_PDF_BYTES} byte safety cap",
                    )
        except Exception:
            # HEAD is best-effort; GET below still enforces the byte cap.
            pass

    request = Request(url, headers=headers)
    try:
        with urlopen_fn(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            content_type = (response.headers.get("Content-Type") or "").lower()
            final_url = response.geturl() or url
            length = _content_length(response.headers)
            wants_pdf = "pdf" in content_type or looks_pdf or urlparse(final_url).path.casefold().endswith(
                ".pdf"
            )
            if wants_pdf and length is not None and length > MAX_PDF_BYTES:
                return PageFetch(
                    url,
                    "empty",
                    status,
                    "",
                    f"PDF Content-Length {length} exceeds {MAX_PDF_BYTES} byte safety cap",
                )
            limit = MAX_PDF_BYTES if wants_pdf else MAX_PAGE_BYTES
            raw = response.read(limit + 1)
    except HTTPError as exc:
        code = exc.code
        if code in {401, 403, 429}:
            outcome = "blocked"
            reason = f"HTTP {code}: page refused automated access; not retried"
        else:
            outcome = "http_error"
            reason = f"HTTP {code}"
        return PageFetch(url, outcome, code, "", reason)
    except TimeoutError:
        return PageFetch(url, "timeout", None, "", "Timed out before a page body was received")
    except URLError as exc:
        return PageFetch(url, "unreachable", None, "", f"Could not reach host: {type(exc.reason).__name__}")

    if not raw:
        return PageFetch(url, "empty", status, "", "Response body was empty")

    is_pdf = _looks_like_pdf(final_url, content_type, raw)
    if is_pdf:
        if len(raw) > MAX_PDF_BYTES:
            return PageFetch(
                url,
                "empty",
                status,
                "",
                f"PDF exceeded {MAX_PDF_BYTES} byte safety cap; not truncated",
            )
        try:
            text = _pdf_to_text(raw)
        except Exception as exc:  # noqa: BLE001 - PDF parse failures are recorded outcomes
            return PageFetch(
                url,
                "empty",
                status,
                "",
                f"PDF retrieved but text could not be extracted: {type(exc).__name__}",
            )
        return PageFetch(
            final_url,
            "ok",
            status or 200,
            text,
            "Manufacturer PDF text retrieved",
            html="",
        )

    if len(raw) > MAX_PAGE_BYTES:
        raw = raw[:MAX_PAGE_BYTES]
    html = raw.decode("utf-8", errors="replace")
    text = html_to_text(html)
    if not text.strip() and "application/ld+json" not in html.casefold():
        return PageFetch(url, "empty", status, "", "Page HTML contained no readable text", html=html)
    return PageFetch(url, "ok", status or 200, text, "Page text retrieved", html=html)
