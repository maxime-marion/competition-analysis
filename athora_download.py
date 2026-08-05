#!/usr/bin/env python3
"""Télécharge un document spécifique d'un fonds Profilife chez Athora."""

from __future__ import annotations

from pathlib import Path

from download_common import (
    create_session,
    document_links,
    download_pdf,
    parse_download_args,
    pdf_filename_from_url,
    select_unique_match,
)


PAGE_URL = "https://www.athora.com/be/fr/bibliotheque/documents"
DEFAULT_FUND = "Profilife - Athora DNCA Invest Beyd Semperosa A"


def select_fund(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne la fiche de fonds par libellé exact ou partiel."""
    fund_sheets = [
        item for item in links if "/fundsheetonline/" in item[1].casefold()
    ]
    return select_unique_match(
        fund_sheets or links,
        query,
        missing_label="Fund",
        multiple_label="documents",
    )


def pdf_filename(url: str) -> str:
    return pdf_filename_from_url(url, "document-athora.pdf")


def download_fund(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    session = create_session("Athora-DIS-Downloader/1.0")

    page_response = session.get(page_url, timeout=30)
    page_response.raise_for_status()
    title, document_url = select_fund(
        document_links(
            page_response.text,
            page_url,
            selector=".views-field-name",
            link_selector="a[href]",
        ),
        query,
    )

    destination = download_pdf(session, document_url, output_dir, pdf_filename(document_url))

    print(f"Document: {title}")
    print(f"URL: {document_url}")
    print(f"Saved to: {destination.resolve()}")
    return destination


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
