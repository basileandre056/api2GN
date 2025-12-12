Document de synthèse – non destiné à la configuration ou au développement

# Résumé du Parser PlantNet -- Documentation Synthétique

## 🔍 Objectif général

Le parser PlantNet permet d'interroger automatiquement l'API Pl@ntNet,
de nettoyer et normaliser les données reçues, de résoudre les taxons
(`cd_nom`), et d'insérer les observations dans la Synthèse GeoNature,
tout en restant compatible avec GeoNature 2.13.

------------------------------------------------------------------------

## 🧩 Fonctionnement global

### 1. **Configuration automatique GeoNature**

Le parser : - crée ou récupère la Source Pl@ntNet, - crée ou récupère le
Cadre d'acquisition, - crée ou récupère le Dataset « Pl@ntNet -- La
Réunion ».

Aucune configuration préalable n'est nécessaire dans l'interface GN.

------------------------------------------------------------------------

### 2. **Interrogation de l'API Pl@ntNet**

Le parser appelle :

    POST /dwc/occurrence/search

Avec les paramètres : - *scientificName* (optionnel), - *geometry*
(polygone de La Réunion), - *minEventDate* / *maxEventDate*.

------------------------------------------------------------------------

### 3. **Normalisation des données reçues**

Le parser nettoie : - basisOfRecord → standardisation via table de
correspondance, - scientificName (suppression auteurs/Ssp), - géométrie
→ conversion en WKB.

Il extrait aussi automatiquement : - dates, - coordonnées, - médias, -
identifiants utilisateur.

------------------------------------------------------------------------

## 🌱 Résolution du `cd_nom` (TAXREF)

Le pipeline de résolution fonctionne ainsi :

1.  **Consultation du cache mémoire** (évite redondances)
2.  **Normalisation botanique** → "Genre espèce"
3.  **Recherche dans TAXREF local**
4.  Si absent → requête TAXREF-LD (API MNHN)
5.  **Validation** que le cd_nom existe en local
6.  En cas d'échec → log + cd_nom = NULL

➡️ Cette partie est robuste et optimise énormément les performances.

------------------------------------------------------------------------

## 🗺 Gestion des géométries

Le parser génère automatiquement : - `the_geom_4326` - `the_geom_local`
(SRID 2975) - `the_geom_point` (centroid)

Grâce au `GeometryMixin` d'API2GN.

------------------------------------------------------------------------

## 📥 Insertion dans la Synthèse

Pour chaque enregistrement :

-   Construction d'un objet **Synthese()**
-   Injection des champs :
    -   mapping,
    -   constant_fields,
    -   dynamic_fields (dont cd_nom),
    -   `additional_data` (médias, basisOfRecord)
-   Commit final (ou dry-run)
-   Mise à jour de l'historique du parser

------------------------------------------------------------------------

## 🚀 Commandes utiles

Dry-run :

    geonature parser run PLANTNET_REUNION --dry-run

Import réel :

    geonature parser run PLANTNET_REUNION

------------------------------------------------------------------------

## ✔ Points forts

-   Résolution des taxons très poussée\
-   Cache cd_nom pour accélération massive\
-   Auto-configuration complète GeoNature\
-   Compatibilité GeoNature 2.13\
-   Code propre, robuste, logué intelligemment
