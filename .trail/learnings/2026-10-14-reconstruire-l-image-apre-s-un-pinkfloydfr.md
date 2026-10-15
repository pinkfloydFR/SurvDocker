---
title: "Reconstruire l'image après un changement, sans scan"
author: PinkfloydFR
date: 2026-10-14
standing: true
---

## Decided
Les modifications de SurvDocker (`filters.py`, `analyzer.py`, config) ne prennent effet qu'après `docker compose up -d --build`. Le user demande ce rebuild après le changement.
Une fois le rebuild fait, ne lance pas de scan (`/scan-now`) : le user le déclenche lui-même ou attend le scan hebdomadaire.

_Told to Claude in 2 past sessions here, most recently on Sep 28._
