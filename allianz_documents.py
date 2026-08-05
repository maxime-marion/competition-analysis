#!/usr/bin/env python3
"""Liste les documents d'information clés du premier produit d'investissement Allianz."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


URL = "https://www.allianz.be/fr/particuliers/documents.html"
CATEGORY = "Investissement"
DOCUMENT_TYPE = "Document d’informations clés"


@dataclass(frozen=True)
class Selection:
    field: str
    value: str


def dismiss_cookie_banner(page: Page) -> None:
    """Refuse les cookies facultatifs si la bannière est présente."""
    reject = page.get_by_role("link", name="Refuser", exact=True)
    if reject.count():
        reject.click()


def select_value(page: Page, selection: Selection, current_value: str = "Toutes") -> None:
    """Sélectionne une valeur dans l'un des menus déroulants Allianz."""
    button = page.get_by_role(
        "button", name=f"{current_value} {selection.field}", exact=True
    )
    button.wait_for(state="visible")
    button.click()

    option = page.get_by_role("option", name=selection.value, exact=True)
    option.wait_for(state="visible")
    option.click()

    page.get_by_role(
        "button", name=f"{selection.value} {selection.field}", exact=True
    ).wait_for(state="visible")


def first_product(page: Page) -> str:
    """Ouvre le menu Produit et retourne la première valeur autre que « Toutes »."""
    button = page.get_by_role("button", name="Toutes Produit", exact=True)
    button.wait_for(state="visible")
    button.click()

    options: Locator = page.locator(".cdk-overlay-container [role='option']")
    options.first.wait_for(state="visible")
    values = [value.strip() for value in options.all_inner_texts()]
    product = next((value for value in values if value and value != "Toutes"), None)
    if product is None:
        raise RuntimeError("Aucun produit n'est proposé pour la catégorie Investissement.")

    page.get_by_role("option", name=product, exact=True).click()
    page.get_by_role("button", name=f"{product} Produit", exact=True).wait_for(
        state="visible"
    )
    return product


def document_titles(page: Page) -> list[str]:
    """Lit les titres de la deuxième colonne de la table de résultats filtrée."""
    rows = page.locator("app-gse-doc tbody tr")
    page.wait_for_function(
        """document_type => {
            const rows = [...document.querySelectorAll('app-gse-doc tbody tr')]
                .filter(row => row.cells.length >= 4);
            return rows.length > 0 && rows.every(row =>
                row.cells[3].innerText.trim() === document_type
            );
        }""",
        DOCUMENT_TYPE,
        timeout=30_000,
    )
    titles = rows.locator("td:nth-child(2)").all_inner_texts()
    return [title.strip() for title in titles if title.strip()]


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="fr-BE")

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
            page.locator("app-gse-doc").wait_for(state="visible", timeout=45_000)
            dismiss_cookie_banner(page)

            select_value(page, Selection("Catégorie", CATEGORY))
            product = first_product(page)
            select_value(page, Selection("Type de document", DOCUMENT_TYPE))

            titles = document_titles(page)
            print(f"Produit retenu : {product}")
            print(f"Documents « {DOCUMENT_TYPE} » ({len(titles)}) :")
            for title in titles:
                print(f"- {title}")
        except PlaywrightTimeoutError as error:
            raise RuntimeError(
                "La page Allianz a changé ou n'a pas fini de charger. "
                "Vérifiez les libellés des menus et réessayez."
            ) from error
        finally:
            browser.close()


if __name__ == "__main__":
    main()
