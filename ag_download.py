#!/usr/bin/env python3
"""Télécharge le KID d'un fonds AG depuis le catalogue MuMa public."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


CATALOGUE_URL = "https://ag.ag-muma.be/fr/allfunds"
DEFAULT_FUND = "AG Life Optitrack Equities"


def normalized(text: str) -> str:
    """Normalise un libellé pour une recherche tolérante aux accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(
        "".join(character for character in decomposed if not unicodedata.combining(character))
        .casefold()
        .split()
    )


def catalogue_funds(
    html: str, catalogue_url: str = CATALOGUE_URL
) -> list[tuple[str, str]]:
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
        raise RuntimeError("Aucun fonds n'a été trouvé dans le catalogue AG.")
    return list(funds.values())


def select_fund(funds: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un fonds par nom exact ou partie distinctive du nom."""
    wanted = normalized(query)
    exact = [item for item in funds if normalized(item[0]) == wanted]
    matches = exact or [item for item in funds if wanted in normalized(item[0])]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"Fonds AG introuvable : {query}")
    raise RuntimeError(
        "Le nom correspond à plusieurs fonds AG :\n"
        + "\n".join(f"- {title}" for title, _ in matches)
    )


def kid_links(html: str, fund_url: str) -> list[tuple[str, str]]:
    """Retourne les liens PDF dont le libellé identifie un KID."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        title = link.get_text(" ", strip=True)
        document_url = urljoin(fund_url, str(link["href"]))
        normalized_title = normalized(title)
        if (
            ".pdf" in urlparse(document_url).path.casefold()
            and "document" in normalized_title
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
        raise RuntimeError("Aucun KID n'a été trouvé dans les documents de ce fonds AG.")
    raise RuntimeError(
        "Plusieurs KID ont été trouvés pour ce fonds AG :\n"
        + "\n".join(f"- {title}" for title, _ in unique_links)
    )


def pdf_filename(url: str) -> str:
    candidate = unquote(Path(urlparse(url).path).name) or "kid-ag.pdf"
    return re.sub(r"[^A-Za-z0-9À-ÿ._ -]+", "_", candidate)


def download_fund(
    query: str, output_dir: Path, catalogue_url: str = CATALOGUE_URL
) -> Path:
    """Trouve puis télécharge le KID public du fonds AG demandé."""
    session = requests.Session()
    session.headers["User-Agent"] = "AG-KID-Downloader/1.0"

    catalogue_response = session.get(catalogue_url, timeout=30)
    catalogue_response.raise_for_status()
    fund_title, fund_url = select_fund(
        catalogue_funds(catalogue_response.text, catalogue_url), query
    )

    fund_response = session.get(fund_url, timeout=30)
    fund_response.raise_for_status()
    document_title, document_url = select_kid(kid_links(fund_response.text, fund_url))

    document_response = session.get(document_url, timeout=60)
    document_response.raise_for_status()
    if not document_response.content.startswith(b"%PDF"):
        raise RuntimeError("Le fichier reçu n'est pas un PDF valide.")

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / pdf_filename(document_url)
    destination.write_bytes(document_response.content)

    print(f"Fonds : {fund_title}")
    print(f"Document : {document_title}")
    print(f"URL : {document_url}")
    print(f"Enregistré dans : {destination.resolve()}")
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fund",
        default=DEFAULT_FUND,
        help=f"Nom complet ou partie du nom du fonds (défaut : {DEFAULT_FUND})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("ag_downloads"),
        help="Répertoire de destination (défaut : ag_downloads)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
