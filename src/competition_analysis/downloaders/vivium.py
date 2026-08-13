#!/usr/bin/env python3
"""Télécharge un document de fonds depuis la page Fiches info Vivium."""

from __future__ import annotations

from pathlib import Path

from competition_analysis.download_common import (
    document_links,
    download_from_html_catalogue,
    parse_download_args,
    pdf_filename_from_url,
    select_unique_match,
)


PAGE_URL = "https://www.vivium.be/fr/private-individuals/fiches-info"
DEFAULT_FUND = "DIC - Branche 23 Euro Corporate SRI Bonds"


def select_fund(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un fonds par libellé exact ou partiel."""
    return select_unique_match(
        links, query, missing_label="Fund", multiple_label="documents"
    )


def pdf_filename(url: str) -> str:
    """Extrait le nom du PDF depuis l'URL Vivium."""
    return pdf_filename_from_url(url, "dic.pdf")


def download_fund(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    return download_from_html_catalogue(
        query,
        output_dir,
        page_url,
        user_agent="Vivium-DIC-Downloader/1.0",
        extract_links=document_links,
        select_link=select_fund,
        build_filename=lambda _title, url: pdf_filename(url),
    )


def parse_args():
    return parse_download_args(
        __doc__,
        item_option="fund",
        item_label="fund",
        default_item=DEFAULT_FUND,
        default_output_dir=Path("vivium_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
