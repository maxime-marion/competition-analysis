# Analyse concurrentielle de documents financiers

## Téléchargement d'un document Allianz

Le script Allianz interroge directement l'API publique utilisée par le centre de
documents, sans navigateur ni simulation d'interface :

```bash
python -m competition_analysis.downloaders.allianz
```

Par défaut, il télécharge le DIC `Allianz ActiveInvest`. Un nom partiel unique peut
être fourni pour sélectionner un autre document :

```bash
python -m competition_analysis.downloaders.allianz --document "ActiveInvest Balanced"
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Le code applicatif se trouve dans `src/competition_analysis`, les téléchargeurs
spécifiques aux entités dans `src/competition_analysis/downloaders`, les tests dans
`tests` et le CSV d'exemple dans `examples`.

Pour lancer les tests :

```bash
python -m unittest discover -s tests -v
```

## Téléchargement d'un DIC Vivium

Le script Vivium recherche directement le nom du fonds parmi les PDF affichés
sur la page, sans dépendre d'une rubrique ou d'un accordéon. Aucun navigateur
n'est nécessaire :

```bash
python -m competition_analysis.downloaders.vivium
```

Par défaut, le script télécharge le DIC « Euro Corporate SRI Bonds ». Pour choisir un autre fonds :

```bash
python -m competition_analysis.downloaders.vivium --fund "Stability Fund"
```

Le PDF est enregistré dans le dossier `vivium_downloads`. À chaque exécution, le script relit la page Vivium afin de récupérer l'URL la plus récente du document.

## Téléchargement d'un document Profilife Athora

Le script Athora recherche directement le nom du fonds dans les documents affichés sur la page, sans dépendre d'une rubrique ou d'un accordéon :

```bash
python -m competition_analysis.downloaders.athora
```

Par défaut, il télécharge le document du fonds `Profilife - Athora DNCA Invest Beyd Semperosa A`. Pour choisir un autre fonds Profilife :

```bash
python -m competition_analysis.downloaders.athora --fund "Athora Pictet Gbl Megatrend Select P"
```

Le PDF est enregistré dans le dossier `athora_downloads`. Le script relit la page Athora à chaque exécution afin de suivre une éventuelle modification de l'URL du document.

## Téléchargement d'un document NN

Le script NN recherche le nom du fonds parmi les documents affichés sur la page
des documents légaux :

```bash
python -m competition_analysis.downloaders.nn
```

Par défaut, il télécharge le document essentiel du fonds `NN Blackrock Global Allocation Fund`. Pour choisir un autre document :

```bash
python -m competition_analysis.downloaders.nn --document "NN Fidelity world Fund"
```

Le PDF est enregistré dans le dossier `nn_downloads`. Le script relit la page NN à chaque exécution afin de récupérer l'URL et le jeton publics actuellement associés au document.

## Téléchargement d'un EID Baloise

Le script Baloise consulte le catalogue EID public intégré à la page de documents
Baloise et recherche le fonds par nom exact ou partiel :

```bash
python -m competition_analysis.downloaders.baloise
```

Par défaut, il télécharge l'EID de `Global Equity Fund`. Pour choisir un autre fonds :

```bash
python -m competition_analysis.downloaders.baloise --fund "Pictet Smartcity Fund"
```

Lorsqu'un fonds existe pour plusieurs produits, utilise le libellé distinctif affiché
dans le message d'erreur, par exemple `nom du fonds — produit — type de prime`.
Le PDF est enregistré dans le dossier `baloise_downloads`.

## Application Streamlit

L'application propose deux onglets alimentés par le même workflow d'analyse :

- **Broker channel** regroupe Allianz, Vivium, Athora, Baloise, NN et AG ;
- **Bank channel** compare AG (catalogue BNP Paribas Fortis), Belfius et KBC.

Chaque onglet conserve ses propres champs, liens source et résultats. Saisis un fonds,
clique sur le bouton de récupération, puis télécharge le document original ou sa copie
surlignée :

```bash
python -m pip install -e .
streamlit run src/competition_analysis/app.py
```

### Documents Belfius

Le téléchargeur Belfius recherche directement le nom du fonds dans le texte visible
des liens de la page retail configurée. Le lien correspondant est ensuite téléchargé
et validé comme PDF. L'URL source reste modifiable dans l'onglet **Bank channel**.

### Documents AG du canal bancaire

L'entité AG du canal bancaire réutilise le téléchargeur MuMa avec son catalogue
spécifique BNP Paribas Fortis : `https://bnppf.ag-muma.be/fr/allfunds`. Elle est
indépendante de l'entité AG du canal Broker, qui conserve son URL source actuelle.
Le sélecteur global **AG product for which funds are associated** permet de choisir
le KID « Easy Fund Plan » ou « Smart Fund Plan Private » pour tous les fonds AG de
l'analyse bancaire.

### Documents KBC

L'entité KBC utilise uniquement le catalogue public des documents d'informations clés
publié par KBC. Elle y recherche directement le nom du fonds, puis télécharge le KID
français, sans appeler l'API de recherche de fonds.
Un nom partiel unique est accepté. En cas de noms identiques, le message d'erreur
affiche les correspondances disponibles :

```bash
python -m competition_analysis.downloaders.kbc --fund "KBC Defensive Balanced Classic Shares CAP"
```

Le PDF est enregistré dans le dossier `kbc_downloads`.

Les PDF ne sont pas affichés dans l'application. PyMuPDF ajoute les surlignages
directement dans une copie générée en mémoire, sans stockage permanent. Cette copie
reste un PDF standard compatible avec Edge, Chrome et Adobe Reader.

### Documents AG

Pour AG, l'application consulte le catalogue public MuMa, sélectionne le fonds par son
nom, puis télécharge automatiquement son document d'informations clés (KID). Comme
pour Vivium, Athora et NN, un nom partiel unique est accepté. Le téléchargeur peut aussi
être utilisé en ligne de commande :

```bash
python -m competition_analysis.downloaders.ag --channel broker --fund "AG Life Optitrack Equities"
python -m competition_analysis.downloaders.ag --channel bank --fund "AG Life Smart Future Defensive"
python -m competition_analysis.downloaders.ag --channel bank --fund "AG Life Smart Future Defensive" --plan "Smart Fund Plan Private"
```

### Extraction de la date de version avec IA

Après avoir chargé un document, clique sur
**Extraire les informations et préparer le PDF surligné (IA)**.
L'application extrait d'abord le texte du PDF localement, puis envoie ce texte à
`gpt-5-mini` afin d'identifier une date de version explicite, la durée de détention
recommandée, la réduction du rendement correspondante ainsi que les frais de gestion
et de transaction, sous forme d'un pourcentage ou d'un intervalle de pourcentages.
Les passages repérés sont ensuite surlignés
directement dans la copie PDF téléchargeable.

Chaque onglet affiche dès le départ un champ de nom de fonds prérempli pour chacune
de ses entités. Modifie les noms directement, puis récupère les documents et extrais
toutes leurs informations en un seul clic. Plusieurs fonds d'une même entité peuvent
être ajoutés grâce au bouton dédié, qui crée un champ par fonds. Le tableau de résultats
centralise la date détectée, la durée de détention recommandée, la réduction du
rendement associée, les frais de gestion, les frais de transaction et la confiance.
Lorsque le tableau de performances propose
plusieurs périodes, l'extraction retient la plus longue et la réduction du rendement
de sa même colonne. Les PDF originaux et leurs versions surlignées sont téléchargeables
directement sous le tableau des résultats.

### Importer une sélection CSV

Dans chaque onglet, il est aussi possible d'importer un fichier CSV. Il doit
contenir une ligne par fonds, avec les colonnes `entity` et `fund name` (ou
`name of the fund`). Une colonne `document URL` peut être ajoutée pour fournir
directement le PDF :

```csv
entity,fund name,document URL
Allianz,Document d’informations clés Allianz ActiveInvest,
AG,AG Life Optitrack Equities,https://example.org/documents/ag-optitrack.pdf
Vivium,Euro Corporate SRI Bonds,
AG,AG Life Optitrack Defensive,
Baloise,Global Equity Fund,
NN,NN Blackrock Global Allocation Fund,
```

Le fichier est validé par rapport à l'onglet actif : `AG`, `Allianz`, `Vivium`,
`Athora`, `Baloise` et `NN` pour **Broker channel**, ou `AG`, `Belfius` et `KBC` pour
**Bank channel**. Après validation,
l'import remplit directement les champs correspondants : aucun tableau de sélection
supplémentaire n'est affiché. Une même entité peut apparaître plusieurs fois avec des
fonds différents ; un champ est créé pour chacun de ses fonds.

Chaque fonds dispose également d'un champ **Direct document URL**. Lorsqu'il est
renseigné, l'application télécharge cette URL et ne lance pas la recherche du
document sur base du nom du fonds. Le nom reste utilisé comme libellé dans les
résultats et pour construire un nom de fichier si l'URL n'en contient pas.

Les liens source de chaque entité sont affichés au-dessus de l'import CSV. Ils peuvent
être remplacés par une autre page catalogue avant l'extraction ; le téléchargeur utilise
alors cette nouvelle URL pour récupérer les documents.

N'enregistre pas la clé dans le projet. Utilise une nouvelle clé (une clé partagée
dans une conversation doit être révoquée), soit dans
`.streamlit/secrets.toml` :

```toml
OPENAI_API_KEY="ta_nouvelle_cle"
```

soit au lancement :

```bash
export OPENAI_API_KEY="ta_nouvelle_cle"
streamlit run src/competition_analysis/app.py
```
