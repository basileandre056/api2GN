# 🛠️ Fiche Technique – Parser Pl@ntNet pour GeoNature

Ce document décrit la structure interne, les mécanismes techniques et les extensions possibles du parser **PlantNetParser** destiné à GeoNature.

---

# 1. Architecture générale

Le parser repose sur :
- **JSONParser** (hérité de `Parser`)
- **GeometryMixin** (projection / géométrie)
- **NomenclatureMixin** (résolution des nomenclatures SINP)
- Une configuration spécifique dans `var/config/parsers_plantnet.py`

Le flux général :

```
GeoNature CLI → ParserModel → PlantNetParser → API PlantNet → Transformations → Synthese
```

---

# 2. Méthodes clés

## `next_row()`
- Effectue l’appel HTTP POST vers l’API PlantNet.
- Récupère une liste d’occurrences.
- Transforme chaque bloc JSON en dictionnaire exploitable.

## `build_object()`
Construit une instance `Synthese` :

1. Injecte :
   - **constant_fields**
   - **dynamic_fields**
   - **mapping**  
2. Gère `additional_data`
3. Génère la **géométrie** via `GeometryMixin`
4. Retourne un modèle SQLAlchemy prêt à être inséré

---

# 3. Résolution du `cd_nom`

## Normalisation :
```
"Thunbergia fragrans Roxb." → "Thunbergia fragrans"
```

## Recherche :
1. TAXREF local → via SQLAlchemy + nom simplifié
2. TAXREF-LD → API en ligne
3. Vérification que le cd_nom LD existe bien en base
4. Mise en cache `_CD_NOM_CACHE`

⚠️ Si aucun taxon trouvé : l’observation peut être importée sans cd_nom.

---

# 4. Géométrie et projections

Input : (lon, lat) en WGS84 (4326)

Transformations :

```
raw → POINT(4326) → the_geom_4326  
                      ↓ ST_Transform  
                 the_geom_local (2975)
```

Effectué via :
```python
from_shape(Point(lon, lat), srid=self.srid)
```
puis :
```python
self.fill_dict_with_geom()
```

---

# 5. Auto-création des métadonnées

Dans `_auto_setup_metadata()` :

### Source
Création via SQL brut (GN 2.13 ne possède pas le modèle Python).

### Cadre d’acquisition
Création ou récupération via `TAcquisitionFramework`.

### Dataset
Création ou récupération via `TDatasets`.

Ces trois éléments alimentent :
```python
constant_fields["id_source"]
constant_fields["id_dataset"]
```

---

# 6. Gestion des imports

## Sécurité
- Mode dry-run (`--dry-run`)
- Gestion fine des erreurs
- Historisation dans `ParserModel`

## Historique stocké :
- `last_import`
- `nb_row_last_import`
- `nb_row_total`

---

# 7. Extensibilité du parser

## Ajouter un filtre API
```python
api_filters = {"scientificName": "..."}
```

## Surveiller plusieurs zones
Créer plusieurs classes héritées de `PlantNetParser`.

## Ajouter des champs additionnels
Modifier :
```python
additionnal_fields = { "media": "associatedMedia" }
```

## Gérer plusieurs géométries
Réimplémenter `get_geom()` si besoin.

---

# 8. Fichiers concernés

| Fichier | Rôle |
|--------|------|
| `api2gn/plantnet_parser.py` | Core du parser |
| `api2gn/var/config/parsers_plantnet.py` | Configuration de l’instance Réunion |
| `api2gn/mixins.py` | Géométrie + nomenclatures |
| `api2gn/schema.py` | Validation du mapping |
| `api2gn/models.py` | ParserModel (historique) |

---

# 9. Bonnes pratiques de développement

- **Toujours activer dry-run lors des tests**
- **Vérifier l’existence des noms scientifiques** avant import massif
- **Utiliser le cache cd_nom** pour éviter 200 requêtes SQL
- **Logger explicitement** les cas problématiques :
  - cd_nom absent
  - géométrie absente
  - mapping incomplet

---

# 10. Points sensibles

- L’API PlantNet peut renvoyer des espèces synonymes → TAXREF-LD indispensable.
- Les modèles SQL GeoNature évoluent d’une version à l’autre.
- La gestion des géométries dépend du SRID local (`ref_geo.get_local_srid()`).

---

Fin de la fiche technique développeurs.
