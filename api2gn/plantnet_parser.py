# -*- coding: utf-8 -*-
#api2gn/plantnet_parser.py


import json
from typing import Dict, Any, List, Optional

import click
import requests
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from sqlalchemy import select, text

from geonature.utils.env import db
from geonature.core.gn_meta.models import TDatasets, TAcquisitionFramework

# ⚠️ TSources N’EXISTE PAS en GN 2.13 → on utilisera SQL brut

# Fallback TAXREF
try:
    from apptax.taxonomie.models import Taxref
except ImportError:
    Taxref = None

from api2gn.parsers import JSONParser

# -------------------------------------------------------------------
# Normalisation basisOfRecord
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
    if Taxref is None:
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
        click.secho(f"[PlantNet] Erreur TAXREF : {e}", fg="red")
        return None


class PlantNetParser(JSONParser):


    name = "PLANTNET_REUNION"
    srid = 4326               # SRID source (PlantNet)
    local_srid = 2975        # SRID de la base GeoNature (the_geom_local)

    progress_bar = False

    url = "https://my-api.plantnet.org/v3/dwc/occurrence/search"
    API_KEY = "2b10IJGxpcJr54FjXELjEVJI1O"

    geometry: Optional[Dict[str, Any]] = None
    scientific_names: List[str] = []
    min_event_date: Optional[str] = None
    max_event_date: Optional[str] = None

    mapping = {
        "nom_cite": "scientificName",
        "date_min": "eventDate",
        "date_max": "eventDate",
        "entity_source_pk_value": "id",
    }

    # Valeurs remplacées automatiquement par _auto_setup_metadata()
    constant_fields = {
        "id_source": None,
        "id_dataset": None,
        "count_min": 1,
        "count_max": 1,
    }

    dynamic_fields = {
        "observers": _build_observers,
        "cd_nom": _resolve_cd_nom,
    }

    additionnal_fields = {
        "associatedMedia": "associatedMedia",
        "basisOfRecord": "basisOfRecord_norm",
    }

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        super().__init__()
        self._auto_setup_metadata()

    # ---------------------------------------------------------------------
    # AUTO-CREATION SOURCE / FRAMEWORK / DATASET — VERSION GN 2.13
    # ---------------------------------------------------------------------
    def _auto_setup_metadata(self):

        # -------------------
        # 1. SOURCE (SQL brut)
        # -------------------
        q_source = db.session.execute(text("""
            SELECT id_source FROM gn_synthese.t_sources
            WHERE name_source = 'Pl@ntNet'
        """)).fetchone()

        if q_source:
            id_source = q_source[0]
            click.secho(f"✔ Source Pl@ntNet existante (id={id_source})", fg="blue")
        else:
            if self.dry_run:
                id_source = -1
                click.secho(
                    "⚠ Dry-run : source 'Pl@ntNet' non créée (id_source=-1, pas d’écriture)",
                    fg="yellow",
                )
            else:
                res = db.session.execute(text("""
                    INSERT INTO gn_synthese.t_sources (name_source, desc_source)
                    VALUES ('Pl@ntNet', 'Import API PlantNet')
                    RETURNING id_source
                """))
                id_source = res.fetchone()[0]
                db.session.commit()
                click.secho(f"✔ Source Pl@ntNet créée (id={id_source})", fg="green")

        # -------------------
        # 2. ACQUISITION FRAMEWORK (via modèle GN)
        # -------------------
        af = db.session.scalar(
            select(TAcquisitionFramework).where(
                TAcquisitionFramework.acquisition_framework_name == "Pl@ntNet"
            )
        )

        if not af:
            af = TAcquisitionFramework(
                acquisition_framework_name="Pl@ntNet",
                acquisition_framework_desc="Cadre d'acquisition Pl@ntNet"
            )
            db.session.add(af)
            if not self.dry_run:
                db.session.commit()
            click.secho("✔ Framework Pl@ntNet créé", fg="green")
        else:
            click.secho(f"✔ Framework existant (id={af.id_acquisition_framework})", fg="blue")

        # -------------------
        # 3. DATASET (via modèle GN)
        # -------------------
        dataset = db.session.scalar(
            select(TDatasets).where(
                TDatasets.dataset_name == "Pl@ntNet – La Réunion"
            )
        )

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
            click.secho("✔ Dataset créé", fg="green")
        else:
            click.secho(f"✔ Dataset existant (id={dataset.id_dataset})", fg="blue")

        # -------------------
        # 4. Mise à jour
        # -------------------
        self.constant_fields["id_source"] = id_source
        self.constant_fields["id_dataset"] = dataset.id_dataset

        click.secho(
            f"✔ id_source={id_source}, id_dataset={dataset.id_dataset}",
            fg="yellow"
        )
    # ---------------------------------------------------------------------
    # API call
    # ---------------------------------------------------------------------
    def _build_payload(self):
        payload = {}
        if self.scientific_names:
            payload["scientificName"] = self.scientific_names
        if self.geometry:
            payload["geometry"] = self.geometry
        if self.min_event_date:
            payload["minEventDate"] = self.min_event_date
        if self.max_event_date:
            payload["maxEventDate"] = self.max_event_date
        return payload

    def _call_api(self):
        click.secho("[PlantNet] Appel API /dwc/occurrence/search", fg="blue")

        resp = requests.post(
            self.url,
            params={"api-key": self.API_KEY},
            json=self._build_payload(),
            timeout=(10, 90)
        )

        if resp.status_code != 200:
            click.secho(f"Erreur API : {resp.text[:200]}", fg="red")
            raise click.ClickException("Erreur API PlantNet")

        data = resp.json()
        self.root = data
        return data.get("results", []) or data.get("data", [])

    # ---------------------------------------------------------------------
    # Construction des objets ligne par ligne
    # ---------------------------------------------------------------------
    def get_geom(self, row):
        lat = row.get("decimalLatitude")
        lon = row.get("decimalLongitude")
        if lat is None or lon is None:
            return None
        return from_shape(Point(lon, lat), srid=self.srid)

    def next_row(self, page=0):
        results = self._call_api()
        self.counter = 0

        for rec in results:
            self.counter += 1

            media = rec.get("media") or []
            medium_url = media[0].get("medium_url") if media else None

            bor_raw = (rec.get("basisOfRecord") or "").strip()
            bor_norm = BASIS_OF_RECORD_MAP.get(bor_raw.lower(), bor_raw)

            yield {
                "id": rec.get("id"),
                "scientificName": rec.get("scientificName"),
                "eventDate": rec.get("eventDate") or rec.get("observedOn"),
                "decimalLatitude": rec.get("decimalLatitude"),
                "decimalLongitude": rec.get("decimalLongitude"),
                "rightsHolder": rec.get("rightsHolder"),
                "user_id": (rec.get("user") or {}).get("id"),
                "associatedMedia": medium_url,     # image plantnet
                "basisOfRecord_norm": bor_norm,
            }

    @property
    def total(self):
        try:
            return len(self.root.get("results", []) or self.root.get("data", []))
        except Exception:
            return 0
