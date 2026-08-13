"""Composants Streamlit de l'analyse concurrentielle."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

from openai import OpenAI
import streamlit as st

from competition_analysis.document_processing import (
    format_number,
    format_percentage,
    format_version_date,
    process_selection,
)
from competition_analysis.entities import BROKER_ENTITIES, Insurer
from competition_analysis.models import ExtractionResult, FundSelection
from competition_analysis.selection_import import parse_fund_csv, valid_source_url


def channel_state_key(channel_key: str, name: str) -> str:
    """Construit une clé d'état Streamlit isolée pour un canal d'analyse."""
    return f"{channel_key}-{name}"


def selections_from_fund_fields(
    channel_key: str, entities: dict[str, Insurer]
) -> list[FundSelection]:
    """Construit la sélection à partir des champs de fonds de l'interface."""
    selections: list[FundSelection] = []
    for identifier, insurer in sorted(
        entities.items(), key=lambda item: item[1].label.casefold()
    ):
        field_count = max(
            1,
            st.session_state.get(
                channel_state_key(channel_key, f"fund-count-{identifier}"), 1
            ),
        )
        for index in range(field_count):
            fund = st.session_state.get(
                channel_state_key(channel_key, f"fund-{identifier}-{index}"), ""
            ).strip()
            if fund:
                document_url = st.session_state.get(
                    channel_state_key(
                        channel_key, f"document-url-{identifier}-{index}"
                    ),
                    "",
                ).strip()
                selections.append(
                    FundSelection(
                        f"{identifier}-{index}",
                        identifier,
                        insurer,
                        fund,
                        document_url or None,
                    )
                )
    return selections


def clear_channel_results(channel_key: str) -> None:
    """Évite d'afficher des résultats qui ne correspondent plus aux champs."""
    st.session_state.pop(channel_state_key(channel_key, "extraction-results"), None)


def initialize_fund_fields(
    channel_key: str, entities: dict[str, Insurer]
) -> None:
    """Préremplit une seule sélection par entité à la première ouverture."""
    initialized_key = channel_state_key(channel_key, "fund-fields-initialized")
    if st.session_state.get(initialized_key):
        return
    for identifier, insurer in entities.items():
        st.session_state[channel_state_key(channel_key, f"fund-count-{identifier}")] = 1
        st.session_state[
            channel_state_key(channel_key, f"fund-{identifier}-0")
        ] = insurer.default_fund
        st.session_state[
            channel_state_key(channel_key, f"document-url-{identifier}-0")
        ] = ""
    st.session_state[initialized_key] = True


def configured_openai_key() -> str | None:
    """Lit une clé des secrets Streamlit ou de l'environnement."""
    try:
        secret_key = st.secrets.get("OPENAI_API_KEY", "").strip()
    except FileNotFoundError:
        secret_key = ""
    return secret_key or os.getenv("OPENAI_API_KEY")


def render_source_url_fields(
    channel_key: str, entities: dict[str, Insurer]
) -> tuple[dict[str, str], list[str]]:
    """Affiche et valide les URL des catalogues des assureurs."""
    st.caption("Source links used to retrieve documents. You can edit them before extraction.")
    source_urls: dict[str, str] = {}
    entity_column, url_column = st.columns([1, 5])
    entity_column.caption("Entity")
    url_column.caption("Source URL")
    for identifier, insurer in sorted(
        entities.items(), key=lambda item: item[1].label.casefold()
    ):
        entity_column, url_column = st.columns([1, 5])
        entity_column.write(insurer.label)
        source_urls[identifier] = url_column.text_input(
            f"{insurer.label} source URL",
            value=insurer.source_url,
            key=channel_state_key(channel_key, f"source-url-{identifier}"),
            on_change=clear_channel_results,
            args=(channel_key,),
            label_visibility="collapsed",
        ).strip()
    source_url_errors = [
        f"The {entities[identifier].label} source URL must start with http:// or https://."
        for identifier, source_url in source_urls.items()
        if not valid_source_url(source_url)
    ]
    for error in source_url_errors:
        st.error(error)
    return source_urls, source_url_errors


def sync_uploaded_csv(
    channel_key: str, entities: dict[str, Insurer]
) -> list[str]:
    """Valide un CSV et synchronise son contenu avec les champs de fonds."""
    uploaded_csv = st.file_uploader(
        "Import fund names (CSV)",
        type="csv",
        key=channel_state_key(channel_key, "csv-upload"),
        help=(
            "Required columns: entity and fund name. The optional document URL column "
            "bypasses the search by fund name. Supported entities in this channel: "
            + ", ".join(entity.label for entity in entities.values())
            + "."
        ),
    )
    imported_signature_key = channel_state_key(channel_key, "imported-csv-signature")
    if uploaded_csv is None:
        st.session_state.pop(imported_signature_key, None)
        return []

    csv_content = uploaded_csv.getvalue()
    imported_selections, csv_errors = parse_fund_csv(csv_content, entities)
    for error in csv_errors:
        st.error(error)
    if csv_errors:
        return csv_errors

    csv_signature = sha256(csv_content).hexdigest()
    if st.session_state.get(imported_signature_key) == csv_signature:
        return []

    imported_funds: dict[str, list[tuple[str, str]]] = {
        identifier: [] for identifier in entities
    }
    for selection in imported_selections:
        imported_funds[selection.identifier].append(
            (selection.fund, selection.document_url or "")
        )
    for identifier, funds in imported_funds.items():
        fund_count_key = channel_state_key(channel_key, f"fund-count-{identifier}")
        previous_count = st.session_state.get(fund_count_key, 1)
        field_count = max(1, len(funds))
        for index in range(max(previous_count, field_count)):
            st.session_state[
                channel_state_key(channel_key, f"fund-{identifier}-{index}")
            ] = funds[index][0] if index < len(funds) else ""
            st.session_state[
                channel_state_key(channel_key, f"document-url-{identifier}-{index}")
            ] = funds[index][1] if index < len(funds) else ""
        st.session_state[fund_count_key] = field_count

    st.session_state[imported_signature_key] = csv_signature
    clear_channel_results(channel_key)
    st.success(
        f"{len(imported_selections)} fund"
        f"{'s' if len(imported_selections) > 1 else ''} imported into the fields below."
    )
    return []


def render_fund_fields(
    channel_key: str, entities: dict[str, Insurer]
) -> tuple[list[FundSelection], list[str]]:
    """Affiche les champs dynamiques et retourne les fonds renseignés."""
    st.caption(
        "Enter fund names and, optionally, a direct document URL. When provided, the "
        "direct URL is used instead of searching the catalogue by fund name."
    )
    insurers = sorted(entities.items(), key=lambda item: item[1].label.casefold())
    fund_columns = st.columns(len(insurers))
    for column, (identifier, insurer) in zip(fund_columns, insurers):
        with column:
            st.subheader(insurer.label)
            field_count_key = channel_state_key(
                channel_key, f"fund-count-{identifier}"
            )
            field_count = max(1, st.session_state.get(field_count_key, 1))
            for field_index in range(field_count):
                st.text_input(
                    f"{insurer.label} — Fund name {field_index + 1}",
                    key=channel_state_key(
                        channel_key, f"fund-{identifier}-{field_index}"
                    ),
                    placeholder="Enter a fund name",
                    on_change=clear_channel_results,
                    args=(channel_key,),
                    label_visibility="collapsed",
                )
                st.text_input(
                    f"{insurer.label} — Direct document URL {field_index + 1}",
                    key=channel_state_key(
                        channel_key, f"document-url-{identifier}-{field_index}"
                    ),
                    placeholder="Direct document URL (optional)",
                    on_change=clear_channel_results,
                    args=(channel_key,),
                    label_visibility="collapsed",
                )
            if st.button(
                f"Add {insurer.label} fund",
                key=channel_state_key(channel_key, f"add-fund-{identifier}"),
                use_container_width=True,
            ):
                st.session_state[field_count_key] = field_count + 1
                clear_channel_results(channel_key)
                st.rerun()
    selections = selections_from_fund_fields(channel_key, entities)
    document_url_errors = [
        f"The direct document URL for {selection.insurer.label} — {selection.fund} "
        "must start with http:// or https://."
        for selection in selections
        if selection.document_url and not valid_source_url(selection.document_url)
    ]
    for error in document_url_errors:
        st.error(error)
    return selections, document_url_errors


def extract_selections(
    selections: list[FundSelection], source_urls: dict[str, str], api_key: str
) -> dict[str, ExtractionResult]:
    """Traite toutes les sélections et traduit leur progression pour Streamlit."""
    results: dict[str, ExtractionResult] = {}
    progress = st.progress(0, text="Preparing extraction…")
    client = OpenAI(api_key=api_key)
    stages_per_selection = 3
    total_stages = len(selections) * stages_per_selection
    stage_labels = (
        "downloading document…",
        "extracting information…",
        "highlighting PDF…",
    )

    for index, selection in enumerate(selections):
        stage_start = index * stages_per_selection

        def report_progress(stage: int) -> None:
            progress.progress(
                (stage_start + stage) / total_stages,
                text=f"{selection.insurer.label}: {stage_labels[stage]}",
            )

        results[selection.key] = process_selection(
            selection,
            source_urls[selection.identifier],
            client,
            report_progress,
        )

    progress.progress(1.0, text="Download, extraction, and highlighting complete.")
    return results


def result_row(
    result: ExtractionResult, entities: dict[str, Insurer] | None = None
) -> dict[str, str]:
    """Convertit un résultat structuré en ligne de tableau."""
    entities = BROKER_ENTITIES if entities is None else entities
    row = {
        "Entity": entities[result.identifier].label,
        "Fund": result.fund,
        "Version date": "—",
        "Recommended holding period": "—",
        "Reduction in yield": "—",
        "Management fees": "—",
        "Transaction fees": "—",
        "Confidence": "—",
    }
    if result.error:
        row["Status"] = "Failed — details below"
        return row

    extraction = result.extraction
    if extraction is None:
        row["Status"] = "Failed — no extraction returned"
        return row
    holding_period = extraction["recommended_holding_period_years"]
    reduction_in_yield = extraction["reduction_in_yield_percent"]
    row.update(
        {
            "Version date": (
                format_version_date(extraction["version_date"]) or "No date found"
            ),
            "Recommended holding period": (
                f"{format_number(holding_period)} years"
                if holding_period is not None
                else "No period found"
            ),
            "Reduction in yield": (
                f"{format_number(reduction_in_yield)} %"
                if reduction_in_yield is not None
                else "No reduction found"
            ),
            "Management fees": (
                format_percentage(extraction["management_fees_percent"])
                or "No management fees found"
            ),
            "Transaction fees": (
                format_percentage(extraction["transaction_fees_percent"])
                or "No transaction fees found"
            ),
            "Confidence": extraction["confidence"] or "not specified",
            "Status": (
                f"Information extracted; highlighting unavailable: {result.highlight_error}"
                if result.highlight_error
                else "Complete"
            ),
        }
    )
    return row


def render_analysis_results(
    channel_key: str,
    entities: dict[str, Insurer],
    results: dict[str, ExtractionResult] | None,
) -> None:
    """Affiche le tableau et les téléchargements des extractions."""
    if not results:
        st.info("No bulk extraction has been run yet.")
        return

    st.dataframe(
        [result_row(result, entities) for result in results.values()],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Entity": st.column_config.TextColumn("Entity", width="small"),
            "Fund": st.column_config.TextColumn("Fund", width="medium"),
            "Version date": st.column_config.TextColumn("Version date", width="medium"),
            "Recommended holding period": st.column_config.TextColumn(
                "Recommended holding period", width="medium"
            ),
            "Reduction in yield": st.column_config.TextColumn(
                "Reduction in yield", width="medium"
            ),
            "Management fees": st.column_config.TextColumn(
                "Management fees", width="medium"
            ),
            "Transaction fees": st.column_config.TextColumn(
                "Transaction fees", width="medium"
            ),
            "Confidence": st.column_config.TextColumn("Confidence", width="small"),
            "Status": st.column_config.TextColumn("Status", width="medium"),
        },
    )
    for result in results.values():
        if result.error:
            insurer = entities[result.identifier]
            st.error(f"{insurer.label} — {result.fund} : {result.error}")

    original_column, highlighted_column = st.columns(2)
    original_column.caption("Original document")
    highlighted_column.caption("Highlighted document")

    for selection_key, result in results.items():
        insurer = entities[result.identifier]
        original_column, highlighted_column = st.columns(2)
        if not result.filename or result.content is None:
            original_column.caption("Unavailable")
            highlighted_column.caption("Unavailable")
            continue

        original_column.download_button(
            f"Original PDF — {insurer.label}: {result.fund}",
            data=result.content,
            file_name=result.filename,
            mime="application/pdf",
            key=channel_state_key(channel_key, f"download-original-{selection_key}"),
            use_container_width=True,
        )
        if result.highlighted_content is None or not result.highlighted_count:
            highlighted_column.caption("Unavailable")
            continue
        highlighted_column.download_button(
            f"Highlighted PDF — {insurer.label}: {result.fund}",
            data=result.highlighted_content,
            file_name=f"{Path(result.filename).stem}-highlighted.pdf",
            mime="application/pdf",
            key=channel_state_key(
                channel_key, f"download-highlighted-{selection_key}"
            ),
            use_container_width=True,
        )


def render_analysis_tab(
    channel_key: str, title: str, entities: dict[str, Insurer]
) -> None:
    """Charge les documents sélectionnés et centralise leurs informations."""
    st.subheader(title)
    initialize_fund_fields(channel_key, entities)
    source_urls, source_url_errors = render_source_url_fields(channel_key, entities)
    csv_errors = sync_uploaded_csv(channel_key, entities)
    selections, document_url_errors = render_fund_fields(channel_key, entities)

    if st.button(
        "Retrieve and extract information (AI)",
        key=channel_state_key(channel_key, "extract"),
        type="primary",
        use_container_width=True,
        disabled=(
            not selections
            or bool(csv_errors)
            or bool(source_url_errors)
            or bool(document_url_errors)
        ),
    ):
        api_key = configured_openai_key()
        if not api_key:
            st.warning(
                "Configure OPENAI_API_KEY in .streamlit/secrets.toml or the environment."
            )
        else:
            st.session_state[
                channel_state_key(channel_key, "extraction-results")
            ] = extract_selections(selections, source_urls, api_key)

    render_analysis_results(
        channel_key,
        entities,
        st.session_state.get(channel_state_key(channel_key, "extraction-results")),
    )
