#!/usr/bin/env python3
"""Télécharge un document NN depuis la page des documents légaux."""

from __future__ import annotations

from pathlib import Path

from download_common import (
    create_session,
    document_links,
    download_pdf,
    normalized,
    parse_download_args,
    sanitized_filename,
    select_unique_match,
)


PAGE_URL = "https://www.nn.be/fr/documents-legaux"
DEFAULT_DOCUMENT = "NN Blackrock Global Allocation Fund"


def select_document(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un document, en privilégiant le DIC lorsqu'il est présent."""
    key_information_documents = [
        item
        for item in links
        if "document d'informations cles" in normalized(item[0])
    ]
    return select_unique_match(
        key_information_documents or links,
        query,
        missing_label="Document",
        multiple_label="documents",
    )


def pdf_filename(title: str) -> str:
    return f"{sanitized_filename(title, 'document-nn')}.pdf"


def download_document(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    session = create_session("NN-Document-Downloader/1.0")

    page_response = session.get(page_url, timeout=30)
    page_response.raise_for_status()
    title, document_url = select_document(
        document_links(
            page_response.text,
            page_url,
            selector="a.download-link[href]",
            require_pdf=False,
        ),
        query,
    )

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
