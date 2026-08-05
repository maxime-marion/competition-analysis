# Extraction des documents Allianz

Ce script ouvre le centre de documents Allianz, sélectionne automatiquement :

1. Catégorie : `Investissement`
2. Le premier produit disponible (actuellement `Allianz Activeinvest`)
3. Type de document : `Document d’informations clés`

Puis il affiche les titres trouvés dans le terminal.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Exécution

```bash
python allianz_documents.py
```

Le site est une application dynamique : Playwright est donc préférable à `requests` seul, car il exécute le JavaScript et interagit avec les listes déroulantes Angular.

## Téléchargement d'un DIC Vivium

Vivium expose directement les PDF dans le HTML de sa page. Aucun navigateur n'est nécessaire :

```bash
python vivium_download.py
```

Par défaut, le script télécharge le DIC « Euro Corporate SRI Bonds ». Pour choisir un autre fonds :

```bash
python vivium_download.py --fund "Stability Fund"
```

Le PDF est enregistré dans le dossier `vivium_downloads`. À chaque exécution, le script relit la page Vivium afin de récupérer l'URL la plus récente du document.

## Téléchargement d'un document Profilife Athora

Le script Athora cible la rubrique `Documents d’Informations Spécifiques`, puis l'accordéon `Fonds branche 23 - Profilife` :

```bash
python athora_download.py
```

Par défaut, il télécharge le document du fonds `Athora DNCA Invest Beyd Semperosa A`. Pour choisir un autre fonds Profilife :

```bash
python athora_download.py --fund "Athora Pictet Gbl Megatrend Select P"
```

Le PDF est enregistré dans le dossier `athora_downloads`. Le script relit la page Athora à chaque exécution afin de suivre une éventuelle modification de l'URL du document.

## Téléchargement d'un document NN Strategy branche 23

Le script NN cible la section néerlandaise `Voor niet-fiscale producten NN Strategy (tak 23)` :

```bash
python nn_download.py
```

Par défaut, il télécharge le document essentiel du fonds `NN Blackrock Global Allocation Fund`. Pour choisir un autre document :

```bash
python nn_download.py --document "NN Fidelity world Fund"
```

Le PDF est enregistré dans le dossier `nn_downloads`. Le script relit la page NN à chaque exécution afin de récupérer l'URL et le jeton publics actuellement associés au document.

## Application Streamlit

L'application regroupe les téléchargeurs Vivium, Athora, NN et AG dans une interface
unique. Saisis un fonds, clique sur le bouton de récupération, puis télécharge le
document original ou sa copie surlignée :

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

Le portail Allianz reste accessible depuis l'onglet dédié, mais son téléchargement automatisé n'est pas encore activé car le site bloque les navigateurs automatisés.

Les PDF ne sont pas affichés dans l'application. PyMuPDF ajoute les surlignages
directement dans une copie générée en mémoire, sans stockage permanent. Cette copie
reste un PDF standard compatible avec Edge, Chrome et Adobe Reader.

### Documents AG

Pour AG, l'application consulte le catalogue public MuMa, sélectionne le fonds par son
nom, puis télécharge automatiquement son document d'informations clés (KID). Comme
pour Vivium, Athora et NN, un nom partiel unique est accepté. Le téléchargeur peut aussi
être utilisé en ligne de commande :

```bash
python ag_download.py --fund "AG Life Optitrack Equities"
```

### Extraction de la date de version avec IA

Après avoir chargé un document, clique sur
**Extraire les informations et préparer le PDF surligné (IA)**.
L'application extrait d'abord le texte du PDF localement, puis envoie ce texte à
`gpt-5-mini` afin d'identifier une date de version explicite, la durée de détention
recommandée et la réduction du rendement correspondante. Les passages repérés sont
ensuite surlignés directement dans la copie PDF téléchargeable.

L'onglet **Global** permet d'importer une sélection de fonds, puis de les récupérer
et d'extraire toutes leurs dates en un seul clic. Le tableau centralise la date
détectée, la durée de détention recommandée, la réduction du rendement associée et
la confiance. Lorsque le tableau de performances propose plusieurs périodes,
l'extraction retient la plus longue et la réduction du rendement de sa même colonne.
Les PDF originaux et leurs versions surlignées sont téléchargeables directement sous
le tableau des résultats.

### Importer une sélection CSV

Dans l'onglet **Global**, il est aussi possible d'importer un fichier CSV. Il doit
contenir une ligne par fonds, avec les colonnes `entity` et `fund name` (ou
`name of the fund`) :

```csv
entity,fund name
AG,AG Life Optitrack Equities
Vivium,Euro Corporate SRI Bonds
AG,AG Life Optitrack Defensive
NN,NN Blackrock Global Allocation Fund
```

Les entités prises en charge sont `AG`, `Vivium`, `Athora` et `NN`. L'application
affiche et valide la sélection importée avant d'activer l'extraction. Une même entité
peut apparaître plusieurs fois avec des fonds différents.

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
streamlit run app.py
```
