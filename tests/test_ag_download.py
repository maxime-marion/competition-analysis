import sys
import unittest
from unittest.mock import patch

from competition_analysis.downloaders.ag import (
    BANK_DEFAULT_FUND,
    CHANNEL_CATALOGUE_URLS,
    DEFAULT_FUND,
    KID_PLANS,
    parse_args,
    select_kid,
)


class AgCommandLineTests(unittest.TestCase):
    def test_channel_is_required(self):
        with patch.object(sys, "argv", ["ag_download.py"]), self.assertRaises(SystemExit):
            parse_args()

    def test_channel_selects_its_default_fund(self):
        for channel, expected_fund in (
            ("broker", DEFAULT_FUND),
            ("bank", BANK_DEFAULT_FUND),
        ):
            with self.subTest(channel=channel), patch.object(
                sys, "argv", ["ag_download.py", "--channel", channel]
            ):
                arguments = parse_args()
                self.assertEqual(arguments.fund, expected_fund)
                self.assertIn(channel, CHANNEL_CATALOGUE_URLS)

    def test_plan_is_forwarded_by_the_command_line(self):
        with patch.object(
            sys,
            "argv",
            ["ag_download.py", "--channel", "bank", "--plan", KID_PLANS[1]],
        ):
            arguments = parse_args()

        self.assertEqual(arguments.plan, "Smart Fund Plan Private")


class AgKidSelectionTests(unittest.TestCase):
    def setUp(self):
        self.links = [
            (
                "Document d'informations clés via Easy Fund Plan",
                "https://example.com/easy.pdf",
            ),
            (
                "Document d'informations clés via Smart Fund Plan Private",
                "https://example.com/private.pdf",
            ),
        ]

    def test_plan_selects_the_matching_kid(self):
        self.assertEqual(select_kid(self.links, "Smart Fund Plan Private"), self.links[1])

    def test_multiple_kids_still_raise_without_a_plan(self):
        with self.assertRaisesRegex(RuntimeError, "Multiple KIDs"):
            select_kid(self.links)

    def test_missing_plan_has_an_explicit_error(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown Plan"):
            select_kid(self.links, "Unknown Plan")


if __name__ == "__main__":
    unittest.main()
