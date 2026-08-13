import unittest

from ag_download import BANK_CATALOGUE_URL, BROKER_CATALOGUE_URL
from entities import BANK_ENTITIES, BROKER_ENTITIES
from kbc_download import PAGE_URL as KBC_PAGE_URL
from streamlit_ui import channel_state_key


class ChannelConfigurationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
