import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from ag_download import BANK_CATALOGUE_URL, BROKER_CATALOGUE_URL
from kbc_download import PAGE_URL as KBC_PAGE_URL
from app import (
    BANK_ENTITIES,
    BROKER_ENTITIES,
    Insurer,
    channel_state_key,
    fetch_pdf,
    format_percentage,
    parse_fund_csv,
    parse_version_date_response,
)


class DirectDocumentUrlTests(unittest.TestCase):
    def test_csv_accepts_an_optional_direct_document_url(self):
        selections, errors = parse_fund_csv(
            b"entity,fund name,document URL\nAG,My Fund,https://example.com/my-fund.pdf\n"
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(selections), 1)
        self.assertEqual(
            selections[0].document_url, "https://example.com/my-fund.pdf"
        )

    def test_csv_rejects_an_invalid_direct_document_url(self):
        selections, errors = parse_fund_csv(
            b"entity,fund name,direct URL\nAG,My Fund,example.com/my-fund.pdf\n"
        )

        self.assertEqual(selections, [])
        self.assertRegex(errors[0], "document URL must start")

    def test_direct_url_bypasses_the_insurer_downloader(self):
        downloader = Mock(side_effect=AssertionError("downloader should not be called"))
        insurer = Insurer("Test", "Default", "https://example.com/catalogue", downloader)

        def write_pdf(_session, _url, output_dir: Path, filename: str) -> Path:
            destination = output_dir / filename
            destination.write_bytes(b"%PDF-direct")
            return destination

        with patch("app.create_session"), patch(
            "app.download_pdf", side_effect=write_pdf
        ) as direct_download:
            filename, content = fetch_pdf(
                insurer,
                "My Fund",
                document_url="https://example.com/direct.pdf",
            )

        self.assertEqual(filename, "direct.pdf")
        self.assertEqual(content, b"%PDF-direct")
        self.assertEqual(downloader.call_count, 0)
        direct_download.assert_called_once()


class ChannelConfigurationTests(unittest.TestCase):
    def test_bank_csv_accepts_bank_entities(self):
        selections, errors = parse_fund_csv(
            (
                b"entity,fund name\n"
                b"AG,AG Life Sustainable Defensive\n"
                b"Belfius,Example Bank Fund\n"
                b"KBC,KBC Defensive Balanced Classic Shares CAP\n"
            ),
            BANK_ENTITIES,
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            {selection.identifier for selection in selections}, {"ag", "belfius", "kbc"}
        )

    def test_bank_ag_uses_bnppf_catalogue(self):
        self.assertEqual(BANK_ENTITIES["ag"].source_url, BANK_CATALOGUE_URL)

    def test_bank_channel_includes_kbc_kid_catalogue(self):
        self.assertEqual(BANK_ENTITIES["kbc"].label, "KBC")
        self.assertEqual(BANK_ENTITIES["kbc"].source_url, KBC_PAGE_URL)
        self.assertIsNotNone(BANK_ENTITIES["kbc"].downloader)

    def test_broker_ag_uses_broker_catalogue(self):
        self.assertEqual(BROKER_ENTITIES["ag"].source_url, BROKER_CATALOGUE_URL)

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


class FeeExtractionTests(unittest.TestCase):
    def test_accepts_single_and_interval_fee_percentages(self):
        response = parse_version_date_response(
            json.dumps(
                {
                    "management_fees_percent": 1.25,
                    "transaction_fees_percent": [0.1, 0.3],
                    "source_highlights": [
                        {"field": "management_fees", "page": 2, "text": "Management fees 1.25%"},
                        {"field": "transaction_fees", "page": 2, "text": "Transaction fees 0.1% - 0.3%"},
                    ],
                }
            )
        )

        self.assertEqual(response["management_fees_percent"], 1.25)
        self.assertEqual(response["transaction_fees_percent"], [0.1, 0.3])
        self.assertEqual(len(response["source_highlights"]), 2)
        self.assertEqual(format_percentage(1.25), "1.25 %")
        self.assertEqual(format_percentage([0.1, 0.3]), "0.1–0.3 %")

    def test_rejects_non_numeric_fee_interval(self):
        with self.assertRaisesRegex(ValueError, "management_fees_percent"):
            parse_version_date_response(
                json.dumps({"management_fees_percent": ["0.1", "0.3"]})
            )

    def test_rejects_reversed_fee_interval(self):
        with self.assertRaisesRegex(ValueError, "transaction_fees_percent"):
            parse_version_date_response(
                json.dumps({"transaction_fees_percent": [0.3, 0.1]})
            )


if __name__ == "__main__":
    unittest.main()
