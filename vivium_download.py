#!/usr/bin/env python3
"""Télécharge un document de fonds depuis la page Fiches info Vivium."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from download_common import (
    create_session,
    download_pdf,
    normalized,
    parse_download_args,
    pdf_filename_from_url,
    select_unique_match,
)


PAGE_URL = "https://www.vivium.be/fr/private-individuals/fiches-info"
DEFAULT_FUND = "DIC - Branche 23 Euro Corporate SRI Bonds"


def fund_links(html: str, page_url: str = PAGE_URL) -> list[tuple[str, str]]:
    """Retourne les liens PDF affichés sur la page Vivium.

    La sélection du fonds se fait ensuite sur son nom complet, sans dépendre du
    libellé ou de la structure d'une section de la page.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for element in soup.find_all("a", href=True):
        if not isinstance(element, Tag):
            continue
        document_url = urljoin(page_url, str(element["href"]))
        if ".pdf" not in urlparse(document_url).path.casefold():
            continue
        links.append((element.get_text(" ", strip=True), document_url))
    return links


def select_fund(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un fonds par libellé exact ou partiel."""
    return select_unique_match(
        links, query, missing_label="Fund", multiple_label="documents"
    )


def pdf_filename(url: str) -> str:
    """Extrait le nom du PDF depuis l'URL Vivium."""
    return pdf_filename_from_url(url, "dic.pdf")


def download_fund(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    session = create_session("Vivium-DIC-Downloader/1.0")

    page_response = session.get(page_url, timeout=30)
    page_response.raise_for_status()
    title, document_url = select_fund(fund_links(page_response.text, page_url), query)

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
        default_output_dir=Path("vivium_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
