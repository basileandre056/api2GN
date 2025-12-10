# 📘 Documentation Utilisateur – Parser Pl@ntNet (GeoNature)

Le parser **Pl@ntNet Réunion** permet d’importer automatiquement dans GeoNature les observations issues de l’API Pl@ntNet, filtrées par espèce, date et emprise géographique.

---

## 🎯 Objectif du parser

Ce parser récupère des observations botaniques depuis l’API Pl@ntNet et les insère dans la Synthèse de GeoNature, en les harmonisant selon les règles du SINP.

---

## 🚀 Comment utiliser ce parser ?

### 1. Vérifier qu’il apparaît dans GeoNature
```
geonature parser list
```
Vous devez voir :
```
🌵 PLANTNET_REUNION - Observations Pl@ntNet sur l'emprise Réunion
```

### 2. Lancer un import en mode test (aucune insertion)
```
geonature parser run PLANTNET_REUNION --dry-run
```

### 3. Lancer l’import réel
```
geonature parser run PLANTNET_REUNION
```

GeoNature affichera :
- la création ou détection automatique de la *source*, du *framework* et du *dataset*  
- les lignes importées  
- les éventuels taxons non trouvés dans TAXREF  

---

## 🗺 Emprise géographique

Le parser est configuré pour **La Réunion** via un polygone GeoJSON défini dans `parsers_plantnet.py`.

---

## 🌱 Espèces importées

La liste est configurable :
```python
EXAMPLE_SPECIES = [
    "Thunbergia fragrans Roxb.",
    "Aciotis purpurascens (Aubl.) Triana",
    ...
]
```

Vous pouvez :
- mettre une liste → import filtré
- laisser vide → import de toutes les espèces retournées par Pl@ntNet

---

## 📅 Filtrage par dates

Exemple :
```python
min_event_date = "2024-01-01"
max_event_date = None
```

---

## 🧭 Correspondances de champs (mapping)

Le parser convertit les données Pl@ntNet vers les champs GeoNature.  
Exemple :
- `eventDate` → `date_min` et `date_max`
- `basisOfRecord` → nomenclature GeoNature
- `media.medium_url` → `associatedMedia` (dans `additional_data`)

---

## 🏷 Gestion du nom scientifique (cd_nom)

Le parser :
1. normalise le nom (“Genre espèce”)  
2. cherche dans TAXREF local  
3. utilise TAXREF-LD en ligne en fallback  
4. met en cache les résultats pour accélérer  

Les observations sans `cd_nom` sont **importées mais sans taxon renseigné**, et signalées dans la console.

---

## 🌐 Géométrie

La géométrie est :
- extraite de `decimalLatitude` + `decimalLongitude`,
- convertie en **POINT 4326**,
- reprojetée en **2975** pour remplir `the_geom_local`.

---

## 📥 Résultat

Le parser insère dans :
```
gn_synthese.synthese
```
avec :
- géométrie locale + 4326  
- champs SINP normalisés  
- image Pl@ntNet dans `additional_data.associatedMedia`  

---

## ✔ Ce que fait automatiquement le parser

- Crée la source Pl@ntNet si absente  
- Crée le cadre d’acquisition  
- Crée le dataset  
- Gère le mapping et les nomenclatures  
- Gère la projection et les géométries  
- Normalise et résout les noms scientifiques  
- Affiche les taxons inconnus  

---

## 🆘 Dépannage

### Aucun cd_nom trouvé ?
→ Ajouter l’espèce dans TAXREF local ou corriger le nom scientifique.

### Trop peu d’observations ?
→ Tester sans filtre d’espèces.

### La géométrie manque ?
→ Vérifier que l’observation Pl@ntNet contient bien `decimalLatitude` et `decimalLongitude`.

---

## ✨ Pour modifier le parser

Modifier :
- l’emprise → `REUNION_POLYGON`
- les espèces → `EXAMPLE_SPECIES`
- les dates → `min_event_date`
- le mapping → attribut `mapping` du parser

---

Fin de la documentation utilisateur.
