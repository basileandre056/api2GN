from marshmallow import Schema, fields


class Api2GNSchema(Schema):
    """
    Schéma de configuration API2GN.

    - Si aucun fichier api2gn_config.toml → OK (dict vide)
    - Si fichier présent → les clés sont chargées
    - La validation métier est faite ailleurs (parser / endpoint)
    """

    # --------------------------------------------------
    # Paramètres génériques du module
    # --------------------------------------------------
    PARSER_NUMBER_OF_TRIES = fields.Integer(
        required=False, missing=5
    )
    PARSER_RETRY_SLEEP_TIME = fields.Integer(
        required=False, missing=5
    )
    PARSER_RETRY_HTTP_STATUS = fields.List(
        fields.Integer(),
        required=False,
        missing=lambda: [503],
    )

    # --------------------------------------------------
    # 🔹 CONFIG PLANTNET (BACKEND UNIQUEMENT)
    # --------------------------------------------------
    
    plantnet_api_url = fields.String(
        required=False, allow_none=True
    )
    
    plantnet_api_key = fields.String(
        required=False, allow_none=True
    )
    
    plantnet_taxref_mode = fields.String(
        required=False, missing="strict"
    )
    
    plantnet_max_data = fields.Integer(
        required=False, missing=1000
    )
    
    plantnet_empty_species_list = fields.Boolean(
        required=False, missing=False
    )
    
    list_species = fields.List(
        fields.String(),
        required=False,
        missing=list
    )
    
    plantnet_min_event_date = fields.String(
        required=False, allow_none=True
    )
    
    plantnet_max_event_date = fields.String(
        required=False, allow_none=True
    )
    
    plantnet_geometry_type = fields.String(
        required=False, missing="Polygon"
    )
    
    plantnet_geometry_coordinates_json = fields.String(
        required=False, allow_none=True
    )
    
    plantnet_mapping_json = fields.String(
        required=False, allow_none=True
    )
