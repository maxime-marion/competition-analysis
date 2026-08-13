#!/usr/bin/env python3
"""Download a French KID from KBC's public investment-document catalogue."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from download_common import (
    create_session,
    download_pdf,
    parse_download_args,
    pdf_filename_from_url,
    select_unique_match,
)


KID_INDEX_URL = (
    "https://www.kbc.be/particulieren/nl/juridische-info/"
    "documentatie-beleggen/essentiele-informatiedocumenten.html"
)
PAGE_URL = KID_INDEX_URL
DEFAULT_FUND = "KBC Defensive Balanced Classic Shares CAP"

LANGUAGE_LABELS = {"bg", "cs", "de", "en", "fr", "hu", "nl", "pl", "sk", "sl"}
KID_PATH = re.compile(r"/KID/", re.IGNORECASE)
KID_LANGUAGE_SUFFIX = re.compile(r"_[A-Z]{2}\.PDF$", re.IGNORECASE)
KID_ISIN = re.compile(r"KID_([A-Z]{2}[A-Z0-9]+)_[A-Z]{2}\.PDF$", re.IGNORECASE)


def _french_document_url(url: str) -> str:
    """Correct the occasional KBC FR anchor that points to another language."""
    return KID_LANGUAGE_SUFFIX.sub("_FR.PDF", url)


def _fund_title(item: Tag) -> str:
    """Read the text preceding the language links in one catalogue item."""
    parts: list[str] = []
    for value in item.stripped_strings:
        text = value.strip()
        if text.casefold() in LANGUAGE_LABELS:
            break
        if text:
            parts.append(text)
    return " ".join(parts)


def kid_links(html: str, page_url: str = KID_INDEX_URL) -> list[tuple[str, str]]:
    """Return every French KID, enriched with its fund family and ISIN."""
    soup = BeautifulSoup(html, "html.parser")
    documents: dict[str, tuple[str, str]] = {}
    for item in soup.select("li"):
        if not isinstance(item, Tag):
            continue
        french_link = next(
            (
                link
                for link in item.select("a[href]")
                if isinstance(link, Tag)
                and link.get_text(" ", strip=True).casefold() == "fr"
                and KID_PATH.search(str(link.get("href", "")))
            ),
            None,
        )
        if french_link is None:
            continue

        fund_title = _fund_title(item)
        if not fund_title:
            continue
        document_url = _french_document_url(
            urljoin(page_url, str(french_link["href"]))
        )
        family_heading = item.find_previous("h2")
        family = (
            family_heading.get_text(" ", strip=True)
            if isinstance(family_heading, Tag)
            else ""
        )
        filename = Path(urlparse(document_url).path).name
        isin_match = KID_ISIN.search(filename)
        details = [fund_title]
        if family:
            details.append(family)
        if isin_match:
            details.append(isin_match.group(1).upper())
        documents.setdefault(document_url, (" — ".join(details), document_url))

    if not documents:
        raise RuntimeError("No French KIDs were found in the KBC catalogue.")
    return list(documents.values())


def select_kid(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Select one KBC KID by its fund name."""
    return select_unique_match(
        links,
        query,
        missing_label="KBC fund KID",
        multiple_label="KBC KIDs",
    )


def download_fund(
    query: str, output_dir: Path, page_url: str = PAGE_URL
) -> Path:
    """Find and download the French KID for a KBC fund."""
    session = create_session("KBC-KID-Downloader/1.0")

    source_response = session.get(page_url, timeout=30)
    source_response.raise_for_status()
    links = kid_links(source_response.text, page_url)
    fund_title, document_url = select_kid(links, query)
    destination = download_pdf(
        session,
        document_url,
        output_dir,
        pdf_filename_from_url(document_url, "kid-kbc.pdf"),
    )

    print(f"Fund: {fund_title}")
    print(f"URL: {document_url}")
    print(f"Saved to: {destination.resolve()}")
    return destination


def parse_args():
    return parse_download_args(
        __doc__,
        item_option="fund",
        item_label="fund",
        default_item=DEFAULT_FUND,
        default_output_dir=Path("kbc_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
