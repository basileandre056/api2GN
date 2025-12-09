from api2gn.parsers import JSONParser

class MonPremierParser(JSONParser):
    name = "mon_premier_parser"
    url = "https://exemple.com/api"  # à remplacer

    mapping = {
        "cd_nom": "cd_nom_source",
        "date_min": "date_start",
        "date_max": "date_end",
    }

    constant_fields = {
        "id_source": 1,  # à adapter
        "id_dataset": 2, # à adapter
    }

PARSERS = [MonPremierParser]
