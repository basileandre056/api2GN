# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify
from geonature.utils.config import config as gn_config

from api2gn.validation import validate_plantnet_config
from api2gn.cli import parser_cli   # 👈 IMPORT ICI

blueprint = Blueprint(
    "api2gn",
    __name__,
    url_prefix="/api/api2gn"
)

# ------------------------------------------------------------------
# CLI HISTORIQUE : geonature parser ...
# ------------------------------------------------------------------

blueprint.cli.add_command(parser_cli)

# Admin + Celery (OBLIGATOIRE)
from api2gn.admin import *        # noqa
from api2gn.tasks import setup_periodic_tasks  # noqa


@blueprint.route("/config", methods=["GET"])
def get_api2gn_config():
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
