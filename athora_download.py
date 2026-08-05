#!/usr/bin/env python3
"""Télécharge un document spécifique d'un fonds Profilife chez Athora."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


PAGE_URL = "https://www.athora.com/be/fr/bibliotheque/documents"
DEFAULT_FUND = "Profilife - Athora DNCA Invest Beyd Semperosa A"


def normalized(text: str) -> str:
    """Normalise un libellé pour rendre la recherche tolérante aux accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(
        "".join(character for character in decomposed if not unicodedata.combining(character))
        .casefold()
        .split()
    )


def fund_links(html: str, page_url: str = PAGE_URL) -> list[tuple[str, str]]:
    """Retourne tous les liens PDF de fonds affichés sur la page Athora.

    La sélection du fonds se fait ensuite sur son nom complet, sans dépendre du
    libellé ou de la structure d'une section de la page.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for row in soup.select(".views-field-name"):
        document_link = row.find("a", href=True)
        if not isinstance(document_link, Tag):
            continue
        document_url = urljoin(page_url, str(document_link["href"]))
        if ".pdf" not in urlparse(document_url).path.casefold():
            continue
        links.append((row.get_text(" ", strip=True), document_url))
    return links


def select_fund(links: list[tuple[str, str]], query: str) -> tuple[str, str]:
    """Sélectionne un fonds par libellé exact ou partiel."""
    wanted = normalized(query)
    exact = [item for item in links if normalized(item[0]) == wanted]
    matches = exact or [item for item in links if wanted in normalized(item[0])]

    if len(matches) == 1:
        return matches[0]
    if not matches:
        available = "\n".join(f"- {title}" for title, _ in links)
        raise RuntimeError(f"Fonds introuvable. Fonds disponibles :\n{available}")
    raise RuntimeError(
        "Le nom correspond à plusieurs fonds :\n"
        + "\n".join(f"- {title}" for title, _ in matches)
    )


def pdf_filename(url: str) -> str:
    candidate = unquote(Path(urlparse(url).path).name) or "document-athora.pdf"
    return re.sub(r"[^A-Za-z0-9À-ÿ._ -]+", "_", candidate)


def download_fund(query: str, output_dir: Path, page_url: str = PAGE_URL) -> Path:
    session = requests.Session()
    session.headers["User-Agent"] = "Athora-DIS-Downloader/1.0"

    page_response = session.get(page_url, timeout=30)
    page_response.raise_for_status()
    title, document_url = select_fund(fund_links(page_response.text, page_url), query)

    document_response = session.get(document_url, timeout=60)
    document_response.raise_for_status()
    if not document_response.content.startswith(b"%PDF"):
        raise RuntimeError("Le fichier reçu n'est pas un PDF valide.")

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / pdf_filename(document_url)
    destination.write_bytes(document_response.content)

    print(f"Document : {title}")
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
        default=Path("athora_downloads"),
        help="Répertoire de destination (défaut : athora_downloads)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    download_fund(arguments.fund, arguments.output_dir)
