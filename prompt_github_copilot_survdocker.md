# Prompt GitHub Copilot — SurvDocker

Tu es un développeur senior spécialisé en Python, Docker Compose, Grafana Loki, Grafana Alloy, Flask et Traefik.

Je souhaite développer une solution entièrement locale permettant d’analyser périodiquement les logs de mes conteneurs Docker et de présenter un rapport web propre, sans intelligence artificielle locale et sans métriques.

## Objectif général

Créer une mini-application web appelée `SurvDocker`, accessible à l’adresse :

```text
https://survdocker.denisflamant.com
```

Le domaine sera publié derrière mon reverse proxy Traefik. L’application devra donc écouter sur un port HTTP interne, par exemple `8080`, sans gérer elle-même TLS.

La chaîne complète sera :

```text
Conteneurs Docker → Grafana Alloy → Grafana Loki → script Python périodique → rapport stocké → mini-site web
```

L’application web ne doit pas analyser les logs à chaque ouverture de page. Le scan doit être réalisé automatiquement une seule fois par semaine, puis le site doit afficher le dernier rapport généré.

## Contraintes impératives

- Ne pas utiliser d’IA, ni locale ni distante.
- Ne pas utiliser Ollama.
- Ne pas utiliser Prometheus, cAdvisor ou de métriques système.
- Ne pas utiliser Telegram pour transmettre le rapport.
- Ne pas analyser les logs à chaque ouverture du site.
- Ne pas envoyer les logs vers un service cloud.
- Utiliser uniquement Docker Compose, Grafana Alloy, Loki et une application Python légère.
- L’application doit rester simple, lisible, maintenable et peu consommatrice.
- Les fichiers de configuration doivent être organisés au même niveau que le fichier `docker-compose.yml`.
- Les logs peuvent contenir des informations sensibles : l’accès au site doit être protégé par Traefik et Authelia.

## Architecture attendue

Créer au minimum les services Docker suivants :

```text
alloy
loki
survdocker
```

Grafana doit être optionnel et ne doit pas être nécessaire au fonctionnement du rapport.

Architecture :

```text
Docker
  ↓
Grafana Alloy
  ↓
Grafana Loki
  ↓
SurvDocker — analyse hebdomadaire
  ↓
Fichier JSON ou SQLite contenant le dernier rapport
  ↓
Interface web HTML
```

## Grafana Alloy

Utiliser Grafana Alloy et non Promtail.

Alloy doit découvrir les conteneurs Docker et envoyer leurs logs à Loki avec des labels peu nombreux et utiles, notamment :

- `job=docker` ;
- `container` ou `container_name` ;
- éventuellement `compose_project` ;
- éventuellement `host`.

Ne jamais créer de label à haute cardinalité avec :

- le message complet ;
- une adresse IP variable ;
- un port variable ;
- un identifiant de requête ;
- un timestamp.

Prévoir la persistance du stockage Alloy afin qu’un redémarrage ne provoque pas de relecture inutile ou de doublons.

Alloy pourra utiliser :

```yaml
- /var/run/docker.sock:/var/run/docker.sock:ro
```

Documenter clairement les implications de sécurité du socket Docker.

## Grafana Loki

Loki doit fonctionner en mode mono-instance local avec stockage filesystem.

Prévoir :

- un volume persistant ;
- une rétention configurable, par défaut 30 jours ;
- une configuration adaptée à un seul hôte Docker ;
- un healthcheck ;
- une limite raisonnable de taille de logs ;
- aucune dépendance à Prometheus.

Le rapport doit pouvoir interroger les logs des sept derniers jours, même si la tâche hebdomadaire est exécutée avec un léger retard.

## Analyse périodique

Le scan doit être exécuté automatiquement une fois par semaine, et non à l’ouverture de la page.
Il faut tout de même une option pour un rafraichissement à la demande.

Prévoir une solution robuste et explicite, au choix :

1. un scheduler interne dans le conteneur `survdocker` ;
2. un processus séparé dans le même conteneur ;
3. un cron externe documenté ;
4. un service Compose séparé de type `survdocker-scheduler`.

Privilégier une solution facilement visible et maintenable. Éviter de lancer un serveur web et un cron de manière fragile dans le même processus sans supervision.

La configuration doit permettre de choisir :

```text
SCAN_DAY=1       # lundi par défaut
SCAN_TIME=06:00
SCAN_LOOKBACK=7d
TIMEZONE=Europe/Paris
```

Le rapport doit être généré automatiquement chaque semaine et enregistré dans un emplacement persistant, par exemple :

```text
./survdocker/data/latest-report.json
./survdocker/data/reports/report-YYYY-MM-DD.json
```

Conserver au moins les quatre derniers rapports hebdomadaires, avec un paramètre de rétention configurable.

Prévoir également une route ou une commande manuelle protégée permettant de demander un nouveau scan, mais cette action doit être explicite et ne doit pas être déclenchée automatiquement par une simple visite du site.

## Contenu du rapport

Pour chaque conteneur Docker ayant au moins une erreur pertinente, afficher au maximum les cinq erreurs ou motifs d’erreurs les plus fréquents sur la période analysée.

Pour chaque entrée, conserver :

- le nom du conteneur ;
- le nombre d’occurrences ;
- le niveau estimé : `error`, `fatal`, `panic`, `warning` ou `unknown` ;
- la première date d’apparition ;
- la dernière date d’apparition ;
- le motif normalisé ;
- au moins une ligne exacte originale ;
- idéalement toutes les lignes exactes originales, avec limitation configurable si leur nombre est excessif ;
- une indication indiquant si le résultat contient toutes les occurrences ou seulement un échantillon.

Le classement doit être effectué séparément pour chaque conteneur.

Exemple logique :

```text
authelia_pf
  1. Redis connection refused — 42 occurrences
  2. Request timeout — 18 occurrences
  3. Configuration deprecated — 12 occurrences

traefik
  1. Gateway timeout — 18 occurrences
  2. Backend unavailable — 7 occurrences
```

## Filtrage des faux problèmes

Créer un fichier de configuration séparé, par exemple :

```text
./survdocker/config/filters.yml
```

Permettre de modifier les filtres sans reconstruire l’image.

Ignorer par défaut les messages ou événements suivants lorsqu’ils représentent des accès normaux :

- `status_code=200` ;
- `status_code=204` ;
- `status_code=301` ;
- `status_code=302` ;
- `status_code=401` ;
- accès non autorisé Authelia ;
- redirection normale vers le portail Authelia ;
- requêtes `robots.txt` ;
- `healthcheck` ;
- `readiness` ;
- `liveness` ;
- `/api/health` ;
- `/ping`.

Attention : le filtrage ne doit pas supprimer une ligne contenant une vraie panne simplement parce qu’elle contient un code HTTP. Prévoir une logique claire et documentée, avec possibilité de désactiver chaque règle.

Conserver par défaut les motifs contenant notamment :

- `error` ;
- `fatal` ;
- `panic` ;
- `exception` ;
- `failed` ;
- `failure` ;
- `timeout` ;
- `connection refused` ;
- `permission denied` ;
- `database locked` ;
- `out of memory` ;
- `crashed` ;
- `restart`.

Afficher séparément les avertissements de configuration tels que :

- `deprecated` ;
- `warning` ;
- `invalid configuration` ;
- `unknown field`.

Ne pas mélanger automatiquement les avertissements de migration avec les erreurs bloquantes.

## Normalisation et regroupement

Créer un mécanisme de normalisation des lignes afin que des valeurs variables ne créent pas un motif différent à chaque fois.

Normaliser notamment :

- les timestamps ;
- les adresses IPv4 et IPv6 ;
- les ports ;
- les identifiants de connexion ;
- les UUID ;
- les identifiants de requêtes ;
- les numéros de socket ;
- les chemins variables si nécessaire.

Exemple :

```text
read tcp 172.19.0.4:9091->172.19.0.35:48234: i/o timeout
read tcp 172.19.0.4:9091->172.19.0.35:53312: i/o timeout
```

doit être regroupé sous un motif tel que :

```text
read tcp <IP>:<PORT>-><IP>:<PORT>: i/o timeout
```

Mais les lignes originales doivent rester disponibles dans le rapport afin de permettre une analyse manuelle.

Le regroupement doit être déterministe, documenté et réalisé sans IA.

## Interface web

Créer une interface web simple, claire et responsive avec Flask et des templates HTML propres.

La page d’accueil doit afficher :

- la date de génération du rapport ;
- la période analysée ;
- le nombre de conteneurs analysés ;
- le nombre de conteneurs avec erreurs ;
- le top 5 de chaque conteneur ;
- une section séparée pour les avertissements de configuration ;
- un lien vers les rapports historiques ;
- un bouton d’actualisation de la page qui ne lance pas de scan ;
- un bouton explicite `Lancer un scan maintenant`, si cette fonction est implémentée.

Chaque erreur doit présenter :

```text
Nom du conteneur
Nombre d’occurrences
Première apparition
Dernière apparition
Motif normalisé
Ligne exacte ou exemples exacts
```

## Bouton de copie

Pour chaque erreur, ajouter un bouton visible :

```text
Copier l’erreur exacte
```

Ce bouton doit copier dans le presse-papiers le contenu utile de l’erreur, notamment :

- nom du conteneur ;
- nombre d’occurrences ;
- motif normalisé ;
- dates première et dernière apparition ;
- lignes exactes originales ;
- éventuellement la période analysée.

Le texte copié doit être propre et directement collable dans une autre application.

Utiliser l’API navigateur `navigator.clipboard.writeText()` avec un fallback si nécessaire.

Après la copie, afficher une confirmation visuelle temporaire, par exemple :

```text
Copié !
```

Ne pas copier uniquement le motif abrégé si les lignes exactes sont disponibles.

## Historique

Prévoir une page `/reports` affichant les rapports historiques disponibles :

- date de génération ;
- période analysée ;
- nombre de conteneurs concernés ;
- lien de consultation ;
- possibilité de télécharger le rapport JSON ou texte.

Prévoir une URL lisible, par exemple :

```text
/reports/2026-08-17
```

## Sécurité web

L’application sera exposée derrière Traefik sur :

```text
https://survdocker.denisflamant.com
```

Ne pas gérer TLS dans Flask.

Fournir les labels Traefik nécessaires :

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.survdocker.rule=Host(`survdocker.denisflamant.com`)"
  - "traefik.http.routers.survdocker.entrypoints=websecure"
  - "traefik.http.routers.survdocker.tls=true"
  - "traefik.http.services.survdocker.loadbalancer.server.port=8080"
```

Prévoir l’ajout d’un middleware Authelia existant, mais ne pas inventer son nom si cela dépend de l’installation. Utiliser une variable clairement documentée, par exemple :

```yaml
- "traefik.http.routers.survdocker.middlewares=${TRAEFIK_AUTH_MIDDLEWARE}"
```

Protéger également la route de scan manuel contre les appels non authentifiés et les requêtes CSRF basiques.

Ne jamais exposer directement le port de Loki vers Internet.

## API Loki

Utiliser l’API HTTP de Loki, notamment `query_range`, pour récupérer les logs de la période concernée.

Le code doit gérer :

- pagination ou limites de résultats ;
- timeouts HTTP ;
- Loki indisponible ;
- réponse vide ;
- données mal formées ;
- timestamps nanosecondes ;
- lignes multilignes autant que possible ;
- caractères non UTF-8 ;
- absence de label `container`.

Ne pas supposer que tous les conteneurs ont le même format de log.

Ajouter une limite configurable pour éviter qu’un conteneur extrêmement bavard ne fasse exploser la mémoire :

```text
MAX_LOG_LINES_PER_CONTAINER=50000
MAX_EXAMPLES_PER_ERROR=100
MAX_ERROR_GROUPS_PER_CONTAINER=5
```

Si le nombre de lignes exactes est limité, l’indiquer clairement dans l’interface :

```text
100 lignes affichées sur 4 231 occurrences
```

## Qualité et maintenance

Fournir :

- un `Dockerfile` propre ;
- un `docker-compose.yml` complet ;
- un fichier `requirements.txt` ;
- une configuration Loki ;
- une configuration Alloy ;
- un fichier `filters.yml` ;
- un exemple de fichier `.env.example` ;
- un README complet en français ;
- une méthode de sauvegarde des rapports ;
- des logs applicatifs simples et non verbeux ;
- une route `/health` ;
- un healthcheck Docker ;
- une gestion correcte des erreurs.

Utiliser des versions d’images explicites et documenter la procédure de mise à jour. Éviter `latest` dans la version finale si cela peut provoquer une mise à jour involontaire.

L’application doit démarrer même si Loki est temporairement indisponible, mais afficher clairement l’état dans l’interface.

## Tests à fournir

Ajouter au minimum des tests unitaires pour :

- filtrage des faux positifs ;
- détection des niveaux d’erreur ;
- normalisation des IP et ports ;
- regroupement des messages ;
- classement top 5 par conteneur ;
- conservation des lignes exactes ;
- limite du nombre d’exemples ;
- génération du texte copié dans le presse-papiers.

Tester notamment ces lignes Authelia et vérifier qu’elles ne sont pas toutes classées comme des pannes :

```text
Access to https://bookstack.denisflamant.com/robots.txt is not authorized
responding with status code 401
responding with status code 302
```

Tester également ces vraies erreurs :

```text
error initializing session backend: redis connection error
connect: connection refused
Request timeout occurred while handling request from client
fatal startup failure
```

## Livrable attendu

Générer une solution fonctionnelle et documentée avec une structure de fichiers complète.

Avant de produire le code final :

1. vérifier les noms des services Docker et les réseaux ;
2. vérifier que Loki et Alloy communiquent par leur nom DNS Docker ;
3. vérifier que l’application web écoute sur `0.0.0.0:8080` ;
4. vérifier que Traefik route vers le port interne `8080` ;
5. vérifier que le scan hebdomadaire ne se lance jamais à la simple ouverture de `/` ;
6. vérifier que les rapports sont persistants ;
7. vérifier que le bouton de copie contient bien les lignes exactes ;
8. vérifier que le rapport affiche clairement les erreurs filtrées et les erreurs conservées.

Le résultat final doit être directement déployable avec Docker Compose et adapté à un serveur Docker personnel utilisant Traefik et Authelia.


# Complément de prompt GitHub Copilot — Alertes Telegram critiques

Ajoute au projet `SurvDocker` un mécanisme d’alertes Telegram réservé exclusivement aux problèmes critiques et immédiats.

## Objectif

Le rapport hebdomadaire reste affiché sur la page web et ne doit pas être envoyé intégralement sur Telegram.

Telegram doit uniquement être utilisé pour signaler une anomalie critique nécessitant une intervention rapide, par exemple :

- un conteneur qui ne démarre plus ;
- un conteneur qui redémarre en boucle ;
- une base de données inaccessible ;
- Redis inaccessible lorsqu’il est indispensable au fonctionnement d’un service ;
- une erreur de connexion persistante à PostgreSQL, MariaDB, MySQL ou SQLite ;
- un service backend indisponible ;
- une erreur `connection refused` répétée ;
- un conteneur marqué `unhealthy` ;
- une erreur `fatal`, `panic` ou un crash répété ;
- une panne de stockage ou un volume inaccessible ;
- une erreur de permission empêchant un service de fonctionner ;
- une panne de résolution DNS interne empêchant un service critique de joindre sa dépendance.

Ne pas envoyer d’alerte Telegram pour les événements suivants, sauf s’ils deviennent répétitifs et configurés explicitement comme critiques :

- les réponses HTTP 401 ;
- les réponses HTTP 302 ;
- les accès non authentifiés bloqués par Authelia ;
- les robots Internet ;
- les requêtes `robots.txt` ;
- les simples warnings ;
- les clés de configuration dépréciées ;
- les erreurs WebAuthn non bloquantes ;
- les healthchecks normaux ;
- une erreur unique et isolée de type timeout ;
- les messages de démarrage et d’arrêt normaux.

## Principe de fonctionnement

Le système doit distinguer deux traitements indépendants :

```text
Scan hebdomadaire complet
  → rapport détaillé sur le site web

Surveillance critique continue
  → alerte Telegram uniquement si nécessaire
```

Le scan hebdomadaire ne doit pas être remplacé par le système d’alerte immédiate.

L’alerte critique doit fonctionner même si aucune personne ne consulte le site web.

## Détection des conteneurs arrêtés

Le système doit vérifier régulièrement l’état des conteneurs Docker, par exemple toutes les 1 à 5 minutes.

Détecter au minimum :

- `exited` ;
- `dead` ;
- `restarting` ;
- `unhealthy` ;
- conteneur absent alors qu’il est déclaré dans la configuration attendue ;
- conteneur qui redémarre plusieurs fois pendant une période courte.

Ne pas envoyer d’alerte pour un conteneur volontairement arrêté si cette situation est explicitement déclarée comme autorisée dans la configuration.

Prévoir une liste configurable :

```yaml
ignored_containers:
  - ancien_conteneur
  - test_temporaire
```

Prévoir aussi une liste de services critiques :

```yaml
critical_containers:
  - traefik
  - authelia_df
  - authelia_pf
  - redis_df
  - redis_pf
  - postgres
  - mariadb
```

La liste doit être configurable sans reconstruire l’image.

## Détection des erreurs de dépendance

Le système doit détecter les motifs indiquant qu’un service critique ne peut plus joindre sa dépendance.

Inclure notamment :

```text
connection refused
connection reset
no route to host
host is unreachable
network is unreachable
name or service not known
temporary failure in name resolution
could not connect
failed to connect
connection timed out
 i/o timeout
server unavailable
backend unavailable
service unavailable
```

Pour les bases de données, inclure notamment :

```text
database unavailable
database connection failed
unable to connect to database
connection to database refused
could not connect to server
postgresql connection refused
mysql connection refused
mariadb connection refused
redis connection refused
redis: connection error
storage backend unavailable
session backend unavailable
```

Une alerte ne doit pas être déclenchée sur une seule occurrence isolée lorsque le service reste fonctionnel. Utiliser un seuil configurable, par exemple :

```yaml
critical_alerts:
  enabled: true
  error_threshold: 3
  error_window: 5m
  restart_threshold: 3
  restart_window: 10m
  notification_cooldown: 1h
```

## Détection des crashes et redémarrages

Déclencher une alerte si un conteneur critique redémarre au moins trois fois en dix minutes, ou si Docker indique un état `restarting`.

Le message doit contenir :

- nom du conteneur ;
- état actuel ;
- nombre de redémarrages ;
- date du premier redémarrage ;
- date du dernier redémarrage ;
- dernières lignes pertinentes du log ;
- éventuellement le code de sortie ;
- lien vers `https://survdocker.denisflamant.com`.

Exemple :

```text
🚨 ALERTE DOCKER CRITIQUE

Conteneur : authelia_pf
État : restarting
Redémarrages : 4 en 10 minutes
Cause probable : Redis inaccessible

Dernière erreur :
error initializing session backend: redis connection error
connect: connection refused

Rapport : https://survdocker.denisflamant.com
```

## Détection des bases de données

Ne pas supposer que tous les conteneurs sont des bases de données.

Prévoir une configuration explicite des dépendances :

```yaml
dependencies:
  authelia_pf:
    - authelia_redis_pf
  authelia_df:
    - authelia_redis_df
  bookstack:
    - mariadb
  application_x:
    - postgres
```

Lorsqu’un conteneur dépendant ne peut plus joindre sa base ou son backend, inclure les deux noms dans l’alerte :

```text
Service : bookstack
Dépendance inaccessible : mariadb
```

Si possible, vérifier également l’état du conteneur de dépendance et son endpoint de santé.

## Configuration Telegram

Utiliser la Telegram Bot API via HTTPS.

Ne jamais inscrire directement les secrets dans le code source.

Lire les valeurs depuis un fichier `.env` ou des secrets Docker :

```env
TELEGRAM_BOT_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=xxxxxxxxxx
TELEGRAM_ENABLED=true
```

Prévoir les variables suivantes :

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ENABLED=false
TELEGRAM_THREAD_ID=
```

L’envoi doit utiliser l’endpoint `sendMessage`.

Le texte doit être court, propre et directement exploitable. Ne jamais envoyer l’intégralité des logs sur Telegram.

Limiter l’alerte à :

- le problème détecté ;
- le conteneur concerné ;
- la cause probable ;
- quelques lignes exactes pertinentes ;
- la dernière date connue ;
- le lien vers le site SurvDocker.

## Anti-spam et déduplication

Le système doit impérativement éviter l’envoi répété d’une même alerte.

Mettre en place :

- une clé d’alerte déterministe ;
- un fichier d’état persistant ou une petite base SQLite ;
- un délai de refroidissement `notification_cooldown` ;
- un mécanisme de résolution d’alerte ;
- une alerte de rétablissement facultative.

Exemple de clé :

```text
container=authelia_pf|type=redis_connection_refused
```

Comportement attendu :

```text
Première détection → envoyer une alerte
Occurrences suivantes → ne rien envoyer pendant le cooldown
Problème résolu → marquer l’alerte comme résolue
Nouvelle panne après résolution → envoyer une nouvelle alerte
```

Prévoir une notification de rétablissement optionnelle :

```text
✅ SERVICE RÉTABLI

Conteneur : authelia_pf
Problème : Redis inaccessible
Durée estimée : 3 minutes
```

Ne pas envoyer plus d’une alerte par clé pendant la période définie.

## Architecture recommandée

Conserver la séparation suivante :

```text
Grafana Alloy
  → collecte les logs

Grafana Loki
  → conserve les logs

SurvDocker web
  → affiche le dernier rapport hebdomadaire

SurvDocker worker ou scheduler
  → exécute le scan hebdomadaire

SurvDocker critical-monitor
  → vérifie périodiquement les conteneurs et les erreurs critiques
  → envoie Telegram uniquement si nécessaire
```

Le moniteur critique peut être :

1. un service séparé dans Docker Compose ;
2. un processus séparé dans l’application, si la supervision est correctement gérée ;
3. un petit conteneur dédié réutilisant le code commun de SurvDocker.

Privilégier un service séparé `survdocker-critical-monitor`, plus facile à redémarrer et à diagnostiquer.

## Sécurité

Le moniteur aura besoin d’interroger Docker.

Préférer autant que possible :

- le socket Docker en lecture seule ;
- une autorisation minimale ;
- un proxy Docker socket dédié si nécessaire ;
- aucun accès en écriture à Docker ;
- aucun appel à `docker stop`, `docker rm`, `docker restart` ou autre action destructive.

Le système doit être strictement en lecture seule : il détecte et signale, mais ne tente pas de réparer automatiquement les conteneurs.

Ne jamais afficher le token Telegram dans l’interface web, les logs ou les rapports.

Masquer ou nettoyer les mots de passe, tokens, clés et URLs contenant des secrets avant d’inclure une ligne exacte dans Telegram.

## Gestion des erreurs Telegram

Si Telegram est indisponible :

- ne pas arrêter la surveillance ;
- enregistrer l’échec localement ;
- éviter de réessayer en boucle très rapidement ;
- réessayer avec un délai progressif ;
- conserver l’alerte pour la prochaine tentative ;
- afficher l’état Telegram dans la page SurvDocker.

Le fonctionnement de Loki, du rapport web et du scan hebdomadaire ne doit pas dépendre de Telegram.

## Tests à fournir

Ajouter des tests unitaires et d’intégration pour vérifier :

- détection d’un conteneur `exited` ;
- détection d’un conteneur `restarting` ;
- détection d’un état `unhealthy` ;
- détection d’une base de données inaccessible ;
- détection d’un Redis inaccessible ;
- seuil empêchant une alerte sur une erreur unique ;
- déduplication pendant le cooldown ;
- nouvelle alerte après résolution ;
- exclusion des codes HTTP 401 et 302 Authelia ;
- exclusion des warnings dépréciés non critiques ;
- absence d’alerte pour un conteneur ignoré ;
- nettoyage des secrets dans les lignes envoyées ;
- fonctionnement lorsque Telegram est indisponible ;
- absence d’action Docker destructive.

## Résultat attendu

Le projet doit fournir :

- les fichiers Docker Compose mis à jour ;
- le code du moniteur critique ;
- le fichier de configuration des conteneurs critiques ;
- le fichier de configuration Telegram ;
- la gestion persistante de l’état et des cooldowns ;
- les tests ;
- la documentation en français incluant explicitement une section configuration abordant tout les parametres et fichiers de configurations ;
- des exemples d’alertes Telegram ;
- une procédure pour désactiver Telegram sans désactiver SurvDocker.

Le comportement final doit être :

```text
Rapport hebdomadaire
  → disponible sur https://survdocker.denisflamant.com
  → top 5 des erreurs par conteneur
  → lignes exactes copiables

Panne critique détectée
  → alerte Telegram courte et immédiate
  → aucune avalanche de messages
  → lien vers le rapport web

Problème normal ou non critique
  → aucune alerte Telegram
  → visible dans le rapport hebdomadaire si pertinent
```
