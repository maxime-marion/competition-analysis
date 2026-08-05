#!/usr/bin/env python3
"""Télécharge un document de la section NN Strategy non fiscale (branche 23)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from download_common import (
    create_session,
    download_pdf,
    normalized,
    parse_download_args,
    sanitized_filename,
    select_unique_match,
)


PAGE_URL = "https://www.nn.be/fr/documents-legaux"
SECTION_TEXT = "Voor niet-fiscale producten NN Strategy (tak 23)"
DEFAULT_DOCUMENT = "NN Blackrock Global Allocation Fund"


def section_links(html: str, page_url: str = PAGE_URL) -> list[tuple[str, str]]:
    """Retourne les documents du bloc NN Strategy non fiscal (branche 23)."""
    soup = BeautifulSoup(html, "html.parser")
    heading_text = soup.find(
        string=lambda value: bool(value)
        and normalized(str(value)) == normalized(SECTION_TEXT)
    )
    if heading_text is None:
        raise RuntimeError(f"The “{SECTION_TEXT}” section was not found.")

    container = heading_text.find_parent(
        "div", class_="paragraphs-item-pt-accordion-item"
    )
    if container is None:
        raise RuntimeError("The NN Strategy section content was not found.")

    links: list[tuple[str, str]] = []
    for link in container.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        title = link.get_text(" ", strip=True)
        normalized_title = normalized(title)
        if (
            title
            and "essentiele" in normalized_title
            and "informatiedocument" in normalized_title
        ):
            links.append((title, urljoin(page_url, str(link["href"]))))
    return links


def select_document(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un document par libellé exact ou partiel."""
    return select_unique_match(
        links, query, missing_label="Document", multiple_label="documents"
    )


def pdf_filename(title: str) -> str:
    return f"{sanitized_filename(title, 'document-nn')}.pdf"


def download_document(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    session = create_session("NN-Document-Downloader/1.0")

    page_response = session.get(page_url, timeout=30)
    page_response.raise_for_status()
    title, document_url = select_document(section_links(page_response.text, page_url), query)

    destination = download_pdf(session, document_url, output_dir, pdf_filename(title))

    print(f"Document: {title}")
    print(f"URL: {document_url}")
    print(f"Saved to: {destination.resolve()}")
    return destination


def parse_args():
    return parse_download_args(
        __doc__,
        item_option="document",
        item_label="document",
        default_item=DEFAULT_DOCUMENT,
        default_output_dir=Path("nn_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_document(arguments.document, arguments.output_dir)
