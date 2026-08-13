import unittest

from competition_analysis.entities import BANK_ENTITIES
from competition_analysis.selection_import import parse_fund_csv


class FundCsvTests(unittest.TestCase):
    def test_accepts_an_optional_direct_document_url(self):
        selections, errors = parse_fund_csv(
            b"entity,fund name,document URL\nAG,My Fund,https://example.com/my-fund.pdf\n"
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(selections), 1)
        self.assertEqual(
            selections[0].document_url, "https://example.com/my-fund.pdf"
        )

    def test_rejects_an_invalid_direct_document_url(self):
        selections, errors = parse_fund_csv(
            b"entity,fund name,direct URL\nAG,My Fund,example.com/my-fund.pdf\n"
        )

        self.assertEqual(selections, [])
        self.assertRegex(errors[0], "document URL must start")

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


if __name__ == "__main__":
    unittest.main()
