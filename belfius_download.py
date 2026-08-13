#!/usr/bin/env python3
"""Download a Belfius fund document linked from the public retail home page."""

from __future__ import annotations

from pathlib import Path

from download_common import (
    document_links,
    download_from_html_catalogue,
    parse_download_args,
    pdf_filename_from_title,
    pdf_filename_from_url,
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


def pdf_filename(title: str, url: str) -> str:
    fallback = pdf_filename_from_title(title, "belfius-fund.pdf")
    return pdf_filename_from_url(url, fallback)


def download_fund(
    query: str, output_dir: Path, page_url: str = PAGE_URL
) -> Path:
    """Find the named fund link on the main page and download it as a PDF."""
    return download_from_html_catalogue(
        query,
        output_dir,
        page_url,
        user_agent="Belfius-Fund-Downloader/1.0",
        extract_links=fund_links,
        select_link=select_fund_link,
        build_filename=pdf_filename,
        item_label="Fund",
    )


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
