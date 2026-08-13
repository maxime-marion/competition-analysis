import unittest

from competition_analysis.downloaders.ag import catalogue_funds, kid_links
from competition_analysis.downloaders.allianz import catalogue_documents as allianz_catalogue_documents
from competition_analysis.downloaders.athora import PAGE_URL as ATHORA_PAGE_URL
from competition_analysis.downloaders.athora import select_fund as select_athora_fund
from competition_analysis.downloaders.baloise import catalogue_documents as baloise_catalogue_documents
from competition_analysis.entities import BROKER_ENTITIES
from competition_analysis.downloaders.nn import PAGE_URL as NN_PAGE_URL
from competition_analysis.downloaders.nn import select_document as select_nn_document
from competition_analysis.downloaders.vivium import PAGE_URL as VIVIUM_PAGE_URL
from competition_analysis.downloaders.vivium import pdf_filename as vivium_pdf_filename


class AgCatalogueTests(unittest.TestCase):
    def test_catalogue_funds_deduplicates_repeated_fund_links(self):
        html = """
        <a href="/fr/fund/example">Example Fund</a>
        <a href="/fr/fund/example">Example Fund duplicate</a>
        """

        self.assertEqual(
            catalogue_funds(html, "https://ag.example/fr/allfunds"),
            [("Example Fund", "https://ag.example/fr/fund/example")],
        )

    def test_kid_links_keep_only_key_information_documents(self):
        html = """
        <a href="/documents/kid.pdf">Document d'informations clés</a>
        <a href="/documents/report.pdf">Rapport annuel</a>
        """

        self.assertEqual(
            kid_links(html, "https://ag.example/fr/fund/example"),
            [
                (
                    "Document d'informations clés",
                    "https://ag.example/documents/kid.pdf",
                )
            ],
        )


class AllianzCatalogueTests(unittest.TestCase):
    def test_catalogue_documents_keeps_public_investment_kids(self):
        data = [
            {
                "sectionName": "Investissement",
                "subSection": [
                    {
                        "subSection": [
                            {
                                "sectionName": "Document d’informations clés",
                                "assets": [
                                    {"title": "Public KID", "url": "/assets/public"},
                                    {
                                        "title": "Secured KID",
                                        "url": "/assets/secured",
                                        "secured": True,
                                    },
                                ],
                            }
                        ]
                    }
                ],
            }
        ]

        self.assertEqual(
            allianz_catalogue_documents(data, "https://api.example/bff"),
            [("Public KID", "https://api.example/bff/assets/public")],
        )


class AthoraSelectionTests(unittest.TestCase):
    def test_selection_is_accent_insensitive(self):
        links = [
            ("Profilife - Fonds Équilibré", "https://example.com/balanced.pdf"),
            ("Profilife - Equity", "https://example.com/equity.pdf"),
        ]

        self.assertEqual(
            select_athora_fund(links, "fonds equilibre"),
            links[0],
        )


class BaloiseCatalogueTests(unittest.TestCase):
    def test_catalogue_label_contains_disambiguating_details(self):
        html = """
        <table>
          <tr data-productid="123">
            <td class="product-name">Global Equity Fund</td>
            <td data-col-id="linkedProducts">Invest 23</td>
            <td data-col-id="costType">Ongoing costs</td>
            <td data-col-id="downloads"><a href="documents/eid.pdf">PDF</a></td>
          </tr>
        </table>
        """

        self.assertEqual(
            baloise_catalogue_documents(html, "https://catalogue.example/"),
            [
                (
                    "Global Equity Fund — Invest 23 — Ongoing costs",
                    "https://catalogue.example/documents/eid.pdf",
                )
            ],
        )


class NnSelectionTests(unittest.TestCase):
    def test_key_information_documents_are_preferred(self):
        links = [
            ("Annual report Example Fund", "https://example.com/report"),
            (
                "Document d'informations clés Example Fund",
                "https://example.com/kid",
            ),
        ]

        self.assertEqual(select_nn_document(links, "Example Fund"), links[1])


class ViviumFilenameTests(unittest.TestCase):
    def test_filename_uses_the_last_pdf_path_component(self):
        self.assertEqual(
            vivium_pdf_filename("https://example.com/archive/My%20Fund.pdf/version"),
            "My Fund.pdf",
        )


class EntityConfigurationTests(unittest.TestCase):
    def test_registry_reuses_provider_page_urls(self):
        self.assertEqual(BROKER_ENTITIES["athora"].source_url, ATHORA_PAGE_URL)
        self.assertEqual(BROKER_ENTITIES["nn"].source_url, NN_PAGE_URL)
        self.assertEqual(BROKER_ENTITIES["vivium"].source_url, VIVIUM_PAGE_URL)


if __name__ == "__main__":
    unittest.main()
