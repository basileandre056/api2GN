# api2GN – Import de données externes dans GeoNature
## Parser Pl@ntNet – Import dynamique configurable (TOML)

Ce dépôt contient le module **api2GN**, utilisé par GeoNature pour importer automatiquement
des données issues de sources externes (API REST, WFS, etc.) dans la Synthèse.

Ce README documente en particulier l’intégration du **parser Pl@ntNet**, développé pour
l’import d’observations botaniques géolocalisées via l’API Pl@ntNet v3.

---

## 🚀 Installation du module api2GN

### Récupération de l'archive :
#### Lorsque le fork sera accepté par le PnX-SI :
```bash

# Récupération de l’archive officielle
wget https://github.com/PnX-SI/api2GN/archive/1.0.0.rc1.zip
unzip 1.0.0.rc1.zip
rm 1.0.0.rc1.zip
mv api2GN-1.0.0.rc1/ api2GN
```

#### En attendant, si le fork est a partir d'un autre repo : 
```bash
# cloner le dépôt
git clone https://github.com/<git_username>/api2GN.git
```
### Suite de l'installation :

```bash
# Depuis le venv GeoNature
cd geonature
source backend/venv/bin/activate

# déplacer le fichier de config :
cp ~/api2GN/api2gn_config.toml.example ~/geonature/config/api2gn_config.toml

# Installation du module
geonature install-gn-module ~/api2GN API2GN

# Mise à jour de la base
geonature db upgrade api2gn@head

# choisir un parser a configurer : par exemple le parser plantnet
cd ~/api2GN/api2gn/var/config/
cp parsers_plantnet.py parsers.py

# Relancer géonature :
sudo systemctl restart geonature geonature-worker

# vérifier que le serveur tourne :
sudo systemctl status geonature

# recharger et lister les parseurs chargés dans api2gn/var/config/parsers.py
geonature api2gn parser list

# phase test (sans intégration des données dans la base)
geonature api2gn parser run PLANTNET_REUNION --dry-run

# extraction réelle (avec intégration des données dans la base )
geonature api2gn parser run PLANTNET_REUNION
```

---

## ⚙️ Configuration (TOML)

Le parser Pl@ntNet est entièrement configurable via un fichier TOML
(polygone, taxons, dates, mode strict TAXREF, paramètres API).

📘 Documentation utilisateur complète :
👉 https://github.com/basileandre056/api2GN/blob/main/documentation/USER_GUIDE.md
---

## 🌿 Parser Pl@ntNet – Présentation

Le parser **Pl@ntNet** permet :

- l’interrogation dynamique de l’API Pl@ntNet (`dwc/occurrence/search`),
- le filtrage par :
  - taxons,
  - périmètre géographique (bbox ou polygone GeoJSON),
  - période temporelle,
- la normalisation Darwin Core,
- l’import dans la Synthèse GeoNature via api2GN.

Le parser est **entièrement configurable via un fichier TOML**, sans modification du python.

---

### ✅ Fonctionnalités clés du parser Pl@ntNet

Le parser Pl@ntNet implémente actuellement :

- Chargement **automatique de la configuration GeoNature (API2GN)**,
  avec **valeurs par défaut intégrées** si la configuration est absente ou incomplète ;
- Import **robuste même sans configuration TOML** (mode fallback) ;
- Résolution avancée des taxons :
  - TAXREF local (prioritaire),
  - fallback automatique vers **TAXREF-LD (MNHN)**,
  - validation de l’existence du `cd_nom` en base GeoNature ;
- Mode **strict TAXREF** (rejet si aucun `cd_nom`) ;
- Cache mémoire des taxons déjà résolus (optimisation forte des performances) ;
- Logs explicites :
  - paramètres effectifs chargés,
  - taxons rejetés,
  - statistiques TAXREF local / TAXREF-LD ;
- Auto-création des métadonnées GeoNature :
  - Source,
  - Cadre d’acquisition,
  - Dataset.


## ⚙️ Fichier de configuration (TOML)

Le fichier de configuration permet de définir :

- le polygone par défaut (ex. La Réunion),
- la liste des taxons ciblés,
- les dates min / max,
- le mode strict TAXREF,
- les paramètres API Pl@ntNet.

## 📊 Interprétation des résultats

L’interprétation détaillée des sorties du parser
(importées, rejetées, gestion du `cd_nom`, mode strict)
est décrite dans la documentation utilisateur :

👉 https://github.com/basileandre056/api2GN/blob/main/documentation/USER_GUIDE.md

## 🛠 Développement de parsers

Le module fournit plusieurs classes de base :

- `GeoNatureParser`
- `JSONParser`
- `WFSParser`

Les méthodes principales surchargables sont :

- `next_row()`
- `build_object(row)`
- `start()`
- `end()`
- `run()`

---

## 📚 Documentation associée

- Documentation technique :  
  https://github.com/basileandre056/api2GN/blob/main/documentation/TECHNICAL_DOC.md

- Documentation utilisateur :  
  https://github.com/basileandre056/api2GN/blob/main/documentation/USER_GUIDE.md


---

## 🔗 Liens utiles

- GeoNature : https://geonature.fr/
- api2GN (upstream) : https://github.com/PnX-SI/api2GN
- Fork api2GN (Pl@ntNet) : https://github.com/basileandre056/api2GN

---

© Basile ANDRE – Stage Assistant Ingénieur – DEAL Réunion
