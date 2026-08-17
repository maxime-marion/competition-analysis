"""Lecture et validation des sélections de fonds importées."""

from __future__ import annotations

import csv
from io import StringIO
from urllib.parse import urlparse

from competition_analysis.download_common import compact_normalized
from competition_analysis.entities import BROKER_ENTITIES, Insurer
from competition_analysis.models import FundSelection


CSV_ENTITY_HEADERS = ("entity", "entite", "assureur")
CSV_FUND_HEADERS = (
    "fund",
    "fundname",
    "nameoffund",
    "nameofthefund",
    "nomdufonds",
)
CSV_DOCUMENT_URL_HEADERS = (
    "documenturl",
    "directurl",
    "documentlink",
    "url",
)
CSV_COMPARISON_AG_FUND_HEADERS = (
    "agfund",
    "agreferencefund",
    "comparisonagfund",
)


def valid_source_url(value: str) -> bool:
    """Vérifie qu'une URL HTTP peut être utilisée comme source de document."""
    parsed_url = urlparse(value)
    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


def parse_fund_csv(
    content: bytes, entities: dict[str, Insurer] | None = None
) -> tuple[list[FundSelection], list[str]]:
    """Lit le CSV importé et valide ses entités avant toute extraction."""
    entities = BROKER_ENTITIES if entities is None else entities
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["The CSV file must be UTF-8 encoded."]

    try:
        dialect = csv.Sniffer().sniff(text[:4_096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return [], ["The CSV file must contain a header row."]

    headers = {
        compact_normalized(header): header
        for header in reader.fieldnames
        if header is not None
    }
    entity_header = next(
        (headers[header] for header in CSV_ENTITY_HEADERS if header in headers), None
    )
    fund_header = next(
        (headers[header] for header in CSV_FUND_HEADERS if header in headers), None
    )
    document_url_header = next(
        (headers[header] for header in CSV_DOCUMENT_URL_HEADERS if header in headers),
        None,
    )
    comparison_ag_fund_header = next(
        (
            headers[header]
            for header in CSV_COMPARISON_AG_FUND_HEADERS
            if header in headers
        ),
        None,
    )
    if not entity_header or not fund_header:
        return [], [
            "The CSV file must contain the “entity” and “fund name” columns "
            "(“name of the fund” is also accepted)."
        ]

    insurers_by_name = {
        compact_normalized(name): (identifier, insurer)
        for identifier, insurer in entities.items()
        for name in (identifier, insurer.label)
    }
    selections: list[FundSelection] = []
    errors: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        entity = (row.get(entity_header) or "").strip()
        fund = (row.get(fund_header) or "").strip()
        document_url = (
            (row.get(document_url_header) or "").strip()
            if document_url_header
            else ""
        )
        comparison_ag_fund = (
            (row.get(comparison_ag_fund_header) or "").strip()
            if comparison_ag_fund_header
            else ""
        )
        if not entity and not fund and not document_url and not comparison_ag_fund:
            continue
        if not entity or not fund:
            errors.append(f"Row {row_number}: entity and fund name are required.")
            continue
        if document_url and not valid_source_url(document_url):
            errors.append(
                f"Row {row_number}: document URL must start with http:// or https://."
            )
            continue
        match = insurers_by_name.get(compact_normalized(entity))
        if not match:
            supported = ", ".join(insurer.label for insurer in entities.values())
            errors.append(f"Row {row_number}: unknown entity “{entity}” ({supported}).")
            continue
        identifier, insurer = match
        selections.append(
            FundSelection(
                f"{identifier}-{row_number}",
                identifier,
                insurer,
                fund,
                document_url or None,
                comparison_ag_fund=comparison_ag_fund or None,
            )
        )

    if not selections and not errors:
        errors.append("The CSV file does not contain any funds.")
    selections.sort(
        key=lambda selection: (
            selection.insurer.label.casefold(),
            selection.fund.casefold(),
        )
    )
    return selections, errors
