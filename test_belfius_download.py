from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from belfius_download import download_fund, fund_links, select_fund_link


class BelfiusLinkTests(unittest.TestCase):
    def test_fund_links_include_non_pdf_relative_links(self):
        links = fund_links(
            '<a href="/documents/example">Belfius Example Fund</a>',
            "https://www.belfius.be/site/retail/fr",
        )

        self.assertEqual(
            links,
            [
                (
                    "Belfius Example Fund",
                    "https://www.belfius.be/documents/example",
                )
            ],
        )

    def test_select_fund_link_matches_visible_name(self):
        selected = select_fund_link(
            [
                ("Belfius Balanced Fund", "https://example.com/balanced.pdf"),
                ("Belfius Equity Fund", "https://example.com/equity.pdf"),
            ],
            "Equity Fund",
        )

        self.assertEqual(selected[0], "Belfius Equity Fund")

    def test_download_fund_fetches_selected_link(self):
        page_response = Mock(text='<a href="/fund.pdf">Example Fund</a>')
        page_response.raise_for_status = Mock()
        session = Mock()
        session.get.return_value = page_response

        def write_pdf(_session, url: str, output_dir: Path, filename: str) -> Path:
            self.assertEqual(url, "https://www.belfius.be/fund.pdf")
            destination = output_dir / filename
            destination.write_bytes(b"%PDF-test")
            return destination

        with TemporaryDirectory() as temporary_directory, patch(
            "belfius_download.create_session", return_value=session
        ), patch("belfius_download.download_pdf", side_effect=write_pdf):
            destination = download_fund(
                "Example Fund",
                Path(temporary_directory),
                "https://www.belfius.be/site/retail/fr",
            )

            self.assertEqual(destination.read_bytes(), b"%PDF-test")


if __name__ == "__main__":
    unittest.main()
