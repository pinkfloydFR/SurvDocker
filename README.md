# SurvDocker

SurvDocker est une solution locale pour analyser les logs Docker via Grafana Alloy et Loki, générer un rapport hebdomadaire persistant, et afficher le dernier résultat dans une interface Flask protégée par Traefik et Authelia.

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

Le site web écoute sur `0.0.0.0:8080` dans le conteneur et expose les routes `/`, `/reports`, `/health` et `/scan-now`.

## Fichiers de configuration

- `survdocker/config/survdocker.yml` : configuration centrale à éditer
- `survdocker/config/alloy.alloy` : configuration Grafana Alloy
- `survdocker/config/loki-config.yml` : configuration Grafana Loki
- `docker-compose.yml` : orchestration complète

Le fichier `survdocker/config/survdocker.yml` est commenté et regroupe la configuration applicative, les filtres, le planificateur, le moniteur critique et Telegram.

Les fichiers `survdocker/config/loki-config.yml` et `survdocker/config/alloy.alloy` sont générés à partir de ce fichier central via la commande `python -m survdocker render-configs`.

Pour un lancement manuel, tu peux aussi exécuter `python start_survdocker.py` à la racine du projet.

Le routage Traefik utilise `SURVDOCKER_HOSTNAME` pour le host public et `TRAEFIK_AUTH_MIDDLEWARE` pour chaîner tes middlewares, par exemple `my-geoblock@file,crowdsec-bouncer@docker,authelia_df@docker,sslheader@docker`.

## Aide au déploiement

Voir [DEPLOYMENT.md](DEPLOYMENT.md) pour la procédure complète de mise en place sur ton serveur.

## Validation locale

L’environnement de développement fourni ici ne permet pas de valider l’intégration Docker réelle, mais la logique Python est couverte par des tests unitaires.

```bash
pytest -q
```
