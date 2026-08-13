#!/usr/bin/env python3
"""Télécharge le KID d'un fonds AG depuis le catalogue MuMa public."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from download_common import (
    create_session,
    document_links,
    download_pdf,
    normalized,
    pdf_filename_from_url,
    select_unique_match,
)


BROKER_CATALOGUE_URL = "https://ag.ag-muma.be/fr/allfunds"
BANK_CATALOGUE_URL = "https://bnppf.ag-muma.be/fr/allfunds"
DEFAULT_FUND = "AG Life Optitrack Equities"
BANK_DEFAULT_FUND = "AG Life Sustainable Defensive"

CHANNEL_CATALOGUE_URLS = {
    "broker": BROKER_CATALOGUE_URL,
    "bank": BANK_CATALOGUE_URL,
}
CHANNEL_DEFAULT_FUNDS = {
    "broker": DEFAULT_FUND,
    "bank": BANK_DEFAULT_FUND,
}


def catalogue_funds(html: str, catalogue_url: str) -> list[tuple[str, str]]:
    """Extrait les couples nom/URL des fonds présents dans le catalogue AG."""
    soup = BeautifulSoup(html, "html.parser")
    funds: dict[str, tuple[str, str]] = {}
    for link in soup.select('a[href*="/fr/fund/"]'):
        if not isinstance(link, Tag):
            continue
        title = link.get_text(" ", strip=True)
        if not title:
            continue
        url = urljoin(catalogue_url, str(link["href"]))
        funds.setdefault(url, (title, url))
    if not funds:
        raise RuntimeError("No funds were found in the AG catalogue.")
    return list(funds.values())


def select_fund(funds: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un fonds par nom exact ou partie distinctive du nom."""
    return select_unique_match(
        funds, query, missing_label="AG fund", multiple_label="documents"
    )


def kid_links(html: str, fund_url: str) -> list[tuple[str, str]]:
    """Retourne les liens PDF dont le libellé identifie un KID."""
    links: list[tuple[str, str]] = []
    for title, document_url in document_links(html, fund_url):
        normalized_title = normalized(title)
        if (
            "document" in normalized_title
            and "information" in normalized_title
            and ("cle" in normalized_title or "kid" in normalized_title)
        ):
            links.append((title, document_url))
    return links


def select_kid(links: list[tuple[str, str]]) -> tuple[str, str]:
    """Retourne l'unique KID du fonds, ou une erreur explicite."""
    unique_links = list(dict.fromkeys(links))
    if len(unique_links) == 1:
        return unique_links[0]
    if not unique_links:
        raise RuntimeError("No KID was found in this AG fund's documents.")
    raise RuntimeError(
        "Multiple KIDs were found for this AG fund:\n"
        + "\n".join(f"- {title}" for title, _ in unique_links)
    )


def pdf_filename(url: str) -> str:
    return pdf_filename_from_url(url, "kid-ag.pdf")


def download_fund(
    query: str, output_dir: Path, catalogue_url: str
) -> Path:
    """Trouve puis télécharge le KID public du fonds AG demandé."""
    session = create_session("AG-KID-Downloader/1.0")

    catalogue_response = session.get(catalogue_url, timeout=30)
    catalogue_response.raise_for_status()
    fund_title, fund_url = select_fund(
        catalogue_funds(catalogue_response.text, catalogue_url), query
    )

    fund_response = session.get(fund_url, timeout=30)
    fund_response.raise_for_status()
    document_title, document_url = select_kid(kid_links(fund_response.text, fund_url))

    destination = download_pdf(session, document_url, output_dir, pdf_filename(document_url))

    print(f"Fund: {fund_title}")
    print(f"Document: {document_title}")
    print(f"URL: {document_url}")
    print(f"Saved to: {destination.resolve()}")
    return destination


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        choices=tuple(CHANNEL_CATALOGUE_URLS),
        required=True,
        help="AG distribution channel whose MuMa catalogue should be searched.",
    )
    parser.add_argument(
        "--fund",
        help="Full name or distinctive part of the fund name.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("ag_downloads"),
        help="Destination directory (default: ag_downloads)",
    )
    arguments = parser.parse_args()
    if not arguments.fund:
        arguments.fund = CHANNEL_DEFAULT_FUNDS[arguments.channel]
    return arguments


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(
        arguments.fund,
        arguments.output_dir,
        CHANNEL_CATALOGUE_URLS[arguments.channel],
    )
