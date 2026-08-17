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
    missing_extraction_fields,
    parse_extraction_response,
    parse_version_date_response,
)
from competition_analysis.document_fetching import fetch_pdf
from competition_analysis.download_common import ApproximateMatchWarning
from competition_analysis.models import ExtractionResult, FundSelection, RetrievalResult
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


def retrieve_selection(selection: FundSelection, source_url: str) -> RetrievalResult:
    """Télécharge un document sans attendre l'extraction des autres fonds."""
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
        return RetrievalResult(selection, filename, content, warning=match_warning)
    except Exception as error:
        return RetrievalResult(selection, error=exception_message(error))


def extract_retrieved_document(
    retrieved: RetrievalResult,
    client: OpenAI,
    report_progress: ProgressReporter | None = None,
) -> ExtractionResult:
    """Extrait et surligne un document déjà récupéré."""
    selection = retrieved.selection
    report_progress = report_progress or (lambda _stage: None)
    report_progress(0)
    if retrieved.error or retrieved.content is None:
        return ExtractionResult(
            identifier=selection.identifier,
            fund=selection.fund,
            comparison_ag_fund=selection.comparison_ag_fund,
            filename=retrieved.filename,
            content=retrieved.content,
            error=retrieved.error or "The document could not be retrieved.",
            warning=retrieved.warning,
        )

    content = retrieved.content
    try:
        extraction = extract_document_information(content, client)
        extraction_attempts = 1
        if missing_extraction_fields(extraction):
            # Retry this fund immediately, before the caller proceeds to another one.
            extraction = extract_document_information(content, client)
            extraction_attempts = 2
    except Exception as error:
        return ExtractionResult(
            identifier=selection.identifier,
            fund=selection.fund,
            comparison_ag_fund=selection.comparison_ag_fund,
            filename=retrieved.filename,
            content=content,
            error=exception_message(error),
            warning=retrieved.warning,
        )

    report_progress(1)
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
        comparison_ag_fund=selection.comparison_ag_fund,
        filename=retrieved.filename,
        content=content,
        extraction=extraction,
        highlighted_content=highlighted_content,
        highlighted_count=highlighted_count,
        extraction_attempts=extraction_attempts,
        warning=retrieved.warning,
        highlight_error=highlight_error,
    )


def process_selection(
    selection: FundSelection,
    source_url: str,
    client: OpenAI,
    report_progress: ProgressReporter | None = None,
) -> ExtractionResult:
    """Compatibilité: récupère, extrait et surligne une seule sélection."""
    report_progress = report_progress or (lambda _stage: None)
    report_progress(0)
    retrieved = retrieve_selection(selection, source_url)
    if retrieved.error:
        return extract_retrieved_document(retrieved, client)
    report_progress(1)
    return extract_retrieved_document(
        retrieved, client, lambda stage: report_progress(stage + 1)
    )
