# -*- coding: utf-8 -*-
# api2gn/plantnet_parser.py

import json
import re
from typing import Dict, Any, List, Optional

import click
import requests
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from sqlalchemy import select, text

from geonature.utils.env import db
from geonature.utils.config import config as gn_config
from geonature.core.gn_meta.models import TDatasets, TAcquisitionFramework

from api2gn.parsers import JSONParser


# =============================================================================
# CONFIGURATION API2GN – Chargée exactement comme Quadrige
# =============================================================================

def load_api2gn_config():
    cfg = gn_config.get("API2GN")
    if not cfg:
        click.secho(
            "[API2GN] ⚠ Aucune configuration chargée (api2gn_config.toml absent).",
            fg="yellow"
        )
        return {}
    return cfg




# =============================================================================
# TAXREF RESOLUTION (optimisée + cache)
# =============================================================================

try:
    from apptax.taxonomie.models import Taxref
except ImportError:
    Taxref = None

_CD_NOM_CACHE: Dict[str, Optional[int]] = {}


def normalize_scientific_name(name: str) -> str:
    if not name:
        return name
    name = re.sub(r"\b(subsp\.|var\.|ssp\.|forma)\b.*", "", name, flags=re.IGNORECASE)
    parts = name.split()
    return f"{parts[0]} {parts[1]}" if len(parts) >= 2 else name


def resolve_cd_nom_local(name: str) -> Optional[int]:
    if Taxref is None:
        return None
    try:
        clean = normalize_scientific_name(name)
        return db.session.scalar(
            select(Taxref.cd_nom).where(Taxref.lb_nom.ilike(clean))
        )
    except Exception as e:
        click.secho(f"[TAXREF local] Erreur : {e}", fg="red")
        return None


def resolve_cd_nom_taxref_ld(name: str) -> Optional[int]:
    try:
        r = requests.get(
            "https://taxref.mnhn.fr/api/taxa",
            params={"q": name},
            timeout=4
        )
        data = r.json()
        if isinstance(data, list) and len(data):
            return data[0].get("cd_nom")
    except Exception:
        pass
    return None


def _resolve_cd_nom(row):
    sci = row.get("scientificName")
    if not sci:
        return None

    if sci in _CD_NOM_CACHE:
        return _CD_NOM_CACHE[sci]

    # 1) Local
    cd = resolve_cd_nom_local(sci)
    if cd:
        _CD_NOM_CACHE[sci] = cd
        return cd

    click.secho(f"[PlantNet] Aucun TAXREF local pour '{sci}' → fallback LD", fg="yellow")

    # 2) TAXREF-LD
    cd_ld = resolve_cd_nom_taxref_ld(sci)
    if cd_ld:
        exists = db.session.scalar(select(Taxref.cd_nom).where(Taxref.cd_nom == cd_ld))
        if exists:
            _CD_NOM_CACHE[sci] = cd_ld
            return cd_ld

        click.secho(
            f"[TAXREF-LD] cd_nom={cd_ld} trouvé mais ABSENT en base locale",
            fg="red"
        )

    _CD_NOM_CACHE[sci] = None
    return None


# =============================================================================
# BASIS OF RECORD NORMALISATION
# =============================================================================

BASIS_OF_RECORD_MAP = {
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


def _build_observers(row):
    rights = row.get("rightsHolder")
    user_id = row.get("user_id")
    if rights and user_id:
        return f"{rights} ({user_id})"
    return rights or (str(user_id) if user_id else None)


# =============================================================================
# PARSER PLANTNET – VERSION DYNAMIQUE VIA CONFIG
# =============================================================================

class PlantNetParser(JSONParser):
    """
    Version entièrement dynamique : URL, API KEY, mapping, géométrie,
    listes d'espèces, dates… tout vient du fichier TOML.
    """

    name = "PLANTNET"
    srid = 4326
    local_srid = 2975
    progress_bar = False

    dynamic_fields = {
        "observers": _build_observers,
    }

    additionnal_fields = {
        "associated_media": "associatedMedia",
        "basis_of_record": "basisOfRecord_norm",
    }


    constant_fields = {
        "id_source": None,
        "id_dataset": None,
        "count_min": 1,
        "count_max": 1,
    }

    def __init__(self, dry_run=False, **runtime_args):
        self.dry_run = dry_run


        #---- Initialisation des compteurs ------------------------------------
        self.imported_rows = 0
        self.rejected_rows = 0
        self.rejected_no_cd_nom = 0

        self.root = None

        cfg = load_api2gn_config()

        # ------------------------------------------------------------------
        # 1) CHARGEMENT CONFIG API
        # ------------------------------------------------------------------
        self.url = cfg.get("plantnet_api_url", "")
        self.API_KEY = cfg.get("plantnet_api_key", "")

        # ------------------------------------------------------------------
        # LIMITE MAX DE DONNÉES
        # ------------------------------------------------------------------
        self.max_data = cfg.get("plantnet_max_data", 1000)

        try:
            self.max_data = int(self.max_data)
        except Exception:
            self.max_data = 1000

        if self.max_data <= 0 or self.max_data > 1000:
            click.secho(
                "[PlantNet] ⚠ Nombre maximum d'import = 1000. "
                "Traitement limité à 1000 occurrences.",
                fg="orange",
                bold=True
            )
            self.max_data = 1000

      

        


        # --------------- Taxref Mode --------------------------------------
        self.taxref_mode = cfg.get("plantnet_taxref_mode", "strict")

        if self.taxref_mode not in ("strict", "permissif"):
            click.secho(
                f"[API2GN] ⚠ plantnet_taxref_mode invalide ({self.taxref_mode}) → strict",
                fg="yellow",
            )
            self.taxref_mode = "strict"


        # ------------------------------------------------------------------
        # 2) DEFAULT SPECIES
        # ------------------------------------------------------------------
        if cfg.get("plantnet_empty_species_list", False):
            species = []
        else:
            species = cfg.get("list_species", [])

        # ------------------------------------------------------------------
        # 3) GEOMETRY PAR DEFAUT
        # ------------------------------------------------------------------
        geom_json = cfg.get("plantnet_geometry_coordinates_json", "[]")
        try:
            coords = json.loads(geom_json)
        except Exception:
            coords = []

        self.geometry = {
            "type": cfg.get("plantnet_geometry_type", "Polygon"),
            "coordinates": coords,
        }

        # ------------------------------------------------------------------
        # 4) DATES PAR DÉFAUT
        # ------------------------------------------------------------------
        self.scientific_names = species
        self.min_event_date = cfg.get("plantnet_min_event_date", None)
        self.max_event_date = cfg.get("plantnet_max_event_date", None)

        # ------------------------------------------------------------------
        # 5) MAPPING DYNAMIQUE (JSON string)
        # ------------------------------------------------------------------
        mapping_json = cfg.get("plantnet_mapping_json", "{}")
        try:
            self.mapping = json.loads(mapping_json)
        except Exception:
            click.secho("[API2GN] ⚠ Erreur parsing mapping_json", fg="red")
            self.mapping = {}

        # backup defaults for runtime override
        self._defaults = {
            "geometry": self.geometry,
            "scientific_names": self.scientific_names,
            "min_event_date": self.min_event_date,
            "max_event_date": self.max_event_date,
        }

        super().__init__()

        # override with runtime args
        self._apply_runtime_args(runtime_args)

        # autogenerate source + dataset
        self._auto_setup_metadata()



    # =============================================================================
    # AUTO CREATION METADATA GN
    # =============================================================================
    


    def _auto_setup_metadata(self):
        # SOURCE
        row = db.session.execute(text("""
            SELECT id_source FROM gn_synthese.t_sources
            WHERE name_source = 'Pl@ntNet'
        """)).fetchone()

        if row:
            id_source = row[0]
        else:
            if self.dry_run:
                id_source = -1
            else:
                r = db.session.execute(text("""
                    INSERT INTO gn_synthese.t_sources (name_source, desc_source)
                    VALUES ('Pl@ntNet', 'Import API PlantNet')
                    RETURNING id_source
                """))
                id_source = r.fetchone()[0]
                db.session.commit()

        # ACQUISITION FRAMEWORK
        af = db.session.scalar(select(TAcquisitionFramework).where(
            TAcquisitionFramework.acquisition_framework_name == "Pl@ntNet"
        ))
        if not af:
            af = TAcquisitionFramework(
                acquisition_framework_name="Pl@ntNet",
                acquisition_framework_desc="Cadre d'acquisition automatisé PlantNet"
            )
            db.session.add(af)
            if not self.dry_run:
                db.session.commit()

        # DATASET
        dataset = db.session.scalar(select(TDatasets).where(
            TDatasets.dataset_name == "Pl@ntNet – La Réunion"
        ))

        if not dataset:
            dataset = TDatasets(
                dataset_name="Pl@ntNet – La Réunion",
                dataset_shortname="PlantNet974",
                dataset_desc="Observations Pl@ntNet La Réunion",
                id_acquisition_framework=af.id_acquisition_framework,
                terrestrial_domain=True,
            )
            db.session.add(dataset)
            if not self.dry_run:
                db.session.commit()

        self.constant_fields["id_source"] = id_source
        self.constant_fields["id_dataset"] = dataset.id_dataset

    # =============================================================================
    # API CALL
    # =============================================================================

    def _build_payload(self):
        payload = {
            "limit": self.max_data
        }

        if self.scientific_names:
            payload["scientificName"] = self.scientific_names

        if self.min_event_date:
            payload["minEventDate"] = self.min_event_date

        if self.max_event_date:
            payload["maxEventDate"] = self.max_event_date

        # Si on veut réactiver le filtre géométrique :
        # if self.geometry:
        #     payload["geometry"] = self.geometry

        return payload


    def _call_api(self):
        click.secho(
            f"[PlantNet] Appel API (limit={self.max_data})",
            fg="blue"
        )

        resp = requests.post(
            self.url,
            params={"api-key": self.API_KEY},
            json=self._build_payload(),
            timeout=(10, 90)
        )

        if resp.status_code != 200:
            click.secho(resp.text, fg="red")
            raise click.ClickException("Erreur API PlantNet")

        data = resp.json()
        self.root = data

        return data.get("results", []) or data.get("data", [])



    
    def print_summary(self):
        if self.dry_run:
            return
        click.secho("\n[PlantNet] Résumé de l'import :", fg="cyan")
        click.secho(f"  ✔ Importées : {self.imported_rows}", fg="green")
        click.secho(f"  ✖ Rejetées  : {self.rejected_rows}", fg="red")

        if self.rejected_no_cd_nom:
            click.secho(
                f"    ↳ sans cd_nom (mode {self.taxref_mode}) : {self.rejected_no_cd_nom}",
                fg="yellow",
            )


    # =============================================================================
    # ITERATION DES RESULTATS
    # =============================================================================

    def get_geom(self, row):
        lat = row.get("decimalLatitude")
        lon = row.get("decimalLongitude")
        if lat is None or lon is None:
            return None
        return from_shape(Point(lon, lat), srid=self.srid)

    def next_row(self):
        try:
            results = self._call_api()

            for rec in results:
                media = rec.get("media") or []
                url = media[0].get("medium_url") if media else None

                bor_raw = (rec.get("basisOfRecord") or "").strip()
                bor_norm = BASIS_OF_RECORD_MAP.get(bor_raw.lower(), bor_raw)

                row = {
                    "id": rec.get("id"),
                    "scientificName": rec.get("scientificName"),
                    "eventDate": rec.get("eventDate") or rec.get("observedOn"),
                    "decimalLatitude": rec.get("decimalLatitude"),
                    "decimalLongitude": rec.get("decimalLongitude"),
                    "rightsHolder": rec.get("rightsHolder"),
                    "user_id": (rec.get("user") or {}).get("id"),
                    "associatedMedia": url,
                    "basisOfRecord_norm": bor_norm,
                }

                cd_nom = _resolve_cd_nom(row)

                if cd_nom is None and self.taxref_mode == "strict":
                    self.rejected_rows += 1
                    self.rejected_no_cd_nom += 1
                    continue

                row["cd_nom"] = cd_nom
                self.imported_rows += 1
                yield row

        finally:
            self.print_summary()



        

    # =============================================================================
    # RUNTIME OVERRIDE
    # =============================================================================

    def _apply_runtime_args(self, args):
        args = args or {}

        self.geometry = args.get("geometry", self._defaults["geometry"])
        self.scientific_names = args.get("scientific_names", self._defaults["scientific_names"])
        self.min_event_date = args.get("min_event_date", self._defaults["min_event_date"])
        self.max_event_date = args.get("max_event_date", self._defaults["max_event_date"])

    @property
    def total(self):
        try:
            return len(self.root.get("results", []) or self.root.get("data", []))
        except Exception:
            return 0
