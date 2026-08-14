"""Recherche des passages source et annotation des PDF."""

from __future__ import annotations

from difflib import SequenceMatcher
import re

import pymupdf

from competition_analysis.document_extraction import format_number, format_version_date
from competition_analysis.download_common import compact_normalized
from competition_analysis.models import DocumentExtraction


def highlight_specs(
    extraction: DocumentExtraction | None,
) -> tuple[tuple[int, str, str], ...]:
    """Retourne les repères validés sous une forme sérialisable."""
    if not extraction:
        return ()
    return tuple(
        (highlight["page"], highlight["field"], highlight["text"])
        for highlight in extraction["source_highlights"]
    )


def _number_spellings(value: int | float) -> tuple[str, ...]:
    """Retourne les écritures décimales usuelles vues dans les DIC multilingues."""
    formatted = format_number(value)
    if formatted is None:
        return ()
    comma = formatted.replace(".", ",")
    return tuple(dict.fromkeys((formatted, comma)))


def highlight_fallbacks(
    extraction: DocumentExtraction | None,
) -> dict[str, tuple[str, ...]]:
    """Construit des recherches locales à partir des valeurs validées du modèle."""
    if not extraction:
        return {}

    fallbacks: dict[str, tuple[str, ...]] = {}
    date_texts = tuple(
        dict.fromkeys(
            text
            for text in (
                extraction["display_date"],
                format_version_date(extraction["version_date"]),
                extraction["version_date"],
            )
            if text
        )
    )
    if date_texts:
        fallbacks["version_date"] = date_texts

    holding_period = extraction["recommended_holding_period_years"]
    if holding_period is not None:
        fallbacks["holding_period"] = tuple(
            f"{number} {unit}"
            for number in _number_spellings(holding_period)
            for unit in ("ans", "an", "years", "year", "jaar")
        )

    for field, value in (
        ("reduction_in_yield", extraction["reduction_in_yield_percent"]),
        ("management_fees", extraction["management_fees_percent"]),
        ("transaction_fees", extraction["transaction_fees_percent"]),
    ):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            fallbacks[field] = tuple(
                variant
                for number in _number_spellings(value)
                for variant in (f"{number} %", f"{number}%")
            )
        elif isinstance(value, list) and len(value) == 2:
            left, right = _number_spellings(value[0]), _number_spellings(value[1])
            fallbacks[field] = tuple(
                variant
                for minimum in left
                for maximum in right
                for separator in ("–", "-", "à", "to")
                for variant in (
                    f"{minimum} {separator} {maximum} %",
                    f"{minimum} % {separator} {maximum} %",
                )
            )
    return fallbacks


def _numeric_fragments(text: str) -> list[str]:
    """Extrait les nombres sans confondre virgule et point décimaux."""
    return [value.replace(",", ".") for value in re.findall(r"\d+(?:[.,]\d+)?", text)]


def fuzzy_word_rectangles(page: pymupdf.Page, text: str) -> list[list[pymupdf.Rect]]:
    """Retrouve les rectangles d'un extrait malgré les sauts de ligne du PDF."""
    indexed_words = [
        (compact_normalized(str(word[4])), str(word[4]), pymupdf.Rect(word[:4]))
        for word in page.get_text("words", sort=True)
    ]
    indexed_words = [item for item in indexed_words if item[0]]
    target = [compact_normalized(word) for word in text.split()]
    target = [word for word in target if word]
    if not indexed_words or not target:
        return []

    page_tokens = [word for word, _, _ in indexed_words]
    exact_matches: list[list[pymupdf.Rect]] = []
    target_length = len(target)
    target_text = "".join(target)
    character_stream = "".join(page_tokens)
    token_starts: list[int] = []
    position = 0
    for token in page_tokens:
        token_starts.append(position)
        position += len(token)
    search_from = 0
    token_ends = {
        token_start + len(token)
        for token_start, token in zip(token_starts, page_tokens)
    }
    while (
        target_text
        and (match_start := character_stream.find(target_text, search_from)) >= 0
    ):
        match_end = match_start + len(target_text)
        if match_start not in token_starts or match_end not in token_ends:
            search_from = match_start + 1
            continue
        matching_words = [
            (raw_word, rectangle)
            for token_start, (token, raw_word, rectangle) in zip(
                token_starts, indexed_words
            )
            if token_start < match_end and token_start + len(token) > match_start
        ]
        if matching_words and (
            not _numeric_fragments(text)
            or _numeric_fragments(" ".join(word for word, _ in matching_words))
            == _numeric_fragments(text)
        ):
            exact_matches.append([rectangle for _, rectangle in matching_words])
        search_from = match_start + 1
    if exact_matches:
        return exact_matches

    best_score = 0.0
    best_rectangles: list[pymupdf.Rect] = []
    minimum_length, maximum_length = max(1, target_length - 2), min(
        len(page_tokens), target_length + 2
    )
    target_numbers = _numeric_fragments(text)
    for window_length in range(minimum_length, maximum_length + 1):
        for start in range(len(page_tokens) - window_length + 1):
            window = indexed_words[start : start + window_length]
            candidate_text = "".join(word for word, _, _ in window)
            candidate_numbers = _numeric_fragments(
                " ".join(raw_word for _, raw_word, _ in window)
            )
            if target_numbers and candidate_numbers != target_numbers:
                continue
            score = SequenceMatcher(None, target_text, candidate_text).ratio()
            if score > best_score:
                best_score = score
                best_rectangles = [rectangle for _, _, rectangle in window]
    return [best_rectangles] if best_score >= 0.82 else []


def source_rectangles(page: pymupdf.Page, field: str, text: str) -> list[pymupdf.Rect]:
    """Choisit la meilleure occurrence, à droite pour les valeurs du tableau."""
    exact_rectangles = list(page.search_for(text))
    if exact_rectangles:
        if field in {"holding_period", "reduction_in_yield"}:
            return [max(exact_rectangles, key=lambda rectangle: rectangle.x1)]
        return [exact_rectangles[0]]

    matches = fuzzy_word_rectangles(page, text)
    if not matches:
        return []
    if field in {"holding_period", "reduction_in_yield"}:
        return max(
            matches,
            key=lambda rectangles: max(rectangle.x1 for rectangle in rectangles),
        )
    return matches[0]


def create_highlighted_pdf(
    content: bytes,
    specs: tuple[tuple[int, str, str], ...],
    fallbacks: dict[str, tuple[str, ...]] | None = None,
) -> tuple[bytes, int]:
    """Surligne une fois chaque champ, avec repli sur sa valeur extraite."""
    highlighted_sources = 0
    fallbacks = fallbacks or {}
    with pymupdf.open(stream=content, filetype="pdf") as document:
        fields = tuple(
            dict.fromkeys([field for _, field, _ in specs] + list(fallbacks))
        )
        for field in fields:
            field_specs = [spec for spec in specs if spec[1] == field]
            match: tuple[pymupdf.Page, list[pymupdf.Rect]] | None = None
            for page_number, _, text in field_specs:
                if page_number > document.page_count:
                    continue
                page = document.load_page(page_number - 1)
                rectangles = source_rectangles(page, field, text)
                if rectangles:
                    match = (page, rectangles)
                    break
            if match is None and field in fallbacks:
                preferred_pages = [
                    page_number - 1
                    for page_number, _, _ in field_specs
                    if 0 < page_number <= document.page_count
                ]
                page_indexes = list(
                    dict.fromkeys(preferred_pages + list(range(document.page_count)))
                )
                for page_index in page_indexes:
                    page = document.load_page(page_index)
                    for text in fallbacks[field]:
                        rectangles = source_rectangles(page, field, text)
                        if rectangles:
                            match = (page, rectangles)
                            break
                    if match is not None:
                        break
            if match is None:
                continue
            page, rectangles = match
            for rectangle in rectangles:
                annotation = page.add_highlight_annot(rectangle)
                annotation.set_colors(stroke=(1, 0.84, 0))
                annotation.update()
            highlighted_sources += 1
        return document.tobytes(garbage=4, deflate=True), highlighted_sources
