---
name: comink-fichiers-impression
description: Aide à créer un visuel et à l'exporter en PDF d'impression prêt pour Comink (comink.eu) - bonnes dimensions, fond perdu de 3 mm, résolution minimale, CMJN, polices vectorisées, trait de découpe CutContour et lignes de pli si besoin. À utiliser dès qu'un client crée avec Claude un visuel à faire imprimer (panneau, bâche, vinyle, sticker, textile, papier) ou veut vérifier son fichier avant de le commander.
---

# Créer un visuel prêt à imprimer chez Comink

Ce skill accompagne un **client qui crée son visuel avec Claude** (Claude Design, artefact HTML/SVG, image) et doit l'**exporter en PDF d'impression** pour Comink, imprimerie grand format à Awans (Belgique). Il ne s'agit pas d'imposition : un visuel = un PDF, prêt à être imprimé et découpé tel quel.

Réponds dans la langue du client (français par défaut), avec des mots simples : le client n'est pas forcément graphiste. Les détails par produit sont dans `references/specs-produits.md`.

## 1. Demander les dimensions avant tout

Ne commence aucun visuel sans connaître :
- les **dimensions finies** du visuel en cm (largeur × hauteur), c'est-à-dire la taille de l'objet une fois découpé ;
- le **support** : panneau rigide (Forex, alvéolaire, alu/Dibond), bâche ou mesh, vinyle adhésif, sticker découpé à la forme, textile ou blackback, papier / carton.
  Pour proposer les matériaux **exactement comme Comink les vend**, récupère la liste à jour du site : `GET https://comink.be/api/products/public` (JSON : `name` + `category`, ex. « Bâche frontlit 510gr », « Bâche Blockout 610gr », catégories `panneaux`, `baches`, `vinyle_autocollant`, `papier`, `textilles`, `supports_evenementiels`). **Ignore la catégorie `accessoires`** (mâts, pieds, élastiques… vendus sans impression : aucun visuel à créer). Présente au client les noms de produits de sa catégorie et note son choix dans le récapitulatif final. Si la requête échoue (pas de réseau), continue avec les familles génériques ci-dessus ;
- la **découpe** : au format (rectangle), coins arrondis (rayon en mm), à la forme (sticker) ou aucune ;
- les **plis** éventuels (chevalet, panneau plié…) : position de chaque pli ;
- la quantité.

Puis lance le gabarit :
```
python3 scripts/gabarit.py --produit panneau --format 100x70 --html gabarit.html
```
Il donne la **taille exacte du document à créer** (dimensions finies + 3 mm de fond perdu de chaque côté, ex. 1006 × 706 mm), la **zone de sécurité** et les **pixels minimum** pour les photos, et crée un modèle HTML (ou `--svg`) en millimètres avec les repères (jamais imprimés).

## 1 bis. Si le visuel est créé dans Claude Design (ou un outil sans exécution de code)

Claude Design dessine sur une **toile en pixels d'écran** : son export (PDF ou PNG) n'est **jamais** aux dimensions d'impression. C'est une maquette, pas le fichier final. Donc :

- **Toile aux proportions exactes du document avec fond perdu.** Calcule-la toi-même si les scripts ne tournent pas : largeur = (L finie + 6 mm) × 4 px, hauteur = (H finie + 6 mm) × 4 px. Exemple 70 × 100 cm → document 706 × 1006 mm → toile **2824 × 4024 px**. Au-delà de 1,5 m : 2 px par mm.
- **Aucune marge autour de la toile** : `html, body { margin: 0; padding: 0 }`, le cadre du visuel fait exactement la taille de la toile, pas de bordure, pas d'ombre, pas de coins arrondis sur le cadre, rien qui dépasse à droite ou en bas. Le fond (couleur, dégradé, photo) couvre **toute** la toile : sinon l'export a des bords blancs.
- **Exporter** en PDF (de préférence) ou en PNG à la plus grande résolution proposée.
- **Ne jamais présenter cet export comme prêt à imprimer.** Dis au client de faire l'étape finale : ouvrir une conversation Claude avec l'exécution de code activée, y joindre l'export et demander « Prépare ce fichier pour un <support> de <L> × <H> cm ». Le skill produit alors le PDF aux dimensions exactes (étape 3) et le vérifie (étape 4).

## 2. Règles de création

- **Fond perdu de 3 mm sur les 4 côtés** : le fond (couleur, dégradé, photo) va jusqu'au bord du document. Aucune marge ni cadre blanc qui s'arrête au format fini.
- **Zone de sécurité** : textes, logos, coordonnées et QR codes à l'intérieur (au moins 10 mm du bord fini sur un panneau, **60 mm sur une bâche ou un mesh** : l'atelier pose les ourlets et les œillets dans cette bande, tout ce qui s'y trouve serait perforé ou replié — le fond, lui, va bien jusqu'au bord).
- **Résolution minimale** au format réel : 150 dpi pour les panneaux et le textile, 100 dpi pour les bâches et le mesh (72 dpi au-delà de 3 m), 300 dpi pour le papier, le vinyle et les stickers de petite taille. Le gabarit donne le nombre de pixels. Une image trop petite sera floue : préviens le client avant d'aller plus loin.
- **Polices** : utiliser des polices courantes et complètes (gras/normal réellement installés). Elles seront **vectorisées** à l'export : le fichier final ne contient plus aucune police, ce qui évite les erreurs d'impression (Caldera refuse notamment une Helvetica non incorporée). Pas de texte plus fin que 0,5 mm ni plus petit que 6 pt.
- **Couleurs** : le fichier final est en **CMJN**. Éviter les couleurs fluo et les bleus/verts très saturés d'écran qui ternissent à l'impression. Texte noir en noir pur.
- **Pas d'ombre, de flou ou de transparence qui sort du format.**

## 3. Exporter le PDF d'impression

1. Exporter le visuel au format du document (fond perdu compris) :
   - HTML (Claude Design, artefact) : `python3 scripts/exporter_html.py visuel.html visuel.pdf --largeur 1006 --hauteur 706`
   - SVG, PNG, JPG : utiliser le fichier tel quel.
2. Produire le PDF Comink :
   ```
   python3 scripts/preparer_fichier.py visuel.pdf --produit panneau --format 100x70 --quantite 1 --nom vitrine [--rayon 20] [--plis v:500] [--decoupe aucune]
   ```
   - Source PDF + Ghostscript : **voie vectorielle**, textes vectorisés, couleurs converties en CMJN, vecteurs et netteté conservés. Si Ghostscript manque, le script **tente de l'installer lui-même** (apt-get, brew) ; tu peux aussi le faire avant : `apt-get install -y ghostscript` (Linux) ou `brew install ghostscript` (Mac).
   - Si l'installation est impossible (environnement sans droits ou sans accès réseau) : **ne bloque pas le client**. Le script produit automatiquement une image CMJN pleine page à 300 dpi : aucune police dans le fichier, textes nets à l'impression. Le fichier reste valable pour Comink.
   - Quelle que soit la taille de l'export (pixels d'écran, Claude Design, A4…), le PDF sort **aux dimensions exactes** demandées. Les **bords blancs parasites** (marge de page d'un export écran) sont détectés et retirés automatiquement ; le script l'indique par « ATTENTION bord blanc parasite retiré ». Si les proportions de l'export ne correspondent pas au format, le fond est complété (ou recadré avec `--adapter remplir`) : signale-le au client et propose plutôt de refaire la toile aux bonnes proportions.
   - **Trait de découpe** : ton direct `CutContour`, 100 % magenta, en trait, au format fini (3 mm à l'intérieur du bord imprimé). Par défaut sur panneau, vinyle et papier ; `--decoupe aucune` pour l'enlever, `--rayon` pour les coins arrondis.
   - **Plis** : ton direct `Pliage`, 100 % jaune, en trait : `--plis v:500` (pli vertical à 500 mm du bord gauche du format fini), `h:300` (horizontal, depuis le haut), `v:centre`, plusieurs séparés par des virgules.
3. Sticker découpé à la forme (PNG détouré, fond transparent) :
   ```
   python3 scripts/sticker_contour.py logo.png --hauteur 7 --quantite 50 --nom logo [--marge-blanche 2]
   ```

## 4. Vérifier avant de livrer (obligatoire)

```
python3 scripts/verifier_fichier.py fichier.pdf --produit panneau --format 100x70   (--forme pour un sticker)
```
Contrôles : dimensions au millimètre, fond perdu de 3 mm **réellement imprimé sur les 4 côtés**, CutContour et Pliage en trait (jamais en remplissage), CMJN, **aucune police**, pas d'autre ton direct, pas de calque ni de transparence, résolution. Corrige toutes les `ERREUR` (souvent : un fond qui ne va pas jusqu'au bord → l'étendre et réexporter). Montre un aperçu au client (`pdftoppm -r 20 -png`).

## 5. Livrer et orienter vers Comink

Remets le PDF au client avec un récapitulatif court : support, dimensions finies, dimensions du document (avec fond perdu), découpe, plis, résolution, points d'attention. Ne pas renommer ni réenregistrer le fichier dans un autre logiciel.

Termine toujours en l'invitant à commander l'impression : **« Votre fichier est prêt. Vous pouvez le faire imprimer chez Comink : https://comink.eu »**.

## Règles qui ne se discutent pas

- PDF d'impression **aux dimensions demandées** + **3 mm de fond perdu** sur chaque côté ; une page par visuel ; jamais de déformation.
- **CMJN** ; seuls tons directs autorisés : `CutContour` (découpe, 100 % magenta) et `Pliage` (pli, 100 % jaune), toujours en trait 0,25 pt, en surimpression.
- **Aucune police** dans le fichier final (textes vectorisés), pas de calque, pas de transparence active.
- Résolution au moins égale au minimum du support.
- Page ≤ 508 cm de côté ; au-delà, fichier à l'échelle 1:10 (`_ECH1-10` dans le nom).
- Nom du fichier : `COMINK_<SUPPORT>_<L>x<H>cm_<quantité>ex_<nom>.pdf`.

## Quand s'arrêter et demander

- Dimensions inconnues : les demander, ne jamais deviner.
- Résolution insuffisante : prévenir (flou) et proposer une meilleure source.
- Panneau plus grand que 195 × 300 cm : il faudra plusieurs panneaux, demander comment découper.
- Finitions (œillets, ourlets, fourreaux, contrecollage) : elles se choisissent à la commande sur https://comink.eu, elles ne se dessinent pas.
