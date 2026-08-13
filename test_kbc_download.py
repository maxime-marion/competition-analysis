from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from kbc_download import download_fund, kid_links, select_kid


CATALOGUE_HTML = """
<h2>Horizon</h2>
<ul>
  <li>KBC Defensive Balanced Classic Shares CAP
    <a href="https://files.example/KID/KID_BE6290498482_NL.PDF">NL</a>
    <a href="https://files.example/KID/KID_BE6290498482_FR.PDF">FR</a>
  </li>
  <li>Fund with a mismatched French link
    <a href="https://files.example/KID/KID_BE6343763601_NL.PDF">FR</a>
  </li>
</ul>
"""

class KbcCatalogueTests(unittest.TestCase):
    def test_kid_links_extract_french_documents_with_disambiguators(self):
        links = kid_links(CATALOGUE_HTML)

        self.assertEqual(len(links), 2)
        self.assertEqual(
            links[0],
            (
                "KBC Defensive Balanced Classic Shares CAP — Horizon — BE6290498482",
                "https://files.example/KID/KID_BE6290498482_FR.PDF",
            ),
        )
        self.assertTrue(links[1][1].endswith("_FR.PDF"))

    def test_select_kid_accepts_a_fund_name(self):
        links = kid_links(CATALOGUE_HTML)

        self.assertEqual(select_kid(links, "Defensive Balanced")[1], links[0][1])

    def test_download_fund_uses_only_the_kid_page(self):
        page_response = Mock(text=CATALOGUE_HTML)
        page_response.raise_for_status = Mock()
        session = Mock()
        session.get.return_value = page_response

        def write_pdf(_session, url: str, output_dir: Path, filename: str) -> Path:
            self.assertEqual(url, "https://files.example/KID/KID_BE6290498482_FR.PDF")
            destination = output_dir / filename
            destination.write_bytes(b"%PDF-test")
            return destination

        with TemporaryDirectory() as temporary_directory, patch(
            "kbc_download.create_session", return_value=session
        ), patch("kbc_download.download_pdf", side_effect=write_pdf):
            destination = download_fund(
                "Defensive Balanced",
                Path(temporary_directory),
                "https://www.kbc.be/kid-index",
            )
            self.assertEqual(destination.read_bytes(), b"%PDF-test")

        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args.args[0], "https://www.kbc.be/kid-index")
        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
