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
SECTION_TEXT = "Fonds branche 23 - Profilife"
DEFAULT_FUND = "Profilife - Athora DNCA Invest Beyd Semperosa A"


def normalized(text: str) -> str:
    """Normalise un libellé pour rendre la recherche tolérante aux accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(
        "".join(character for character in decomposed if not unicodedata.combining(character))
        .casefold()
        .split()
    )


def section_links(html: str, page_url: str = PAGE_URL) -> list[tuple[str, str]]:
    """Retourne les documents de l'accordéon Fonds branche 23 - Profilife."""
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (
            tag
            for tag in soup.find_all("h3")
            if normalized(tag.get_text(" ", strip=True)) == normalized(SECTION_TEXT)
        ),
        None,
    )
    if heading is None:
        raise RuntimeError(f"La section « {SECTION_TEXT} » est introuvable.")

    panel = heading.find_parent("div", class_="panel")
    if panel is None:
        raise RuntimeError("Le contenu de l'accordéon Profilife est introuvable.")

    links: list[tuple[str, str]] = []
    for row in panel.select(".views-field-name"):
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
    title, document_url = select_fund(section_links(page_response.text, page_url), query)

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
