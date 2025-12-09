import json
from typing import Dict, Any, List, Optional

import click
import requests
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from sqlalchemy import select

from geonature.utils.env import db
from geonature.core.gn_meta.models import TDatasets, TAcquisitionFramework, TSources


# Fallback TAXREF : on suppose que le modèle Taxref existe
try:
    from apptax.taxonomie.models import Taxref
except ImportError:
    Taxref = None

from api2gn.parsers import JSONParser

# -------------------------------------------------------------------
#  Config "basisOfRecord" 
#  -> on l'utilise pour normaliser la valeur et la stocker
#     dans additional_data["basisOfRecord"]
# -------------------------------------------------------------------
BASIS_OF_RECORD_MAP: Dict[str, str] = {
    "human_observation": "HUMAN_OBSERVATION",
    "observation": "OBSERVATION",
    "machine_observation": "MACHINE_OBSERVATION",
    "preserved_specimen": "PRESERVED_SPECIMEN",
    "living_specimen": "LIVING_SPECIMEN",
    "material_sample": "MATERIAL_SAMPLE",
    "photograph": "HUMAN_OBSERVATION",
    "photo": "HUMAN_OBSERVATION",
    "image": "MACHINE_OBSERVATION",
}


def _build_observers(row: Dict[str, Any]) -> Optional[str]:
    """
    Concat rightsHolder et user.id dans observers :
       'Carole elorac (104850711)'
    """
    rights = row.get("rightsHolder")
    user_id = row.get("user_id")
    if rights and user_id:
        return f"{rights} ({user_id})"
    if rights:
        return rights
    if user_id:
        return str(user_id)
    return None


def _resolve_cd_nom(row: Dict[str, Any]) -> Optional[int]:
    """
    Fallback TAXREF simple :
      SELECT cd_nom FROM taxref WHERE lb_nom ILIKE scientificName LIMIT 1
    """
    if Taxref is None:
        # modèle non disponible → on ne bloque pas l'import
        return None

    sci = row.get("scientificName")
    if not sci:
        return None

    try:
        cd_nom = db.session.scalar(
            select(Taxref.cd_nom).where(Taxref.lb_nom.ilike(sci)).limit(1)
        )
        if not cd_nom:
            click.secho(f"[PlantNet] Aucun cd_nom pour '{sci}'", fg="yellow")
        return cd_nom
    except Exception as e:
        click.secho(f"[PlantNet] Erreur résolution cd_nom : {e}", fg="red")
        return None


class PlantNetParser(JSONParser):
    """
    Parser générique Pl@ntNet pour API2GN.

    Principe :
      - Appel POST sur /v3/dwc/occurrence/search
      - Lecture des occurrences dans results[]
      - Conversion → lignes "plates" consommées par JSONParser.build_object()
      - Mapping vers la Synthèse :
          * nom_cite       ← scientificName
          * date_min/max   ← eventDate
          * entity_source_pk_value ← id
          * observers      ← rightsHolder (user.id)
          * cd_nom         ← fallback TAXREF(lb_nom = scientificName)
          * associatedMedia ← medium_url (additional_data["associatedMedia"])
    """

    srid = 4326
    progress_bar = False

    # Endpoint DWC search
    url = "https://my-api.plantnet.org/v3/dwc/occurrence/search"

    # ⚠ Clé API fournie (à déplacer plus tard en config GN)
    API_KEY = "2b10IJGxpcJr54FjXELjEVJI1O"

    # Paramètres Pl@ntNet par défaut (surchargeables dans une sous-classe)
    #  -> tu pourras définir ça dans ton parser concret dans var/config/parsers.py
    geometry: Optional[Dict[str, Any]] = None   # GeoJSON Polygon
    scientific_names: List[str] = []            # Liste de noms scientifiques
    min_event_date: Optional[str] = None        # "YYYY-MM-DD"
    max_event_date: Optional[str] = None        # "YYYY-MM-DD"

    # Mapping vers la Synthèse (colonnes "simples")
    mapping = {
        "nom_cite": "scientificName",
        "date_min": "eventDate",
        "date_max": "eventDate",
        "entity_source_pk_value": "id",
    }

    # ⚠ A ADAPTER dans ton instance :
    #    id_source : source Pl@ntNet
    #    id_dataset : JDD associé
    constant_fields = {
        "id_source": 16,   # TODO: mettre l'id_source réel Pl@ntNet
        "id_dataset": 705, # TODO: mettre l'id_dataset réel
        "count_min": 1,
        "count_max": 1,
    }

    # Champs calculés dynamiquement
    dynamic_fields = {
        # observers = 'rightsHolder (user.id)'
        "observers": _build_observers,
        # cd_nom fallback TAXREF
        "cd_nom": _resolve_cd_nom,
    }

    # Champs stockés dans additional_data
    # -> JSONParser.build_object va faire :
    #    additional_data["associatedMedia"] = row["associatedMedia"]
    #    additional_data["basisOfRecord"]  = row["basisOfRecord_norm"]
    #
    # ⚠ repère : associatedMedia = medium_url Pl@ntNet
    additionnal_fields = {
        "associatedMedia": "associatedMedia",
        "basisOfRecord": "basisOfRecord_norm",
    }

    def __init__(self, dry_run=False):
        self.dry_run = dry_run

        super().__init__()

        # Auto création de la source et du dataset
        self._auto_setup_metadata()
    

    def _auto_setup_metadata(self):
        """
        Create or get:
        - Source 'Pl@ntNet'
        - Acquisition framework 'Pl@ntNet'
        - Dataset 'Pl@ntNet – La Réunion'

        Then update constant_fields with the IDs.
        """

        # --- SOURCE ---
        source = db.session.execute(
            select(TSources).where(TSources.name_source == "Pl@ntNet")
        ).scalar()

        if not source:
            source = TSources(
                name_source="Pl@ntNet",
                desc_source="Import automatique via API Pl@ntNet"
            )
            db.session.add(source)
            if not self.dry_run:
                db.session.commit()
            click.secho("✔ Source 'Pl@ntNet' créée", fg="green")
        else:
            click.secho("✔ Source 'Pl@ntNet' existante", fg="blue")

        # --- ACQUISITION FRAMEWORK ---
        af = db.session.execute(
            select(TAcquisitionFramework)
            .where(TAcquisitionFramework.acquisition_framework_name == "Pl@ntNet")
        ).scalar()

        if not af:
            af = TAcquisitionFramework(
                acquisition_framework_name="Pl@ntNet",
                acquisition_framework_desc="Cadre d'acquisition Pl@ntNet"
            )
            db.session.add(af)
            if not self.dry_run:
                db.session.commit()
            click.secho("✔ Acquisition Framework 'Pl@ntNet' créé", fg="green")
        else:
            click.secho("✔ Acquisition Framework 'Pl@ntNet' existant", fg="blue")

        # --- DATASET ---
        dataset = db.session.execute(
            select(TDatasets)
            .where(TDatasets.dataset_name == "Pl@ntNet – La Réunion")
        ).scalar()

        if not dataset:
            dataset = TDatasets(
                dataset_name="Pl@ntNet – La Réunion",
                dataset_shortname="PlantNet974",
                dataset_desc="Observations Pl@ntNet sur La Réunion",
                id_acquisition_framework=af.id_acquisition_framework,
                terrestrial_domain=True,
                marine_domain=False
            )
            db.session.add(dataset)
            if not self.dry_run:
                db.session.commit()
            click.secho("✔ Dataset 'Pl@ntNet – La Réunion' créé", fg="green")
        else:
            click.secho("✔ Dataset 'Pl@ntNet – La Réunion' existant", fg="blue")

        # --- Update constant_fields ---
        self.constant_fields["id_source"] = source.id_source
        self.constant_fields["id_dataset"] = dataset.id_dataset

        click.secho(
            f"✔ id_source={source.id_source}, id_dataset={dataset.id_dataset} mis à jour",
            fg="yellow"
        )
    

    def _build_payload(self) -> Dict[str, Any]:
        """
        Construit le corps JSON envoyé à l’API Pl@ntNet.
        On reprend la logique de tes curl :
          - scientificName : liste de taxons
          - geometry : Polygon GeoJSON
          - minEventDate / maxEventDate
        """
        payload: Dict[str, Any] = {}

        if self.scientific_names:
            payload["scientificName"] = self.scientific_names

        if self.geometry:
            payload["geometry"] = self.geometry

        if self.min_event_date:
            payload["minEventDate"] = self.min_event_date
        if self.max_event_date:
            payload["maxEventDate"] = self.max_event_date

        return payload

    def _call_api(self) -> List[Dict[str, Any]]:
        """
        Appel POST unique à Pl@ntNet (sans pagination pour l’instant),
        avec body JSON et api-key en query string.
        """
        params = {"api-key": self.API_KEY}
        payload = self._build_payload()

        click.secho("[PlantNet] Appel API Pl@ntNet /dwc/occurrence/search", fg="blue")

        resp = requests.post(
            self.url,
            params=params,
            json=payload,
            timeout=(10, 90),
        )
        if resp.status_code != 200:
            click.secho(
                f"[PlantNet] Erreur HTTP {resp.status_code} : {resp.text[:200]}",
                fg="red",
            )
            raise click.ClickException("Erreur API Pl@ntNet")

        data = resp.json()
        self.root = data
        results = data.get("results", []) or data.get("data", [])
        if not results:
            click.secho("[PlantNet] Aucun résultat (results[] vide)", fg="yellow")
        return results

    def get_geom(self, row: Dict[str, Any]):
        """
        Surcharge JSONParser.get_geom :
        - utilise decimalLatitude / decimalLongitude
        - retourne un WKB via from_shape
        """
        lat = row.get("decimalLatitude")
        lon = row.get("decimalLongitude")
        if lat is None or lon is None:
            click.secho("[PlantNet] Pas de coordonnées, géométrie ignorée", fg="yellow")
            return None
        try:
            pt = Point(lon, lat)
            return from_shape(pt, srid=self.srid)
        except Exception as e:
            click.secho(f"[PlantNet] Erreur geom : {e}", fg="red")
            return None

    def next_row(self, page: int = 0):
        """
        Implémentation spécifique :
          - 1 appel POST à l’API
          - on "aplatit" chaque résultat en un dict simple,
            consommable par JSONParser.build_object()
        """
        results = self._call_api()
        self.counter = 0

        for rec in results:
            self.counter += 1

            # extraction medium_url
            media_list = rec.get("media") or []
            medium_url = None
            if media_list:
                medium_url = media_list[0].get("medium_url")

            # normalisation basisOfRecord
            bor_raw = (rec.get("basisOfRecord") or "").strip()
            bor_norm = BASIS_OF_RECORD_MAP.get(bor_raw.lower(), bor_raw)

            row: Dict[str, Any] = {
                "id": rec.get("id"),
                "scientificName": rec.get("scientificName"),
                "eventDate": rec.get("eventDate") or rec.get("observedOn"),
                "decimalLatitude": rec.get("decimalLatitude"),
                "decimalLongitude": rec.get("decimalLongitude"),
                "rightsHolder": rec.get("rightsHolder"),
                "user_id": (rec.get("user") or {}).get("id"),
                # ⚠ repère : associatedMedia = medium_url Pl@ntNet
                "associatedMedia": medium_url,
                "basisOfRecord_norm": bor_norm,
            }

            yield row

    @property
    def total(self) -> int:
        """
        Nombre total d’items — utile si un jour tu actives progress_bar.
        Ici : on renvoie le nombre de résultats de l’appel courant.
        """
        try:
            results = self.root.get("results", []) or self.root.get("data", [])
            return len(results)
        except Exception:
            return 0
