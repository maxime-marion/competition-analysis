#!/usr/bin/env python3
"""Télécharge un EID de fonds depuis le catalogue public Baloise."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from competition_analysis.download_common import (
    DocumentLink,
    download_from_html_catalogue,
    normalized,
    parse_download_args,
    pdf_filename_from_title,
    select_unique_match,
)


PAGE_URL = "https://mybaloise.baloise.be/nl/documenten/all-ipid-eid.html#eid"
CATALOGUE_URL = "https://baloise-be-nl.insurances.priips.clever-soft.com/"
DEFAULT_FUND = "Global Equity Fund"


def catalogue_documents(
    html: str, catalogue_url: str = CATALOGUE_URL
) -> list[DocumentLink]:
    """Extrait les libellés distinctifs et les URL des EID Baloise."""
    soup = BeautifulSoup(html, "html.parser")
    documents: list[DocumentLink] = []
    for row in soup.select("tr[data-productid]"):
        if not isinstance(row, Tag):
            continue
        fund = row.select_one(".product-name")
        link = row.select_one('td[data-col-id="downloads"] a[href]')
        if not isinstance(fund, Tag) or not isinstance(link, Tag):
            continue

        fund_name = fund.get_text(" ", strip=True)
        document_url = str(link.get("href", "")).strip()
        if not fund_name or not document_url:
            continue

        label_parts = [fund_name]
        for selector in (
            'td[data-col-id="linkedProducts"]',
            'td[data-col-id="costType"]',
        ):
            detail = row.select_one(selector)
            if not isinstance(detail, Tag):
                continue
            detail_text = detail.get_text(" ", strip=True)
            if detail_text and normalized(detail_text) not in {
                normalized(part) for part in label_parts
            }:
                label_parts.append(detail_text)

        documents.append(
            (" — ".join(label_parts), urljoin(catalogue_url, document_url))
        )

    unique_documents = list(dict.fromkeys(documents))
    if not unique_documents:
        raise RuntimeError("No EIDs were found in the Baloise catalogue.")
    return unique_documents


def select_fund(links: list[DocumentLink], query: str) -> DocumentLink:
    """Sélectionne un EID par nom de fonds ou libellé complet distinctif."""
    return select_unique_match(
        links,
        query,
        missing_label="Baloise fund",
        multiple_label="documents",
    )


def pdf_filename(title: str) -> str:
    return pdf_filename_from_title(title, "eid-baloise.pdf")


def eid_catalogue_url(page_url: str) -> str:
    """Résout la page Baloise officielle vers son catalogue EID intégré."""
    official_page = PAGE_URL.split("#", 1)[0]
    return (
        CATALOGUE_URL
        if page_url.rstrip("/").split("#", 1)[0] == official_page
        else page_url
    )


def download_fund(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    """Trouve puis télécharge l'EID public du fonds Baloise demandé."""
    catalogue_url = eid_catalogue_url(page_url)
    return download_from_html_catalogue(
        query,
        output_dir,
        catalogue_url,
        user_agent="Baloise-EID-Downloader/1.0",
        extract_links=catalogue_documents,
        select_link=select_fund,
        build_filename=lambda title, _url: pdf_filename(title),
    )


def parse_args():
    return parse_download_args(
        __doc__,
        item_option="fund",
        item_label="fund",
        default_item=DEFAULT_FUND,
        default_output_dir=Path("baloise_downloads"),
    )


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
