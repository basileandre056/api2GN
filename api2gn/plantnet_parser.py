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
# DEFAULT CONFIG (fallback si API2GN absente ou incomplète)
# =============================================================================

DEFAULT_CONFIG = {
    "plantnet_api_url": "https://my-api.plantnet.org/v3/dwc/occurrence/search",
    "plantnet_api_key": None,  # volontairement None
    "plantnet_taxref_mode": "strict",
    "plantnet_max_data": 1000,
    "plantnet_empty_species_list": True,
    "list_species": [],
    "plantnet_min_event_date": None,
    "plantnet_max_event_date": None,
    "plantnet_geometry_type": "Polygon",
    "plantnet_geometry_coordinates_json": None,
    "plantnet_mapping_json": "{}",
}



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

def load_api2gn_config():
    cfg = gn_config.get("API2GN")

    if not cfg:
        click.secho(
            "[API2GN] ⚠ Aucune config GeoNature → utilisation des valeurs par défaut",
            fg="yellow"
        )
        return DEFAULT_CONFIG.copy()

    # merge defaults + config
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)

    return merged




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
        self.taxref_local_ok = 0
        self.taxref_ld_ok = 0


        self.root = None

        cfg = load_api2gn_config()

        self.url = cfg["plantnet_api_url"]
        self.API_KEY = cfg["plantnet_api_key"]

        if not self.API_KEY:
            raise click.ClickException(
                "[PlantNet] ❌ API KEY absente (plantnet_api_key)"
            )

        self.max_data = int(cfg["plantnet_max_data"])
        self.taxref_mode = cfg["plantnet_taxref_mode"]

        self.empty_species = cfg["plantnet_empty_species_list"]
        self.scientific_names = [] if self.empty_species else cfg["list_species"]

        self.geometry_type = cfg["plantnet_geometry_type"]

        if cfg["plantnet_geometry_coordinates_json"]:
            self.geometry_coordinates = json.loads(
                cfg["plantnet_geometry_coordinates_json"]
            )
        else:
            self.geometry_coordinates = None

        self.geometry = (
            {
                "type": self.geometry_type,
                "coordinates": self.geometry_coordinates,
            }
            if self.geometry_coordinates
            else None
        )

        # dates
        self.min_event_date = cfg["plantnet_min_event_date"]
        self.max_event_date = cfg["plantnet_max_event_date"]

        # mapping dynamique
        self.mapping = json.loads(cfg["plantnet_mapping_json"])


        # backup defaults for runtime override
        self._defaults = {
            "geometry": self.geometry,
            "scientific_names": self.scientific_names,
            "min_event_date": self.min_event_date,
            "max_event_date": self.max_event_date,

        }

        self.print_initial_summary()


        super().__init__()

        # override with runtime args
        self._apply_runtime_args(runtime_args)

        # autogenerate source + dataset
        self._auto_setup_metadata()

        # Offset pour itération par blocs de 1000
        self.offset = 0


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
            "limit": self.max_data,
            "offset": self.offset
        }

        if self.scientific_names:
            payload["scientificName"] = self.scientific_names

        if self.min_event_date:
            payload["minEventDate"] = self.min_event_date

        if self.max_event_date:
            payload["maxEventDate"] = self.max_event_date

        if self.geometry:
            payload["geometry"] = self.geometry

        return payload


    def _call_api(self):
        click.secho(
            f"[PlantNet] Appel API (limit={self.max_data}, offset={self.offset})",
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
        if self.root is None:
            self.root = data

        return data.get("results", []) or data.get("data", [])

    
    def print_summary(self):
        if self.dry_run:
            return

        click.secho("\n[PlantNet] Résumé de l'import :", fg="cyan")

        click.secho(f"✔ Occurrences importées     : {self.imported_rows}", fg="green")
        click.secho(f"✖ Occurrences rejetées      : {self.rejected_rows}", fg="red")

        click.secho(
            f"✔ Occurrences validées TAXREF local : {self.taxref_local_ok}",
            fg="green"
        )

        click.secho(
            f"✔ Occurrences validés TAXREF LD    : {self.taxref_ld_ok}",
            fg="green"
        )


    def print_initial_summary(self):
        click.secho("\n[PlantNet] Paramètres effectifs :", fg="cyan", bold=True)

        click.secho(f"URL API            : {self.url}", fg="cyan")
        click.secho(f"API KEY présente   : {bool(self.API_KEY)}", fg="cyan")
        click.secho(f"Mode TAXREF        : {self.taxref_mode}", fg="cyan")
        click.secho(f"Max data           : {self.max_data}", fg="cyan")

        click.secho(
            f"Dates              : {self.min_event_date} → {self.max_event_date}",
            fg="cyan"
        )

        if self.geometry:
            click.secho(
                f"Géométrie          : {self.geometry_type} "
                f"({len(self.geometry_coordinates[0])} points)",
                fg="cyan"
            )
        else:
            click.secho("Géométrie          : Aucune", fg="yellow")

        if self.scientific_names:
            click.secho(
                f"Filtre espèces     : {len(self.scientific_names)} taxons",
                fg="cyan"
            )
        else:
            click.secho(
                "Filtre espèces     : aucun (import global)",
                fg="yellow"
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
    

    def _resolve_cd_nom(self, row):
        sci = row.get("scientificName")
        if not sci:
            return None

        if sci in _CD_NOM_CACHE:
            return _CD_NOM_CACHE[sci]

        # 1) TAXREF local
        cd = resolve_cd_nom_local(sci)
        if cd:
            _CD_NOM_CACHE[sci] = cd
            self.taxref_local_ok += 1
            return cd

        # 2) TAXREF-LD
        cd_ld = resolve_cd_nom_taxref_ld(sci)
        if cd_ld:
            exists = db.session.scalar(
                select(Taxref.cd_nom).where(Taxref.cd_nom == cd_ld)
            )
            if exists:
                _CD_NOM_CACHE[sci] = cd_ld
                self.taxref_ld_ok += 1
                return cd_ld

        _CD_NOM_CACHE[sci] = None
        return None


    def next_row(self):
        try:
            while True:
                results = self._call_api()
                nb_results = len(results)

                if not results:
                    break

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

                    cd_nom = self._resolve_cd_nom(row)

                    if cd_nom is None and self.taxref_mode == "strict":
                        self.rejected_rows += 1
                        self.rejected_no_cd_nom += 1
                        continue

                    row["cd_nom"] = cd_nom
                    self.imported_rows += 1
                    yield row

                # 🔁 Condition de poursuite
                if nb_results < self.max_data:
                    break

                # ➕ On décale l’offset
                self.offset += self.max_data
                if self.offset > 1_000_000:
                    click.secho(
                        "[PlantNet] ⚠ Arrêt de sécurité (offset trop élevé)",
                        fg="red",
                        bold=True
                    )
                    break
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
