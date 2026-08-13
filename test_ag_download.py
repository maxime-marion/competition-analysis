import sys
import unittest
from unittest.mock import patch

from ag_download import (
    BANK_DEFAULT_FUND,
    CHANNEL_CATALOGUE_URLS,
    DEFAULT_FUND,
    parse_args,
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


if __name__ == "__main__":
    unittest.main()
