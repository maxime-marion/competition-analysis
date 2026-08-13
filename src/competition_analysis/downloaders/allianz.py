#!/usr/bin/env python3
"""Télécharge un DIC depuis le catalogue public Allianz."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from competition_analysis.download_common import (
    DocumentLink,
    create_session,
    download_selected_pdf,
    normalized,
    parse_download_args,
    pdf_filename_from_title,
    select_unique_match,
)


PAGE_URL = "https://www.allianz.be/fr/particuliers/documents.html"
API_BASE_URL = "https://apps.allianz.be/myallianz-documents/bff"
API_DOCUMENTS_URL = f"{API_BASE_URL}/documents"
INVESTMENT_CATEGORY = "Investissement"
DOCUMENT_TYPE = "Document d’informations clés"
DEFAULT_DOCUMENT = "Document d’informations clés Allianz ActiveInvest"


def documents_api_url(page_url: str) -> str:
    """Résout la page Allianz officielle vers l'API de son centre de documents."""
    return API_DOCUMENTS_URL if page_url.rstrip("/") == PAGE_URL else page_url


def catalogue_documents(
    data: object, api_base_url: str = API_BASE_URL
) -> list[DocumentLink]:
    """Extrait les DIC d'investissement et leurs URL depuis la réponse Allianz."""
    if not isinstance(data, list):
        raise RuntimeError("The Allianz document catalogue has an invalid format.")

    category = next(
        (
            item
            for item in data
            if isinstance(item, dict)
            and normalized(str(item.get("sectionName", "")))
            == normalized(INVESTMENT_CATEGORY)
        ),
        None,
    )
    if category is None:
        raise RuntimeError(
            "The Investment category was not found in the Allianz catalogue."
        )

    documents: list[DocumentLink] = []
    for product in category.get("subSection", []):
        if not isinstance(product, dict):
            continue
        for document_group in product.get("subSection", []):
            if not isinstance(document_group, dict) or normalized(
                str(document_group.get("sectionName", ""))
            ) != normalized(DOCUMENT_TYPE):
                continue
            for asset in document_group.get("assets", []):
                if not isinstance(asset, dict) or asset.get("secured") is True:
                    continue
                title = str(asset.get("title", "")).strip()
                path = str(asset.get("url", "")).strip()
                if title and path:
                    documents.append(
                        (title, urljoin(f"{api_base_url}/", path.lstrip("/")))
                    )

    unique_documents = list(dict.fromkeys(documents))
    if not unique_documents:
        raise RuntimeError("No investment KIDs were found in the Allianz catalogue.")
    return unique_documents


def select_document(links: list[DocumentLink], query: str) -> DocumentLink:
    """Sélectionne un DIC Allianz par libellé exact ou partiel distinctif."""
    return select_unique_match(
        links,
        query,
        missing_label="Allianz document",
        multiple_label="documents",
    )


def pdf_filename(title: str) -> str:
    return pdf_filename_from_title(title, "document-allianz.pdf")


def download_document(
    query: str, output_dir: Path, page_url: str = PAGE_URL
) -> Path:
    """Trouve puis télécharge le DIC public Allianz demandé sans navigateur."""
    session = create_session("Allianz-Document-Downloader/1.0")
    session.headers.update(
        {
            "language": "fr",
            "reference_type": "AEMPROLINKNET",
            "x-correlation-id": str(uuid4()),
        }
    )

    api_url = documents_api_url(page_url)
    catalogue_response = session.get(api_url, timeout=30)
    catalogue_response.raise_for_status()
    title, document_url = select_document(
        catalogue_documents(catalogue_response.json(), api_url.rsplit("/", 1)[0]),
        query,
    )

    return download_selected_pdf(
        session,
        document_url,
        output_dir,
        pdf_filename(title),
        details=(("Document", title),),
    )


def parse_args():
    return parse_download_args(
        __doc__,
        item_option="document",
        item_label="document",
        default_item=DEFAULT_DOCUMENT,
        default_output_dir=Path("allianz_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_document(arguments.document, arguments.output_dir)
