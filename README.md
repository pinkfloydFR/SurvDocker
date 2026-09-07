# SurvDocker

SurvDocker est une solution locale pour analyser les logs Docker via Grafana Alloy et Loki, générer un rapport hebdomadaire persistant, et afficher le dernier résultat dans une interface Flask.

<img width="2494" height="1143" alt="image" src="https://github.com/user-attachments/assets/17458e39-93e7-494c-8492-9e6298d9f402" />

-> Développé à l'aide de Claude Code, si vous êtes contre, ne l'utilisez pas ! <-


## Composants

- `survdocker` : interface web Flask
- `survdocker-scheduler` : exécution hebdomadaire du scan
- `survdocker-critical-monitor` : surveillance continue des incidents critiques
- `loki` : stockage local des logs
- `alloy` : collecte des logs Docker

## Démarrage

```bash
cp .env.example .env
python start_survdocker.py
```

Le script unique génère d’abord les fichiers dérivés puis lance `docker compose up -d --build`.

Le site web écoute sur `0.0.0.0:60000` dans le conteneur et expose les routes `/`, `/reports`, `/health`, `/scan-now`, `/test-alert` et `/export.json`.

Cliquer sur le nom d’un conteneur dans le tableau de bord ouvre `/containers/<nom>/logs` dans un nouvel onglet : cette page interroge Loki en direct et propose un menu déroulant pour filtrer par période (période du rapport, 5 minutes, 1 heure, 24h, 48h, ou toutes les données conservées).

Le bouton « Exporter pour analyse » (ou `/export.json` directement) télécharge un fichier JSON qui agrège tous les rapports conservés (`scan.retention_reports`) : pour chaque couple conteneur/motif d’erreur, il donne le nombre total d’occurrences, la première et la dernière apparition, dans combien de rapports il est réapparu, et des exemples de lignes brutes, classés du problème le plus récurrent au moins récurrent. Ce fichier est pensé pour être donné tel quel à un assistant (Claude ou autre) afin d’identifier les problèmes qui reviennent le plus souvent.

## Fichiers de configuration

- `survdocker/config/survdocker.yml` : configuration centrale à éditer
- `survdocker/system/alloy.alloy` : configuration technique Alloy générée automatiquement
- `survdocker/system/loki-config.yml` : configuration technique Loki générée automatiquement
- `docker-compose.yml` : orchestration complète

Le dossier `survdocker/config` contient uniquement la configuration utilisateur à modifier.
Dans cette version minimale, `survdocker.yml` contient seulement les paramètres métier du scan, des filtres et du moniteur critique.

Les configurations techniques non destinées à être éditées sont générées dans `survdocker/system`.

Les fichiers `survdocker/system/loki-config.yml` et `survdocker/system/alloy.alloy` sont générés à partir de ce fichier central via la commande `python -m survdocker render-configs`.

Pour un lancement manuel, tu peux aussi exécuter `python start_survdocker.py` à la racine du projet.

Le routage Traefik utilise `SURVDOCKER_HOSTNAME` pour le host public et `TRAEFIK_AUTH_MIDDLEWARE` pour chaîner tes middlewares, par exemple `my-geoblock@file,crowdsec-bouncer@docker,authelia_df@docker,sslheader@docker`.

Les valeurs d’infrastructure Docker (hôte/port app, chaîne Traefik, secrets Telegram et/ou Apprise) sont gérées via `.env` — `LOKI_BASE_URL` est fixée en dur dans `docker-compose.yml` sur le nom DNS interne `http://loki:3100`.

## Aide au déploiement

Voir [DEPLOYMENT.md](DEPLOYMENT.md) pour la procédure complète de mise en place sur ton serveur.

## Validation locale

L’environnement de développement fourni ici ne permet pas de valider l’intégration Docker réelle, mais la logique Python est couverte par des tests unitaires.

```bash
pytest -q
```
