#!/usr/bin/env python3
"""Télécharge un document NN depuis la page des documents légaux."""

from __future__ import annotations

from pathlib import Path

from competition_analysis.download_common import (
    document_links,
    download_from_html_catalogue,
    normalized,
    parse_download_args,
    pdf_filename_from_title,
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
    return pdf_filename_from_title(title, "document-nn.pdf")


def catalogue_documents(html: str, page_url: str) -> list[tuple[str, str]]:
    """Extrait les liens de téléchargement affichés par NN."""
    return document_links(
        html,
        page_url,
        selector="a.download-link[href]",
        require_pdf=False,
    )


def download_document(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    return download_from_html_catalogue(
        query,
        output_dir,
        page_url,
        user_agent="NN-Document-Downloader/1.0",
        extract_links=catalogue_documents,
        select_link=select_document,
        build_filename=lambda title, _url: pdf_filename(title),
    )


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
