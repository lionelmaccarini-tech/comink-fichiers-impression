# Skill Comink pour Claude — fichiers prêts à imprimer

Ce skill apprend à [Claude](https://claude.ai) toutes les règles de l'impression grand format chez [Comink](https://comink.be) (Awans, Belgique) : il produit des **PDF prêts à imprimer** — dimensions exactes, fond perdu de 3 mm, CMJN, trait de découpe CutContour, polices vectorisées.

## Installation

1. Téléchargez ce dépôt en ZIP (bouton **Code → Download ZIP**) ou récupérez le ZIP prêt à l'emploi sur [comink.be/telechargements](https://comink.be/telechargements).
2. Sur claude.ai : **Paramètres → Capacités → Skills → Téléverser un skill**, puis sélectionnez le ZIP.
3. Vérifiez que l'**exécution de code** est activée (même page Capacités).

## Utilisation

Ouvrez une conversation et décrivez votre projet :

> Crée-moi un panneau 100 × 70 cm pour ma vitrine…

ou joignez un visuel existant (PNG, PDF, maquette) :

> Prépare ce fichier pour un panneau de 100 × 70 cm.

Claude applique le gabarit, exporte le PDF aux dimensions exactes et le vérifie point par point avant de vous le remettre.

Mode d'emploi complet : **[comink.be/claude](https://comink.be/claude)**

## Contenu

- `SKILL.md` — les instructions du skill
- `references/specs-produits.md` — les spécifications par support (panneau, bâche, vinyle, sticker, textile, papier…)
- `scripts/` — gabarit, préparation du PDF (CMJN, CutContour, plis), contour de sticker, vérification finale

## Supports couverts

Panneaux rigides (Forex, Dibond, alvéolaire), bâches et mesh, vinyles adhésifs, stickers découpés à la forme, textiles et blackback, affiches papier.

---

© Comink — [comink.be](https://comink.be) · Les finitions (œillets, ourlets, contrecollage…) se choisissent à la commande.
