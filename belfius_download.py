#!/usr/bin/env python3
"""Download a Belfius fund document linked from the public retail home page."""

from __future__ import annotations

from pathlib import Path

from download_common import (
    create_session,
    document_links,
    download_pdf,
    parse_download_args,
    pdf_filename_from_url,
    sanitized_filename,
    select_unique_match,
)


PAGE_URL = "https://www.belfius.be/site/retail/fr"
DEFAULT_FUND = "Belfius Global Equity Fund"


def fund_links(html: str, page_url: str = PAGE_URL) -> list[tuple[str, str]]:
    """Return all labelled links found directly on the Belfius main page."""
    return document_links(html, page_url, require_pdf=False)


def select_fund_link(
    links: list[tuple[str, str]], query: str
) -> tuple[str, str]:
    """Select a unique main-page link by its visible fund name."""
    return select_unique_match(
        links,
        query,
        missing_label="Belfius fund link",
        multiple_label="Belfius links",
    )


def download_fund(
    query: str, output_dir: Path, page_url: str = PAGE_URL
) -> Path:
    """Find the named fund link on the main page and download it as a PDF."""
    session = create_session("Belfius-Fund-Downloader/1.0")
    page_response = session.get(page_url, timeout=30)
    page_response.raise_for_status()
    fund_title, document_url = select_fund_link(
        fund_links(page_response.text, page_url), query
    )

    fallback = sanitized_filename(fund_title, "belfius-fund")
    if not fallback.casefold().endswith(".pdf"):
        fallback += ".pdf"
    destination = download_pdf(
        session,
        document_url,
        output_dir,
        pdf_filename_from_url(document_url, fallback),
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
        default_output_dir=Path("belfius_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
