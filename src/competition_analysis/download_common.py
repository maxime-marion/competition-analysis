"""Fonctions partagées par les téléchargeurs de documents d'assureurs."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
import re
import unicodedata
import warnings
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


DocumentLink = tuple[str, str]
LinkExtractor = Callable[[str, str], list[DocumentLink]]
LinkSelector = Callable[[list[DocumentLink], str], DocumentLink]
FilenameBuilder = Callable[[str, str], str]


class ApproximateMatchWarning(UserWarning):
    """Signale qu'un résultat exact a été préféré à des résultats partiels."""


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


def compact_normalized(text: str) -> str:
    """Normalise un libellé en ne conservant que ses caractères alphanumériques."""
    return "".join(character for character in normalized(text) if character.isalnum())


def select_unique_match(
    links: list[DocumentLink],
    query: str,
    *,
    missing_label: str,
    multiple_label: str,
) -> DocumentLink:
    """Retourne le meilleur titre correspondant à ``query`` après normalisation."""
    wanted = normalized(query)
    matches = [item for item in links if wanted in normalized(item[0])]

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"{missing_label} not found: {query}")

    exact_matches = [item for item in matches if normalized(item[0]) == wanted]
    if len(exact_matches) == 1:
        approximate_matches = [item for item in matches if item != exact_matches[0]]
        warnings.warn(
            "An exact fund-name match was selected, but the name also matches "
            f"{len(approximate_matches)} other document(s) approximately:\n"
            + "\n".join(
                f"- {title}: {url}" for title, url in approximate_matches
            ),
            ApproximateMatchWarning,
            stacklevel=2,
        )
        return exact_matches[0]

    raise RuntimeError(
        f"The name matches multiple {multiple_label}:\n"
        + "\n".join(f"- {title}: {url}" for title, url in matches)
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


def pdf_filename_from_title(title: str, fallback: str) -> str:
    """Construit un nom de PDF sûr depuis le libellé d'un document."""
    filename = sanitized_filename(title, fallback)
    return filename if filename.casefold().endswith(".pdf") else f"{filename}.pdf"


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


def download_selected_pdf(
    session: requests.Session,
    document_url: str,
    output_dir: Path,
    filename: str,
    *,
    details: Iterable[tuple[str, str]],
) -> Path:
    """Télécharge un PDF sélectionné et affiche un résumé homogène."""
    destination = download_pdf(session, document_url, output_dir, filename)
    for label, value in details:
        print(f"{label}: {value}")
    print(f"URL: {document_url}")
    print(f"Saved to: {destination.resolve()}")
    return destination


def download_from_html_catalogue(
    query: str,
    output_dir: Path,
    catalogue_url: str,
    *,
    user_agent: str,
    extract_links: LinkExtractor,
    select_link: LinkSelector,
    build_filename: FilenameBuilder,
    item_label: str = "Document",
) -> Path:
    """Exécute le flux commun des catalogues HTML à page unique."""
    session = create_session(user_agent)
    catalogue_response = session.get(catalogue_url, timeout=30)
    catalogue_response.raise_for_status()
    title, document_url = select_link(
        extract_links(catalogue_response.text, catalogue_url), query
    )
    return download_selected_pdf(
        session,
        document_url,
        output_dir,
        build_filename(title, document_url),
        details=((item_label, title),),
    )


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
