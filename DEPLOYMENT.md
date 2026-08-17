# Déploiement SurvDocker

Ce document décrit le déploiement sur un serveur Docker personnel derrière Traefik et Authelia.

## 1. Préparer les fichiers

1. Copier le dépôt sur le serveur.
2. Créer le fichier `.env` à partir de `.env.example`.
3. Éditer `survdocker/config/survdocker.yml` uniquement pour les réglages applicatifs.
4. Lancer `python start_survdocker.py` pour générer les configs dérivées et démarrer la stack.

Le fichier `.env` doit contenir toutes les variables utilisées par le compose, sans valeur de secours dans le fichier YAML. Les chemins utilisés pour les volumes sont lus depuis `.env`, tandis que les chemins internes des conteneurs restent fixés dans le compose.

Le fichier central contient déjà des commentaires pour expliquer chaque paramètre.

## 2. Réglages à adapter

- `app.scan_token` : protège la route `/scan-now`.
- `SURVDOCKER_HOSTNAME` : nom public exposé par Traefik.
- `TRAEFIK_AUTH_MIDDLEWARE` : chaîne de middlewares Traefik, par exemple `my-geoblock@file,crowdsec-bouncer@docker,authelia_df@docker,sslheader@docker`.
- `loki.base_url` : doit rester sur le nom DNS Docker `http://loki:3100`.
- `telegram.enabled` : activer seulement si Telegram est réellement configuré.
- `critical.critical_alerts` : ajuste les seuils et le cooldown des alertes.
- `SURVDOCKER_DATA_DIR`, `SURVDOCKER_CONFIG_DIR`, `SURVDOCKER_CONFIG_FILE` : chemins utilisés dans le compose.
- `LOKI_BASE_URL` : URL interne de Loki.
- `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_THREAD_ID` : variables d’alerte si Telegram est actif.

## 3. Démarrage de la stack

Le script `start_survdocker.py` exécute `docker compose up -d --build` après avoir généré les configs dérivées.

Ordre attendu dans Compose :

1. `loki`
2. `alloy`
3. `survdocker`
4. `survdocker-scheduler`
5. `survdocker-critical-monitor`

## 4. Vérifications utiles

- L’application Flask doit écouter sur `0.0.0.0:8080` dans le conteneur.
- Traefik doit router vers le port interne `8080`.
- Le réseau externe `traefik` doit exister sur le serveur Docker.
- Le volume `survdocker/data` doit être persistant.
- Le scan hebdomadaire ne doit pas se déclencher à chaque visite de `/`.

## 5. Fichiers à connaître

- `survdocker/config/survdocker.yml` : configuration centrale à modifier.
- `survdocker/config/alloy.alloy` : configuration de collecte Alloy, générée à partir du fichier central.
- `survdocker/config/loki-config.yml` : configuration Loki, générée à partir du fichier central.
- `docker-compose.yml` : orchestration des services.

## 6. Mise à jour

Après changement de configuration :

1. Modifier `survdocker/config/survdocker.yml`.
2. Redémarrer les services concernés.
3. Vérifier `/health` puis `/reports`.

## 7. Notes de sécurité

- Le socket Docker monté dans Alloy et le moniteur critique doit rester en lecture seule.
- Le port Loki ne doit pas être exposé directement sur Internet.
- Le site reste protégé par Traefik et Authelia.
