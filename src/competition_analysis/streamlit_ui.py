"""Composants Streamlit de l'analyse concurrentielle."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

from openai import OpenAI
import pandas as pd
import streamlit as st

from competition_analysis.document_processing import (
    extract_retrieved_document,
    format_number,
    format_percentage,
    format_version_date,
    retrieve_selection,
)
from competition_analysis.entities import BROKER_ENTITIES, Insurer
from competition_analysis.models import ExtractionResult, FundSelection, RetrievalResult
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
                document_variant = st.session_state.get(
                    channel_state_key(channel_key, f"document-variant-{identifier}"),
                    insurer.document_variants[0] if insurer.document_variants else None,
                )
                selections.append(
                    FundSelection(
                        f"{identifier}-{index}",
                        identifier,
                        insurer,
                        fund,
                        document_url or None,
                        document_variant,
                        st.session_state.get(
                            channel_state_key(
                                channel_key,
                                f"comparison-ag-fund-{identifier}-{index}",
                            ),
                            "",
                        ).strip()
                        or None,
                    )
                )
    return selections


def clear_channel_results(channel_key: str) -> None:
    """Évite d'afficher des résultats qui ne correspondent plus aux champs."""
    st.session_state.pop(channel_state_key(channel_key, "retrieval-results"), None)
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
        if insurer.document_variants:
            st.session_state[
                channel_state_key(channel_key, f"document-variant-{identifier}")
            ] = insurer.document_variants[0]
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
            "bypasses the search by fund name. The optional AG fund column identifies "
            "the AG fund used for comparison. Supported entities in this channel: "
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

    imported_funds: dict[str, list[tuple[str, str, str]]] = {
        identifier: [] for identifier in entities
    }
    for selection in imported_selections:
        imported_funds[selection.identifier].append(
            (
                selection.fund,
                selection.document_url or "",
                selection.comparison_ag_fund or "",
            )
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
            st.session_state[
                channel_state_key(
                    channel_key, f"comparison-ag-fund-{identifier}-{index}"
                )
            ] = funds[index][2] if index < len(funds) else ""
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
    for identifier, insurer in sorted(
        entities.items(), key=lambda item: item[1].label.casefold()
    ):
        if insurer.document_variants:
            st.selectbox(
                insurer.document_variant_label,
                insurer.document_variants,
                key=channel_state_key(
                    channel_key, f"document-variant-{identifier}"
                ),
                on_change=clear_channel_results,
                args=(channel_key,),
                help=f"Applied to every {insurer.label} fund in this analysis.",
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
                if identifier != "ag" and "ag" in entities:
                    st.text_input(
                        f"{insurer.label} — AG fund used for comparison {field_index + 1}",
                        key=channel_state_key(
                            channel_key,
                            f"comparison-ag-fund-{identifier}-{field_index}",
                        ),
                        placeholder="AG fund used for comparison (optional)",
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
    selected_ag_funds = {
        selection.fund.casefold()
        for selection in selections
        if selection.identifier == "ag"
    }
    comparison_errors = [
        f"The AG comparison fund for {selection.insurer.label} — {selection.fund} "
        "must exactly match an AG fund selected in this analysis."
        for selection in selections
        if (
            selection.identifier != "ag"
            and selection.comparison_ag_fund
            and selection.comparison_ag_fund.casefold() not in selected_ag_funds
        )
    ]
    errors = document_url_errors + comparison_errors
    for error in errors:
        st.error(error)
    return selections, errors


def retrieve_selections(
    selections: list[FundSelection], source_urls: dict[str, str]
) -> dict[str, RetrievalResult]:
    """Télécharge toutes les sélections avant toute extraction par IA."""
    results: dict[str, RetrievalResult] = {}
    progress = st.progress(0, text="Preparing retrieval…")
    for index, selection in enumerate(selections):
        progress.progress(
            index / len(selections),
            text=f"{selection.insurer.label}: retrieving document…",
        )
        results[selection.key] = retrieve_selection(
            selection, source_urls[selection.identifier]
        )
    progress.progress(1.0, text="Document retrieval complete.")
    return results


def extract_selections(
    retrieved_documents: dict[str, RetrievalResult], api_key: str
) -> dict[str, ExtractionResult]:
    """Extrait et surligne les documents déjà récupérés."""
    progress = st.progress(0, text="Preparing extraction…")
    client = OpenAI(api_key=api_key)
    results: dict[str, ExtractionResult] = {}
    total_stages = len(retrieved_documents) * 2
    for index, (selection_key, retrieved) in enumerate(retrieved_documents.items()):
        stage_start = index * 2

        def report_progress(stage: int, *, retrieved=retrieved) -> None:
            stage_label = ("extracting information…", "highlighting PDF…")[stage]
            progress.progress(
                (stage_start + stage) / total_stages,
                text=f"{retrieved.selection.insurer.label}: {stage_label}",
            )

        results[selection_key] = extract_retrieved_document(
            retrieved, client, report_progress
        )

    progress.progress(1.0, text="Extraction and highlighting complete.")
    return results


def result_row(
    result: ExtractionResult,
    entities: dict[str, Insurer] | None = None,
    is_comparison_ag_fund: bool = False,
) -> dict[str, str]:
    """Convertit un résultat structuré en ligne de tableau."""
    entities = BROKER_ENTITIES if entities is None else entities
    row = {
        "Entity": (
            "↳ AG" if is_comparison_ag_fund else entities[result.identifier].label
        ),
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
    extracted_source_count = sum(
        value is not None
        for value in (
            extraction["version_date"],
            holding_period,
            reduction_in_yield,
            extraction["management_fees_percent"],
            extraction["transaction_fees_percent"],
        )
    )
    if result.highlight_error:
        status = (
            f"Information extracted; highlighting unavailable: {result.highlight_error}"
        )
    elif result.highlighted_count < extracted_source_count:
        status = (
            "Information extracted; highlighting partial "
            f"({result.highlighted_count}/{extracted_source_count})"
        )
    else:
        status = (
            f"Complete — {result.highlighted_count}/{extracted_source_count} highlighted"
        )
    if result.extraction_attempts > 1:
        status = f"Retried extraction once; {status}"
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
            "Status": status,
        }
    )
    return row


def comparison_result_rows(
    results: dict[str, ExtractionResult], entities: dict[str, Insurer]
) -> list[dict[str, str]]:
    """Présente chaque concurrent, suivi du fonds AG auquel il est comparé."""
    ag_results = {
        result.fund.casefold(): result
        for result in results.values()
        if result.identifier == "ag"
    }
    rows: list[dict[str, str]] = []
    for result in results.values():
        if result.identifier == "ag":
            continue
        rows.append(result_row(result, entities))
        if result.comparison_ag_fund:
            ag_result = ag_results.get(result.comparison_ag_fund.casefold())
            if ag_result:
                rows.append(result_row(ag_result, entities, is_comparison_ag_fund=True))
    return rows


def comparison_result_row_style(row: pd.Series) -> list[str]:
    """Colore les lignes AG et concurrentes pour rendre chaque paire lisible."""
    color = "background-color: #e8f5e9; color: #1b5e20"  # Green for AG.
    if row["Entity"] != "↳ AG":
        color = "background-color: #e8f1ff; color: #0d47a1"  # Blue for competitors.
    return [color] * len(row)


def render_retrieval_results(
    channel_key: str,
    entities: dict[str, Insurer],
    results: dict[str, RetrievalResult] | None,
) -> None:
    """Affiche les documents récupérés et les erreurs à corriger avant l'IA."""
    if not results:
        return

    with st.expander("Retrieved document details", expanded=False):
        for selection_key, result in results.items():
            insurer = entities[result.selection.identifier]
            label = f"{insurer.label} — {result.selection.fund}"
            if result.error:
                st.error(f"{label}: {result.error}")
                continue
            st.success(f"{label}: {result.filename} retrieved.")
            if result.warning:
                st.warning(f"{label}: {result.warning}")
            if result.filename and result.content is not None:
                st.download_button(
                    f"Retrieved PDF — {label}",
                    data=result.content,
                    file_name=result.filename,
                    mime="application/pdf",
                    key=channel_state_key(
                        channel_key, f"download-retrieved-{selection_key}"
                    ),
                )


def render_analysis_results(
    channel_key: str,
    entities: dict[str, Insurer],
    results: dict[str, ExtractionResult] | None,
) -> None:
    """Affiche le tableau et les téléchargements des extractions."""
    if not results:
        st.info("No bulk extraction has been run yet.")
        return

    result_dataframe = pd.DataFrame(comparison_result_rows(results, entities))
    st.dataframe(
        result_dataframe.style.apply(comparison_result_row_style, axis=1),
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
        elif result.warning:
            insurer = entities[result.identifier]
            st.warning(f"{insurer.label} — {result.fund}: {result.warning}")

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
        "Retrieve documents",
        key=channel_state_key(channel_key, "retrieve"),
        type="primary",
        use_container_width=True,
        disabled=(
            not selections
            or bool(csv_errors)
            or bool(source_url_errors)
            or bool(document_url_errors)
        ),
    ):
        st.session_state[channel_state_key(channel_key, "retrieval-results")] = (
            retrieve_selections(selections, source_urls)
        )
        st.session_state.pop(channel_state_key(channel_key, "extraction-results"), None)

    retrieval_results = st.session_state.get(
        channel_state_key(channel_key, "retrieval-results")
    )
    retrieval_ready = bool(retrieval_results) and all(
        result.error is None and result.content is not None
        for result in retrieval_results.values()
    )
    if retrieval_results and not retrieval_ready:
        st.info("Correct the failed fund names or URLs, then retrieve the documents again.")

    render_retrieval_results(channel_key, entities, retrieval_results)

    if st.button(
        "Extract and highlight information (AI)",
        key=channel_state_key(channel_key, "extract"),
        type="primary",
        use_container_width=True,
        disabled=not retrieval_ready,
    ):
        api_key = configured_openai_key()
        if not api_key:
            st.warning(
                "Configure OPENAI_API_KEY in .streamlit/secrets.toml or the environment."
            )
        else:
            st.session_state[
                channel_state_key(channel_key, "extraction-results")
            ] = extract_selections(retrieval_results, api_key)

    render_analysis_results(
        channel_key,
        entities,
        st.session_state.get(channel_state_key(channel_key, "extraction-results")),
    )
