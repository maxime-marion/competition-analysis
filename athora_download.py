#!/usr/bin/env python3
"""Télécharge un document spécifique d'un fonds Profilife chez Athora."""

from __future__ import annotations

from pathlib import Path

from download_common import (
    document_links,
    download_from_html_catalogue,
    parse_download_args,
    pdf_filename_from_url,
    select_unique_match,
)


PAGE_URL = "https://www.athora.com/be/fr/bibliotheque/documents"
DEFAULT_FUND = "Profilife - Athora DNCA Invest Beyd Semperosa A"


def select_fund(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un fonds par libellé exact ou partiel."""
    return select_unique_match(
        links,
        query,
        missing_label="Fund",
        multiple_label="documents",
    )


def pdf_filename(url: str) -> str:
    return pdf_filename_from_url(url, "document-athora.pdf")


def fund_links(html: str, page_url: str) -> list[tuple[str, str]]:
    """Extrait les documents de fonds de la vue Athora."""
    return document_links(
        html,
        page_url,
        selector=".views-field-name",
        link_selector="a[href]",
    )


def download_fund(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    return download_from_html_catalogue(
        query,
        output_dir,
        page_url,
        user_agent="Athora-DIS-Downloader/1.0",
        extract_links=fund_links,
        select_link=select_fund,
        build_filename=lambda _title, url: pdf_filename(url),
    )


def parse_args():
    return parse_download_args(
        __doc__,
        item_option="fund",
        item_label="fund",
        default_item=DEFAULT_FUND,
        default_output_dir=Path("athora_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
