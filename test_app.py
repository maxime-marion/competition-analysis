import json
import unittest

from app import format_percentage, parse_version_date_response


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
