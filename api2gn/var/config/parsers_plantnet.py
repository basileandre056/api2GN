# -*- coding: utf-8 -*-
# api2gn/var/config/parsers_plantnet.py

"""
Déclaration des parseurs PlantNet pour GeoNature.

Toute la configuration (URL, API key, géométrie, espèces, dates, mapping…)
est désormais entièrement gérée dans le fichier :

    api2gn_config.toml

Ce fichier ne fait plus que charger le parser générique et l'exposer à GeoNature.
"""

from api2gn.plantnet_parser import PlantNetParser

# ---------------------------------------------------------------------
# 📌 Parser principal basé sur la configuration TOML
# ---------------------------------------------------------------------

class PlantNetReunion(PlantNetParser):
    """
    Parser PlantNet dynamique.
    Les paramètres (geometry, dates, species…) sont tous chargés
    depuis le fichier api2gn_config.toml.
    """
    name = "PLANTNET_REUNION"            # nom affiché dans GeoNature
    description = "Import dynamique Pl@ntNet (configurable via TOML)"


# ---------------------------------------------------------------------
# 📌 Liste des parseurs à exposer à GeoNature
# ---------------------------------------------------------------------

PARSERS = [PlantNetReunion]
