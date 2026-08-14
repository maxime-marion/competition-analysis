"""Téléchargement des documents sélectionnés."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from competition_analysis.download_common import (
    create_session,
    download_pdf,
    pdf_filename_from_title,
    pdf_filename_from_url,
)
from competition_analysis.entities import Insurer


def fetch_pdf(
    insurer: Insurer,
    fund: str,
    source_url: str | None = None,
    document_url: str | None = None,
    document_variant: str | None = None,
) -> tuple[str, bytes]:
    """Télécharge le PDF dans un dossier temporaire puis retourne ses données."""
    if not document_url and insurer.downloader is None:
        raise ValueError(f"No downloader is configured for {insurer.label}.")
    with TemporaryDirectory(prefix="fund-document-") as temporary_directory:
        output_dir = Path(temporary_directory)
        if document_url:
            fallback = pdf_filename_from_title(fund, "document.pdf")
            filename = pdf_filename_from_url(document_url, fallback)
            path = download_pdf(
                create_session("competition-analysis/1.0"),
                document_url,
                output_dir,
                filename,
            )
        else:
            assert insurer.downloader is not None
            downloader_arguments = (fund, output_dir, source_url or insurer.source_url)
            if document_variant:
                path = insurer.downloader(
                    *downloader_arguments, document_variant=document_variant
                )
            else:
                path = insurer.downloader(*downloader_arguments)
        return path.name, path.read_bytes()
