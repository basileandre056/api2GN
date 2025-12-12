# -*- coding: utf-8 -*-

import json


def validate_plantnet_config(cfg: dict) -> list[str]:
    """
    Validation métier PlantNet (non bloquante).
    Retourne une liste de warnings lisibles.
    """
    warnings = []

    # --------------------------------------------------
    # API
    # --------------------------------------------------
    if not cfg.get("plantnet_api_url"):
        warnings.append("plantnet_api_url manquant")

    if not cfg.get("plantnet_api_key"):
        warnings.append("plantnet_api_key manquant")

    # --------------------------------------------------
    # Dates
    # --------------------------------------------------
    min_date = cfg.get("plantnet_min_event_date")
    max_date = cfg.get("plantnet_max_event_date")

    if min_date and max_date and min_date > max_date:
        warnings.append(
            "plantnet_min_event_date est postérieure à plantnet_max_event_date"
        )

    # --------------------------------------------------
    # Géométrie
    # --------------------------------------------------
    geom_json = cfg.get("plantnet_geometry_coordinates_json")
    if geom_json:
        try:
            coords = json.loads(geom_json)
            if not isinstance(coords, list):
                warnings.append("plantnet_geometry_coordinates_json doit être une liste")
        except Exception:
            warnings.append("plantnet_geometry_coordinates_json n’est pas un JSON valide")

    # --------------------------------------------------
    # Espèces
    # --------------------------------------------------
    species = cfg.get("example_species")
    if species is not None and not isinstance(species, list):
        warnings.append("example_species doit être une liste de chaînes")

    # --------------------------------------------------
    # Mapping
    # --------------------------------------------------
    mapping_json = cfg.get("plantnet_mapping_json")
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
            if not isinstance(mapping, dict):
                warnings.append("plantnet_mapping_json doit être un objet JSON")
        except Exception:
            warnings.append("plantnet_mapping_json n’est pas un JSON valide")

    return warnings
