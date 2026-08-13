"""Modèles partagés par le traitement des documents et l'interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias, TypedDict

from entities import Insurer


Percentage: TypeAlias = int | float
PercentageValue: TypeAlias = Percentage | list[Percentage] | None
HighlightField: TypeAlias = Literal[
    "version_date",
    "holding_period",
    "reduction_in_yield",
    "management_fees",
    "transaction_fees",
]


class SourceHighlight(TypedDict):
    """Court passage du PDF permettant de vérifier une valeur extraite."""

    field: HighlightField
    page: int
    text: str


class DocumentExtraction(TypedDict):
    """Informations validées extraites d'un document financier."""

    version_date: str | None
    display_date: str | None
    confidence: str | None
    recommended_holding_period_years: Percentage | None
    reduction_in_yield_percent: Percentage | None
    management_fees_percent: PercentageValue
    transaction_fees_percent: PercentageValue
    source_highlights: list[SourceHighlight]


@dataclass(frozen=True)
class FundSelection:
    """Un fonds prêt à être téléchargé pour un assureur pris en charge."""

    key: str
    identifier: str
    insurer: Insurer
    fund: str
    document_url: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Résultat complet d'une extraction, succès comme échec."""

    identifier: str
    fund: str
    filename: str | None = None
    content: bytes | None = None
    extraction: DocumentExtraction | None = None
    highlighted_content: bytes | None = None
    highlighted_count: int = 0
    error: str | None = None
    highlight_error: str | None = None
