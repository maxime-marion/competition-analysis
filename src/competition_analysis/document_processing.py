"""Orchestration du traitement des documents financiers.

Les opérations spécialisées sont regroupées dans ``document_fetching``,
``document_extraction`` et ``pdf_highlighting``. Les imports ci-dessous restent
disponibles afin de préserver l'API publique historique du module.
"""

from __future__ import annotations

from collections.abc import Callable
import warnings

from openai import OpenAI

from competition_analysis.document_extraction import (
    DOCUMENT_EXTRACTION_MODEL,
    DOCUMENT_EXTRACTION_PROMPT,
    extract_document_information,
    extract_pdf_text,
    extract_version_date,
    format_number,
    format_percentage,
    format_version_date,
    parse_extraction_response,
    parse_version_date_response,
)
from competition_analysis.document_fetching import fetch_pdf
from competition_analysis.download_common import ApproximateMatchWarning
from competition_analysis.models import ExtractionResult, FundSelection
from competition_analysis.pdf_highlighting import (
    create_highlighted_pdf,
    fuzzy_word_rectangles,
    highlight_fallbacks,
    highlight_specs,
    source_rectangles,
)


ProgressReporter = Callable[[int], None]


def exception_message(error: Exception) -> str:
    """Retourne un message exploitable même pour une exception sans texte."""
    return str(error).strip() or error.__class__.__name__


def process_selection(
    selection: FundSelection,
    source_url: str,
    client: OpenAI,
    report_progress: ProgressReporter | None = None,
) -> ExtractionResult:
    """Traite une sélection complète sans dépendre de l'interface Streamlit."""
    report_progress = report_progress or (lambda _stage: None)
    report_progress(0)
    match_warning: str | None = None
    try:
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", ApproximateMatchWarning)
            filename, content = fetch_pdf(
                selection.insurer,
                selection.fund,
                source_url,
                selection.document_url,
                selection.document_variant,
            )
        match_warning = next(
            (
                str(caught.message)
                for caught in caught_warnings
                if issubclass(caught.category, ApproximateMatchWarning)
            ),
            None,
        )
        report_progress(1)
        extraction = extract_document_information(content, client)
    except Exception as error:
        return ExtractionResult(
            identifier=selection.identifier,
            fund=selection.fund,
            error=exception_message(error),
        )

    report_progress(2)
    highlighted_content: bytes | None = None
    highlighted_count = 0
    highlight_error: str | None = None
    specs = highlight_specs(extraction)
    fallbacks = highlight_fallbacks(extraction)
    if specs or fallbacks:
        try:
            highlighted_content, highlighted_count = create_highlighted_pdf(
                content, specs, fallbacks
            )
        except Exception as error:
            highlight_error = exception_message(error)

    return ExtractionResult(
        identifier=selection.identifier,
        fund=selection.fund,
        filename=filename,
        content=content,
        extraction=extraction,
        highlighted_content=highlighted_content,
        highlighted_count=highlighted_count,
        warning=match_warning,
        highlight_error=highlight_error,
    )
