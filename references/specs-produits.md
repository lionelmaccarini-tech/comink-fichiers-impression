# Spécifications Comink pour les fichiers clients

Toutes les cotes « finies » sont la taille de l'objet livré. Le **document à créer** = dimensions finies + **3 mm de fond perdu de chaque côté**.

## Document à créer et pixels nécessaires

| Format fini | Document à créer | Pixels à 150 dpi | Pixels à 300 dpi |
|---|---|---|---|
| A3 29,7 × 42 cm | 303 × 426 mm | 1789 × 2516 | 3579 × 5031 |
| 50 × 70 cm | 506 × 706 mm | 2988 × 4169 | 5976 × 8339 |
| 60 × 40 cm | 606 × 406 mm | 3579 × 2398 | 7157 × 4795 |
| 100 × 70 cm | 1006 × 706 mm | 5941 × 4169 | 11882 × 8339 |
| 140 × 100 cm | 1406 × 1006 mm | 8303 × 5941 | 16606 × 11882 |
| 100 × 200 cm | 1006 × 2006 mm | 5941 × 11846 | 11882 × 23693 |

Bâche / mesh à 100 dpi : 1 m = 3937 px (+ 24 px pour 2 × 3 mm de fond perdu).

- Le **fond va jusqu'au bord du document** sur les 4 côtés : c'est le fond perdu. Un cadre ou une marge blanche = liseré blanc après découpe.
- Une image trop petite ne devient pas nette en l'agrandissant : vérifier les pixels **avant** de la placer.

## Règles communes

| Point | Règle |
|---|---|
| Format | PDF, une page par visuel, dimensions finies + 3 mm de fond perdu par côté, tolérance 0,5 mm. |
| Couleurs | CMJN. Texte noir en 100 % K. Grands aplats noirs en noir enrichi possible (C40 M30 J30 N100). |
| Polices | Aucune dans le fichier final : textes vectorisés (convertis en tracés). Pas de texte < 6 pt ni de filet < 0,5 mm. |
| Découpe | Ton direct `CutContour`, alternative CMJN 0/100/0/0 (100 % magenta), trait 0,25 pt, surimpression, jamais en remplissage. Un tracé fermé et lisse par élément. Rectangle : au format fini, donc 3 mm à l'intérieur du bord imprimé. |
| Pli | Ton direct `Pliage`, alternative CMJN 0/0/100/0 (100 % jaune), trait 0,25 pt, surimpression, ligne d'un bord à l'autre du document. |
| Structure | Pas de calque, pas de transparence active, pas d'autre ton direct. |
| Taille maximale | 508 cm de côté par page (limite PDF). Au-delà : fichier à l'échelle 1:10, nom suffixé `_ECH1-10`. |
| Nom | `COMINK_<SUPPORT>_<L>x<H>cm_<N>ex_<nom>.pdf` |

## Par support

| Support | Découpe par défaut | Résolution minimum | Recommandée | Zone de sécurité |
|---|---|---|---|---|
| Panneau rigide (Forex, alvéolaire, alu/Dibond) | CutContour au format | 150 dpi | 150 dpi | 10 mm |
| Vinyle adhésif (rectangle) | CutContour au format | 150 dpi | 300 dpi | 5 mm |
| Papier, carton, affiche | CutContour au format | 300 dpi | 300 dpi | 5 mm |
| Bâche PVC, mesh | aucune (renfort et œillets posés par l'atelier) | 72 dpi (> 3 m) / 100 dpi | 100 dpi | 30 mm |
| Textile, blackback | aucune (finition atelier) | 100 dpi | 150 dpi | 20 mm |
| Sticker découpé à la forme | CutContour à la forme | 150 dpi | 300 dpi | 2 mm |

### Stickers et lettrage découpés à la forme

- À partir d'un PNG détouré (fond transparent).
- Un CutContour **par élément** (chaque lettre ou forme séparée) ; les contre-formes (intérieur d'un « o ») sont découpées aussi.
- Le visuel est agrandi de **1 mm** autour de sa forme : la couleur dépasse le trait, sans liseré blanc. Option `--marge-blanche X` pour un bord blanc de X mm.
- Tracés lissés (courbes, pas de facettes). Élément découpé d'au moins ~5 mm.

### Plis

- Indiquer la position de chaque pli depuis le bord gauche (pli vertical) ou le haut (pli horizontal) du **format fini**.
- Exemple panneau 100 × 140 cm plié en deux : `--plis h:700`. Chevalet : un pli par face.

## Contrôles effectués par `verifier_fichier.py`

1. Dimensions de page = format fini + 3 mm par côté.
2. **Fond perdu réellement imprimé** sur les 4 côtés de chaque trait de découpe.
3. CutContour et Pliage présents si demandés, toujours en trait.
4. Aucune police.
5. Aucune image RVB, aucun autre ton direct.
6. Aucun calque ni transparence.
7. Résolution des images ≥ minimum du support.
8. Une seule page, côté ≤ 508 cm.
