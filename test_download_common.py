import unittest

from download_common import pdf_filename_from_title, select_unique_match


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

    def test_exact_match_does_not_hide_partial_match(self):
        links = [
            ("Global Equity Fund", "https://example.com/exact.pdf"),
            (
                "Global Equity Fund — Invest 23",
                "https://example.com/extended.pdf",
            ),
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
