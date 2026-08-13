import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from competition_analysis.document_processing import (
    fetch_pdf,
    format_percentage,
    parse_extraction_response,
)
from competition_analysis.entities import Insurer


class DirectDocumentUrlTests(unittest.TestCase):
    def test_direct_url_bypasses_the_insurer_downloader(self):
        downloader = Mock(side_effect=AssertionError("downloader should not be called"))
        insurer = Insurer("Test", "Default", "https://example.com/catalogue", downloader)

        def write_pdf(_session, _url, output_dir: Path, filename: str) -> Path:
            destination = output_dir / filename
            destination.write_bytes(b"%PDF-direct")
            return destination

        with patch("competition_analysis.document_processing.create_session"), patch(
            "competition_analysis.document_processing.download_pdf", side_effect=write_pdf
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


class ExtractionResponseTests(unittest.TestCase):
    def test_accepts_single_and_interval_fee_percentages(self):
        response = parse_extraction_response(
            json.dumps(
                {
                    "management_fees_percent": 1.25,
                    "transaction_fees_percent": [0.1, 0.3],
                    "source_highlights": [
                        {
                            "field": "management_fees",
                            "page": 2,
                            "text": "Management fees 1.25%",
                        },
                        {
                            "field": "transaction_fees",
                            "page": 2,
                            "text": "Transaction fees 0.1% - 0.3%",
                        },
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
            parse_extraction_response(
                json.dumps({"management_fees_percent": ["0.1", "0.3"]})
            )

    def test_rejects_reversed_fee_interval(self):
        with self.assertRaisesRegex(ValueError, "transaction_fees_percent"):
            parse_extraction_response(
                json.dumps({"transaction_fees_percent": [0.3, 0.1]})
            )

    def test_rejects_unknown_confidence(self):
        with self.assertRaisesRegex(ValueError, "confidence"):
            parse_extraction_response(json.dumps({"confidence": "certain"}))


if __name__ == "__main__":
    unittest.main()
