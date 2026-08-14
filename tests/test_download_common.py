import unittest
import warnings

from competition_analysis.download_common import (
    ApproximateMatchWarning,
    pdf_filename_from_title,
    select_unique_match,
)


class PdfFilenameTests(unittest.TestCase):
    def test_title_is_sanitized_and_gets_a_pdf_suffix(self):
        self.assertEqual(
            pdf_filename_from_title("Fund: Balanced / Growth", "document.pdf"),
            "Fund_ Balanced _ Growth.pdf",
        )

    def test_existing_pdf_suffix_is_not_duplicated(self):
        self.assertEqual(
            pdf_filename_from_title("Existing.PDF", "document.pdf"),
            "Existing.PDF",
        )


class SelectUniqueMatchTests(unittest.TestCase):
    def select(self, links, query):
        return select_unique_match(
            links,
            query,
            missing_label="Fund",
            multiple_label="documents",
        )

    def test_exact_match_is_selected_and_partial_match_is_reported(self):
        links = [
            ("Global Equity Fund", "https://example.com/exact.pdf"),
            (
                "Global Equity Fund — Invest 23",
                "https://example.com/extended.pdf",
            ),
        ]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            selected = self.select(links, "Global Equity Fund")

        self.assertEqual(selected, links[0])
        self.assertEqual(len(caught), 1)
        self.assertTrue(issubclass(caught[0].category, ApproximateMatchWarning))
        self.assertIn("Global Equity Fund — Invest 23", str(caught[0].message))

    def test_multiple_partial_matches_remain_ambiguous(self):
        links = [
            ("Global Equity Fund A", "https://example.com/a.pdf"),
            ("Global Equity Fund B", "https://example.com/b.pdf"),
        ]

        with self.assertRaisesRegex(RuntimeError, "matches multiple documents"):
            self.select(links, "Global Equity Fund")

    def test_unique_partial_match_is_returned(self):
        links = [
            ("DIC - Euro Corporate SRI Bonds", "https://example.com/sri.pdf"),
            ("DIC - Global Equity Fund", "https://example.com/equity.pdf"),
        ]

        self.assertEqual(
            self.select(links, "Euro Corporate"),
            links[0],
        )


if __name__ == "__main__":
    unittest.main()
