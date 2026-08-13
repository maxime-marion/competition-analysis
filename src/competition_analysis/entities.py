"""Configuration des entités et de leurs téléchargeurs de documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from competition_analysis.downloaders.ag import (
    BANK_CATALOGUE_URL as AG_BANK_CATALOGUE_URL,
    BANK_DEFAULT_FUND as AG_BANK_DEFAULT_FUND,
    BROKER_CATALOGUE_URL as AG_BROKER_CATALOGUE_URL,
    DEFAULT_FUND as AG_DEFAULT_FUND,
    download_fund as download_ag_fund,
)
from competition_analysis.downloaders.allianz import (
    DEFAULT_DOCUMENT as ALLIANZ_DEFAULT_DOCUMENT,
    PAGE_URL as ALLIANZ_PAGE_URL,
    download_document as download_allianz_document,
)
from competition_analysis.downloaders.athora import (
    DEFAULT_FUND as ATHORA_DEFAULT_FUND,
    PAGE_URL as ATHORA_PAGE_URL,
    download_fund as download_athora_fund,
)
from competition_analysis.downloaders.baloise import (
    DEFAULT_FUND as BALOISE_DEFAULT_FUND,
    PAGE_URL as BALOISE_PAGE_URL,
    download_fund as download_baloise_fund,
)
from competition_analysis.downloaders.belfius import (
    DEFAULT_FUND as BELFIUS_DEFAULT_FUND,
    PAGE_URL as BELFIUS_PAGE_URL,
    download_fund as download_belfius_fund,
)
from competition_analysis.downloaders.kbc import (
    DEFAULT_FUND as KBC_DEFAULT_FUND,
    PAGE_URL as KBC_PAGE_URL,
    download_fund as download_kbc_fund,
)
from competition_analysis.downloaders.nn import (
    DEFAULT_DOCUMENT as NN_DEFAULT_DOCUMENT,
    PAGE_URL as NN_PAGE_URL,
    download_document as download_nn_document,
)
from competition_analysis.downloaders.vivium import (
    DEFAULT_FUND as VIVIUM_DEFAULT_FUND,
    PAGE_URL as VIVIUM_PAGE_URL,
    download_fund as download_vivium_fund,
)


Downloader = Callable[[str, Path, str], Path]


@dataclass(frozen=True)
class Insurer:
    label: str
    default_fund: str
    source_url: str
    downloader: Downloader | None = None


BROKER_ENTITIES = {
    "allianz": Insurer(
        label="Allianz",
        default_fund=ALLIANZ_DEFAULT_DOCUMENT,
        source_url=ALLIANZ_PAGE_URL,
        downloader=download_allianz_document,
    ),
    "ag": Insurer(
        label="AG",
        default_fund=AG_DEFAULT_FUND,
        source_url=AG_BROKER_CATALOGUE_URL,
        downloader=download_ag_fund,
    ),
    "vivium": Insurer(
        label="Vivium",
        default_fund=VIVIUM_DEFAULT_FUND,
        source_url=VIVIUM_PAGE_URL,
        downloader=download_vivium_fund,
    ),
    "athora": Insurer(
        label="Athora",
        default_fund=ATHORA_DEFAULT_FUND,
        source_url=ATHORA_PAGE_URL,
        downloader=download_athora_fund,
    ),
    "baloise": Insurer(
        label="Baloise",
        default_fund=BALOISE_DEFAULT_FUND,
        source_url=BALOISE_PAGE_URL,
        downloader=download_baloise_fund,
    ),
    "nn": Insurer(
        label="NN",
        default_fund=NN_DEFAULT_DOCUMENT,
        source_url=NN_PAGE_URL,
        downloader=download_nn_document,
    ),
}

BANK_ENTITIES = {
    "ag": Insurer(
        label="AG",
        default_fund=AG_BANK_DEFAULT_FUND,
        source_url=AG_BANK_CATALOGUE_URL,
        downloader=download_ag_fund,
    ),
    "belfius": Insurer(
        label="Belfius",
        default_fund=BELFIUS_DEFAULT_FUND,
        source_url=BELFIUS_PAGE_URL,
        downloader=download_belfius_fund,
    ),
    "kbc": Insurer(
        label="KBC",
        default_fund=KBC_DEFAULT_FUND,
        source_url=KBC_PAGE_URL,
        downloader=download_kbc_fund,
    ),
}
