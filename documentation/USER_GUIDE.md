
Public cible : administrateurs GeoNature


# 🌵 PLANTNET_REUNION — Interprétation des résultats et configuration

Ce document explique :
- comment interpréter les sorties du parser **PLANTNET_REUNION** ;
- comment configurer finement le parser via le fichier **TOML** ;
- comment ajuster le comportement de l’import (taxons, géométrie, dates, mapping).

---

## 1. Interprétation des résultats de l’import

### Exemple de sortie

```text
[PlantNet] Résumé de l'import :
  ✔ Importées : 93
  ✖ Rejetées  : 7
    ↳ sans cd_nom (mode strict) : 7
```

### ✔ Importées

Ce nombre correspond aux **observations Pl@ntNet effectivement intégrées** (ou simulées en `--dry-run`) dans GeoNature.

Une observation est importée si :
- elle contient des coordonnées valides ;
- elle respecte les filtres définis (taxons, dates, géométrie) ;
- un `cd_nom` TAXREF a pu être résolu (localement ou via TAXREF-LD).

### ✖ Rejetées

Les observations rejetées ne sont **pas insérées** dans GeoNature.

Dans le cas présent :
- **7 observations** ont été rejetées car **aucun `cd_nom` valide** n’a pu être résolu.

### 🔒 Mode strict TAXREF

Le parser fonctionne volontairement en **mode strict** :
- si `cd_nom = NULL` → rejet de l’observation ;
- ceci garantit la cohérence taxonomique avec GeoNature et le SINP.

Les messages suivants indiquent un fallback vers TAXREF-LD :
```text
[PlantNet] Aucun TAXREF local pour 'Impatiens hawkeri W.Bull' → fallback LD
```

Si le taxon :
- n’existe pas en base TAXREF locale ;
- ou n’est pas reconnu par TAXREF-LD ;

➡️ l’observation est rejetée.

---

## 2. Utilisation du fichier de configuration TOML

Le parser **PLANTNET_REUNION** est entièrement piloté par un fichier TOML,
chargé via la clé racine `API2GN`.

### 2.1 Paramètres API

```toml
plantnet_api_url = "https://my-api.plantnet.org/v3/dwc/occurrence/search"
plantnet_api_key = "XXXXXX"
```

- `plantnet_api_url` : endpoint officiel Pl@ntNet (Darwin Core)
- `plantnet_api_key` : clé API personnelle (obligatoire)

---

### 2.2 Taxons interrogés

```toml
plantnet_empty_species_list = false

list_species = [
  "Thunbergia fragrans Roxb.",
  "Aciotis purpurascens (Aubl.) Triana"
]
```

- `plantnet_empty_species_list = true`
  - ➜ aucun filtre taxonomique (requête large)
- `false`
  - ➜ utilisation de `list_species`

⚠️ Une requête sans filtre peut générer **beaucoup de données**.

---

### 2.3 Filtrage temporel

```toml
plantnet_min_event_date = "2024-01-01"
plantnet_max_event_date = ""
```

- format ISO `YYYY-MM-DD`
- chaîne vide = pas de borne

Les dates sont appliquées côté API Pl@ntNet.

---

### 2.4 Géométrie spatiale

```toml
plantnet_geometry_type = "Polygon"

# Coordonnées du polygone de La Réunion (format JSON string)
plantnet_geometry_coordinates_json = """
[
  [
    [55.2793527748355, -20.915228550665972],
    [55.27008417364911, -20.956699600097522],
    [55.272781834306045, -20.990067818924132],
    [55.24154247413543, -21.012828480359914],
    [55.229601308302335, -21.012320811388733],
    [55.20306370884094, -21.03728202564804],
    [55.2090094279888, -21.080223628620047],
    [55.25827859954282, -21.143358510033835],
    [55.274530299783294, -21.158004227477832],
    [55.26803118055358, -21.201419453006835],
    [55.28264247558579, -21.23119747763502],
    [55.316751902044786, -21.27408831927319],
    [55.33353590554157, -21.28720537566896],
    [55.36981100987185, -21.291745622641415],
    [55.39526652661942, -21.30233444107118],
    [55.408251792072065, -21.324027778375992],
    [55.47971989626498, -21.3588225144628],
    [55.602617179716134, -21.39057530426892],
    [55.6432278410189, -21.39613255666528],
    [55.776417030052784, -21.373446069134616],
    [55.818106329059276, -21.34319195017966],
    [55.82331052066087, -21.22161106690031],
    [55.85270968339859, -21.189865462733053],
    [55.85271295622192, -21.148855304979136],
    [55.79296256256757, -21.115423740583253],
    [55.71480245804722, -20.970500886680966],
    [55.69525608822789, -20.927907495081726],
    [55.61707060894801, -20.89138923253705],
    [55.458527809075775, -20.8640016028845],
    [55.397749243333635, -20.87270438232669],
    [55.31410187673734, -20.91979309421808],
    [55.2793527748355, -20.915228550665972]
  ]
]
"""

```