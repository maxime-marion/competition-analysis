import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import warnings

import pymupdf

from competition_analysis.document_processing import (
    create_highlighted_pdf,
    fetch_pdf,
    format_percentage,
    fuzzy_word_rectangles,
    highlight_fallbacks,
    parse_extraction_response,
    process_selection,
)
from competition_analysis.download_common import ApproximateMatchWarning
from competition_analysis.entities import Insurer
from competition_analysis.models import FundSelection


class DirectDocumentUrlTests(unittest.TestCase):
    def test_direct_url_bypasses_the_insurer_downloader(self):
        downloader = Mock(side_effect=AssertionError("downloader should not be called"))
        insurer = Insurer("Test", "Default", "https://example.com/catalogue", downloader)

        def write_pdf(_session, _url, output_dir: Path, filename: str) -> Path:
            destination = output_dir / filename
            destination.write_bytes(b"%PDF-direct")
            return destination

        with patch("competition_analysis.document_fetching.create_session"), patch(
            "competition_analysis.document_fetching.download_pdf", side_effect=write_pdf
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

    def test_document_variant_is_forwarded_to_the_insurer_downloader(self):
        def write_pdf(
            _fund: str,
            output_dir: Path,
            _source_url: str,
            *,
            document_variant: str,
        ) -> Path:
            self.assertEqual(document_variant, "Smart Fund Plan Private")
            destination = output_dir / "selected.pdf"
            destination.write_bytes(b"%PDF-selected")
            return destination

        insurer = Insurer(
            "AG",
            "Default",
            "https://example.com/catalogue",
            write_pdf,
            ("Easy Fund Plan", "Smart Fund Plan Private"),
            "AG plan",
        )

        filename, content = fetch_pdf(
            insurer,
            "My Fund",
            document_variant="Smart Fund Plan Private",
        )

        self.assertEqual(filename, "selected.pdf")
        self.assertEqual(content, b"%PDF-selected")


class MatchWarningTests(unittest.TestCase):
    def test_process_selection_preserves_an_approximate_match_warning(self):
        insurer = Insurer("Test", "Default", "https://example.com/catalogue", Mock())
        selection = FundSelection("test-0", "test", insurer, "Exact Fund")
        extraction = {
            "version_date": None,
            "display_date": None,
            "confidence": None,
            "recommended_holding_period_years": None,
            "reduction_in_yield_percent": None,
            "management_fees_percent": None,
            "transaction_fees_percent": None,
            "source_highlights": [],
        }

        def fetch_with_warning(*_args, **_kwargs):
            warnings.warn("Another approximate match", ApproximateMatchWarning)
            return "exact.pdf", b"%PDF-exact"

        with patch(
            "competition_analysis.document_processing.fetch_pdf",
            side_effect=fetch_with_warning,
        ), patch(
            "competition_analysis.document_processing.extract_document_information",
            return_value=extraction,
        ):
            result = process_selection(selection, insurer.source_url, Mock())

        self.assertIsNone(result.error)
        self.assertEqual(result.filename, "exact.pdf")
        self.assertEqual(result.warning, "Another approximate match")


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


class HighlightingTests(unittest.TestCase):
    @staticmethod
    def _pdf_with_text(text: str) -> bytes:
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), text)
        content = document.tobytes()
        document.close()
        return content

    def test_word_match_ignores_spacing_around_percentage_sign(self):
        content = self._pdf_with_text("Frais de gestion 1,25 %")
        with pymupdf.open(stream=content, filetype="pdf") as document:
            matches = fuzzy_word_rectangles(document[0], "1,25%")

        self.assertEqual(len(matches), 1)
        self.assertGreaterEqual(len(matches[0]), 1)

    def test_fuzzy_match_does_not_replace_a_numeric_value(self):
        content = self._pdf_with_text("Management fees 1.35 %")
        with pymupdf.open(stream=content, filetype="pdf") as document:
            matches = fuzzy_word_rectangles(document[0], "Management fees 1.25 %")

        self.assertEqual(matches, [])

    def test_word_match_does_not_confuse_decimal_with_integer(self):
        content = self._pdf_with_text("Management fees 125 %")
        with pymupdf.open(stream=content, filetype="pdf") as document:
            matches = fuzzy_word_rectangles(document[0], "1,25 %")

        self.assertEqual(matches, [])

    def test_falls_back_to_extracted_value_when_model_omits_source(self):
        content = self._pdf_with_text("Frais de gestion 1,25 %")
        extraction = parse_extraction_response(
            json.dumps({"management_fees_percent": 1.25})
        )

        highlighted, count = create_highlighted_pdf(
            content, (), highlight_fallbacks(extraction)
        )

        self.assertEqual(count, 1)
        with pymupdf.open(stream=highlighted, filetype="pdf") as document:
            self.assertIsNotNone(document[0].first_annot)

    def test_falls_back_when_model_page_or_text_is_wrong(self):
        content = self._pdf_with_text("Recommended holding period 5 years")
        extraction = parse_extraction_response(
            json.dumps(
                {
                    "recommended_holding_period_years": 5,
                    "source_highlights": [
                        {
                            "field": "holding_period",
                            "page": 9,
                            "text": "ten years",
                        }
                    ],
                }
            )
        )

        _, count = create_highlighted_pdf(
            content,
            ((9, "holding_period", "ten years"),),
            highlight_fallbacks(extraction),
        )

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
