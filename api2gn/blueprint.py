# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify
from geonature.utils.config import config as gn_config

# CLI
from api2gn.commands import cmd_list_parsers, run

# Validation
from api2gn.validation import validate_plantnet_config

# ------------------------------------------------------------------
# Blueprint principal API2GN
# ------------------------------------------------------------------

blueprint = Blueprint(
    "api2gn",
    __name__,
    url_prefix="/api/api2gn"
)

# ------------------------------------------------------------------
# CLI GeoNature
# ------------------------------------------------------------------

blueprint.cli.add_command(cmd_list_parsers)
blueprint.cli.add_command(run)

# ------------------------------------------------------------------
# Admin + Celery (imports obligatoires)
# ------------------------------------------------------------------

from api2gn.admin import *        # noqa: F401,F403
from api2gn.tasks import setup_periodic_tasks  # noqa: F401


# ------------------------------------------------------------------
# Endpoint de configuration (comme Quadrige / ZH)
# ------------------------------------------------------------------

@blueprint.route("/config", methods=["GET"])
def get_api2gn_config():
    """
    Retourne la configuration API2GN.

    - Si api2gn_config.toml absent → warning + config={}
    - Si présent → validation métier non bloquante
    """
    cfg = gn_config.get("API2GN")

    if not cfg:
        return jsonify({
            "status": "warning",
            "message": (
                "Aucune configuration API2GN chargée. "
                "Le fichier api2gn_config.toml est absent ou vide."
            ),
            "config": {}
        }), 200

    warnings = validate_plantnet_config(cfg)

    if warnings:
        return jsonify({
            "status": "warning",
            "message": "La configuration API2GN comporte des incohérences.",
            "warnings": warnings,
            "config": cfg,
        }), 200

    return jsonify({
        "status": "ok",
        "config": cfg
    }), 200
