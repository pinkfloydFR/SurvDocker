# Notes de session — SurvDocker

Résumé des modifications faites lors des sessions Claude Code précédentes, pour reprise rapide de contexte. À lire avant toute nouvelle modif de l'UI ou du pipeline Loki/Alloy.

## Infra / déploiement

- **Port** : passé de `8080` à `60000` partout (`Dockerfile` EXPOSE, `.env`/`.env.example` `SURVDOCKER_PORT`, `docker-compose.yml` label Traefik + `config.py` fallback, README/DEPLOYMENT.md).
- **Accès direct** : ajout de `ports: - "60000:60000"` sur le service `survdocker` dans `docker-compose.yml` (en plus du routage Traefik existant via `SURVDOCKER_HOSTNAME`), pour accès direct `http://<ip>:60000`.
- **Rebuild requis** : `templates/`, `web.py`, `scan.py`, `analyzer.py`, `render_configs.py` sont **copiés dans l'image** (pas montés en volume) → toute modif de code nécessite `docker compose up -d --build survdocker` (ou toute la stack), un simple `restart` ne suffit pas.
  `survdocker/system/alloy.alloy` et `loki-config.yml` sont eux **montés en volume** → un simple `docker compose restart alloy` / `restart loki` suffit après édition.

## Bugs Loki/Alloy corrigés

1. **Scan qui timeout ("Loki injoignable")** : en réalité un dépassement de la limite gRPC interne par défaut de Loki (4 Mo) entre `querier`/`query-frontend` sur les grosses requêtes (lookback 7j). Fix : `grpc_server_max_recv_msg_size` / `grpc_server_max_send_msg_size: 67108864` ajoutés dans `server:` de `loki-config.yml` (et dans `render_loki_config` de `render_configs.py`).
2. **Faux conteneur "docker" dans les rapports** : `discovery.relabel` dans `alloy.alloy` utilisait `regex = "/(.*)"`, qui échoue si `__meta_docker_container_name` n'a pas de slash initial → régex changée en `"/?(.*)"`. Cause résiduelle trouvée : au démarrage d'Alloy, quelques lignes sont ingérées **avant** que `discovery.docker` ait fini de résoudre les noms → elles arrivent sans label `container` et retombent sur le label statique `job="docker"`. Fix définitif : ajout d'un stage de filtrage dans `loki.process "docker_logs"` :
   ```
   stage.match {
     selector = "{container=\"\"}"
     stage.drop { expression = ".*" }
   }
   ```
   Ces deux fixs sont dans `render_configs.py` (source) **et** `survdocker/system/alloy.alloy` (généré, à garder synchronisés).
3. **`container_count` faux dans l'UI** : `report_summary()` comptait `len(report["containers"])`, qui ne liste que les conteneurs ayant au moins une erreur retenue après filtrage — pas tous les conteneurs scannés. Fix : `scan.py` calcule maintenant `report["scanned_container_count"]` (tous les conteneurs vus dans les logs bruts avant filtrage) et `analyzer.report_summary()` l'utilise en priorité.

## Fonctionnalités ajoutées

- **Feedback de scan** : `scan.py` écrit un état `"running"` dans `data/last-scan.json` dès le début du scan (pas seulement à la fin). `/health` expose `scan_state` + `scan_timestamp`. `index.html` affiche une barre de progression animée qui poll `/health` et se termine par un reload auto (succès) ou un message d'erreur.
- **Logs complets par conteneur** : nouvelle route `GET /containers/<name>/logs` (`web.py`) qui interroge Loki directement (`{job="docker", container="<name>"}`) sur la période du rapport affiché, et renvoie le texte brut trié chronologiquement. Le nom de chaque conteneur dans l'UI est un lien `target="_blank"` vers cette route.
- **Copie d'erreur** : l'icône de copie (presse-papiers, en haut à droite du bloc d'exemples) ne copie plus que les lignes brutes d'exemples (`group.examples`), sans le préambule Container/Level/Occurrences/etc. (`format_report_copy`/`copyable_text` dans `analyzer.py` restent inchangées, encore utilisées par l'export `.txt` et testées par `tests/test_copy.py`/`test_analyzer.py`).
- **Bouton "remonter en haut"** : bouton flottant en bas à droite, apparaît après 400px de scroll, scroll fluide au clic.
- **Format de date** : filtre Jinja `format_datetime` (dans `web.py`) → `YYYY-MM-DD HH:mm:ss`, appliqué à génération, première/dernière apparition. Affichage uniquement — les JSON de rapport gardent l'ISO 8601 brut.

## UI (`survdocker/templates/index.html`)

- **Thème sombre** partout (`index.html`, `reports.html`, `report_detail.html`) + largeur pleine (`width: 100%` au lieu de `max-width` fixe).
- **En-tête** : réduite à un seul bloc compact (`panel header-panel`) — plus de titre "Dernier rapport Docker" ni de paragraphe descriptif. Deux lignes : (1) badge + 4 stats en ligne (génération, conteneurs analysés, avec erreurs, groupes), (2) actions (Historique / Actualiser / Scanner) + barre de progression repliable.
- **Blocs conteneur** : couleur de bordure/fond alternée par conteneur (classes `c0`–`c5`, cycle de 6 teintes) pour la lisibilité.
- **Par groupe d'erreur** : ligne "Niveau X · N occurrence(s)" déplacée sur la même ligne que les métadonnées (Première/Dernière apparition, Exemples, Complet — chacune sur une seule ligne label+valeur), alignée à droite. Le message normalisé en gras (redondant avec les exemples) a été supprimé, ainsi que "Top des erreurs sur la période analysée".
- **Exemples** : seulement les 5 premiers affichés (au lieu de jusqu'à 100), avec note "+N autres" ; export JSON/texte et copie gardent tout.

## Points d'attention pour la suite

- Le fichier `.env` de ce dépôt contient de vrais secrets (token Telegram, scan token) — ne jamais les afficher/committer en clair dans une réponse ou un doc.
- `render_configs.py` (source) et `survdocker/system/{alloy.alloy,loki-config.yml}` (générés) sont actuellement maintenus **manuellement en double** dans cette session car l'environnement Python local n'a pas PyYAML dispo pour lancer `render-configs` — bien vérifier qu'ils restent synchronisés si l'un des deux est modifié.
- Toujours rebuild (`docker compose up -d --build survdocker`) après une modif de template/`web.py`/`scan.py`/`analyzer.py`.
