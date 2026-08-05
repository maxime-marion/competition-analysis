"""Fonctions partagées par les téléchargeurs de documents d'assureurs."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


DocumentLink = tuple[str, str]


def document_links(
    html: str,
    page_url: str,
    *,
    selector: str = "a[href]",
    link_selector: str | None = None,
    require_pdf: bool = True,
) -> list[DocumentLink]:
    """Retourne les liens de documents et leurs libellés depuis le HTML fourni.

    ``selector`` limite éventuellement la zone de recherche et ``link_selector``
    désigne le lien à utiliser à l'intérieur de chaque élément sélectionné. Cela
    permet de conserver un libellé porté par un conteneur plutôt que par son lien.
    Les documents non terminés par ``.pdf`` sont acceptés avec
    ``require_pdf=False``.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: list[DocumentLink] = []
    for element in soup.select(selector):
        link = element if link_selector is None else element.select_one(link_selector)
        if not isinstance(link, Tag) or not link.has_attr("href"):
            continue
        document_url = urljoin(page_url, str(link["href"]))
        if require_pdf and ".pdf" not in urlparse(document_url).path.casefold():
            continue
        links.append((element.get_text(" ", strip=True), document_url))
    return list(dict.fromkeys(links))


def normalized(text: str) -> str:
    """Normalise un libellé pour une recherche tolérante aux accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(
        "".join(character for character in decomposed if not unicodedata.combining(character))
        .casefold()
        .split()
    )


def select_unique_match(
    links: list[DocumentLink],
    query: str,
    *,
    missing_label: str,
    multiple_label: str,
) -> DocumentLink:
    """Retourne le résultat exact ou partiel unique pour ``query``."""
    wanted = normalized(query)
    exact = [item for item in links if normalized(item[0]) == wanted]
    matches = exact or [item for item in links if wanted in normalized(item[0])]

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"{missing_label} not found: {query}")
    raise RuntimeError(
        f"The name matches multiple {multiple_label}:\n"
        + "\n".join(f"- {title}" for title, _ in matches)
    )


def sanitized_filename(value: str, fallback: str) -> str:
    """Construit un nom de fichier local sûr, en conservant les accents."""
    filename = re.sub(r"[^A-Za-z0-9À-ÿ._ -]+", "_", value).strip(" ._")
    return filename or fallback


def pdf_filename_from_url(url: str, fallback: str) -> str:
    """Extrait et nettoie le dernier nom de PDF présent dans une URL."""
    parts = [unquote(part) for part in urlparse(url).path.split("/") if part]
    candidate = next(
        (part for part in reversed(parts) if part.casefold().endswith(".pdf")),
        fallback,
    )
    return sanitized_filename(candidate, fallback)


def create_session(user_agent: str) -> requests.Session:
    """Crée une session HTTP identifiée de façon cohérente."""
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    return session


def download_pdf(
    session: requests.Session,
    document_url: str,
    output_dir: Path,
    filename: str,
) -> Path:
    """Télécharge, valide puis enregistre un PDF dans ``output_dir``."""
    response = session.get(document_url, timeout=60)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError("The downloaded file is not a valid PDF.")

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / filename
    destination.write_bytes(response.content)
    return destination


def parse_download_args(
    description: str | None,
    *,
    item_option: str,
    item_label: str,
    default_item: str,
    default_output_dir: Path,
) -> argparse.Namespace:
    """Construit l'interface en ligne de commande commune aux téléchargeurs."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        f"--{item_option}",
        default=default_item,
        help=(
            f"Full name or part of the {item_label} name "
            f"(default: {default_item})"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Destination directory (default: {default_output_dir})",
    )
    return parser.parse_args()
