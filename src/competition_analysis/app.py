"""Point d'entrée Streamlit de l'analyse concurrentielle."""

from __future__ import annotations

import streamlit as st

from competition_analysis.entities import BANK_ENTITIES, BROKER_ENTITIES
from competition_analysis.streamlit_ui import render_analysis_tab


def main() -> None:
    """Configure la page et affiche les deux canaux d'analyse."""
    st.set_page_config(page_title="Fund documents", page_icon="📄", layout="wide")
    broker_tab, bank_tab = st.tabs(["Broker channel", "Bank channel"])
    with broker_tab:
        render_analysis_tab(
            "broker", "Broker channel competition analysis", BROKER_ENTITIES
        )
    with bank_tab:
        render_analysis_tab("bank", "Bank channel competition analysis", BANK_ENTITIES)


if __name__ == "__main__":
    main()
