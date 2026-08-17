import unittest
from unittest.mock import Mock, patch

from competition_analysis.downloaders.ag import (
    BANK_CATALOGUE_URL,
    BROKER_CATALOGUE_URL,
    KID_PLANS,
)
from competition_analysis.entities import BANK_ENTITIES, BROKER_ENTITIES
from competition_analysis.downloaders.kbc import PAGE_URL as KBC_PAGE_URL
from competition_analysis.models import ExtractionResult, FundSelection, RetrievalResult
from competition_analysis.streamlit_ui import (
    comparison_result_row_style,
    comparison_result_rows,
    channel_state_key,
    extract_selections,
    retrieve_selections,
)


class ChannelConfigurationTests(unittest.TestCase):
    def test_bank_ag_uses_bnppf_catalogue(self):
        self.assertEqual(BANK_ENTITIES["ag"].source_url, BANK_CATALOGUE_URL)
        self.assertEqual(BANK_ENTITIES["ag"].document_variants, KID_PLANS)

    def test_bank_channel_includes_kbc_kid_catalogue(self):
        self.assertEqual(BANK_ENTITIES["kbc"].label, "KBC")
        self.assertEqual(BANK_ENTITIES["kbc"].source_url, KBC_PAGE_URL)
        self.assertIsNotNone(BANK_ENTITIES["kbc"].downloader)

    def test_broker_ag_uses_broker_catalogue(self):
        self.assertEqual(BROKER_ENTITIES["ag"].source_url, BROKER_CATALOGUE_URL)
        self.assertEqual(BROKER_ENTITIES["ag"].document_variants, ())

    def test_channel_keys_are_isolated(self):
        self.assertEqual(
            channel_state_key("broker", "fund-belfius-0"),
            "broker-fund-belfius-0",
        )
        self.assertEqual(
            channel_state_key("bank", "fund-belfius-0"),
            "bank-fund-belfius-0",
        )
        self.assertNotEqual(
            channel_state_key("broker", "extraction-results"),
            channel_state_key("bank", "extraction-results"),
        )

    def test_results_show_the_referenced_ag_fund_below_each_competitor(self):
        results = {
            "ag-0": ExtractionResult("ag", "AG Life Defensive"),
            "belfius-0": ExtractionResult(
                "belfius", "Belfius Balanced", comparison_ag_fund="AG Life Defensive"
            ),
            "kbc-0": ExtractionResult(
                "kbc", "KBC Balanced", comparison_ag_fund="AG Life Defensive"
            ),
        }

        rows = comparison_result_rows(results, BANK_ENTITIES)

        self.assertEqual(
            [(row["Entity"], row["Fund"]) for row in rows],
            [
                ("Belfius", "Belfius Balanced"),
                ("↳ AG", "AG Life Defensive"),
                ("KBC", "KBC Balanced"),
                ("↳ AG", "AG Life Defensive"),
            ],
        )

    def test_result_row_styles_distinguish_ag_and_competitor_rows(self):
        self.assertTrue(
            all(
                "#e8f5e9" in style
                for style in comparison_result_row_style({"Entity": "↳ AG"})
            )
        )
        self.assertTrue(
            all(
                "#e8f1ff" in style
                for style in comparison_result_row_style({"Entity": "Belfius"})
            )
        )


class ExtractionPipelineTests(unittest.TestCase):
    def test_retrieval_does_not_start_extraction(self):
        insurer = BROKER_ENTITIES["ag"]
        selections = [
            FundSelection("ag-0", "ag", insurer, "First fund"),
            FundSelection("ag-1", "ag", insurer, "Second fund"),
        ]
        events: list[str] = []
        retrieved_documents = {
            "ag-0": RetrievalResult(selections[0], "first.pdf", b"first"),
            "ag-1": RetrievalResult(selections[1], "second.pdf", b"second"),
        }

        def retrieve(selection, _source_url):
            events.append(f"retrieve:{selection.key}")
            return retrieved_documents[selection.key]

        with patch("competition_analysis.streamlit_ui.st.progress", return_value=Mock()), patch(
            "competition_analysis.streamlit_ui.retrieve_selection", side_effect=retrieve
        ):
            results = retrieve_selections(selections, {"ag": insurer.source_url})

        self.assertEqual(
            events,
            ["retrieve:ag-0", "retrieve:ag-1"],
        )
        self.assertEqual(set(results), {"ag-0", "ag-1"})

    def test_extraction_uses_already_retrieved_documents(self):
        insurer = BROKER_ENTITIES["ag"]
        selection = FundSelection("ag-0", "ag", insurer, "Fund")
        retrieved = {"ag-0": RetrievalResult(selection, "fund.pdf", b"content")}

        with patch("competition_analysis.streamlit_ui.st.progress", return_value=Mock()), patch(
            "competition_analysis.streamlit_ui.OpenAI"
        ), patch(
            "competition_analysis.streamlit_ui.extract_retrieved_document",
            return_value=ExtractionResult("ag", "Fund"),
        ) as extract:
            extract_selections(retrieved, "key")

        extract.assert_called_once()


if __name__ == "__main__":
    unittest.main()
