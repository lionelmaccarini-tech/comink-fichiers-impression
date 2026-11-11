#!/usr/bin/env python3
"""Prépare le PDF d'impression Comink d'un visuel : format exact + 3 mm de fond perdu, CMJN,
polices vectorisées, CutContour (découpe, magenta) et Pliage (plis, jaune) si besoin.

Exemples :
  python3 preparer_fichier.py affiche.pdf --produit panneau --format 100x70 --nom vitrine
  python3 preparer_fichier.py logo.png --produit panneau --format 60x60 --rayon 30 --nom enseigne
  python3 preparer_fichier.py panneau.pdf --produit panneau --format 100x140 --plis v:500 --nom immo
  python3 preparer_fichier.py bache.jpg --produit bache --format 300x100 --nom chantier

Voie vectorielle (source PDF + Ghostscript) : textes vectorisés, vecteurs conservés.
Sinon : image CMJN pleine page à la résolution du produit + traits vectoriels (aucune police)."""
import argparse, os, shutil, subprocess, sys, tempfile
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comink_pdf import (PRODUITS, MAX_PIXELS, MM, RasterIndisponible, rasteriser_pdf, spec, nom_fichier, charger_source, adapter, rgb_vers_cmjn,
                        rect_arrondi, ecrire_pdf, controle_fond_perdu, boites_pdf, gs_dispo, mettre_au_format,
                        vectoriser_cmjn, ajouter_traits_pdf, bords_blancs)


def plis_traces(spec_plis, bl, W, H):
    """'v:500,h:300,v:centre' -> segments PDF (points). Positions en mm depuis le bord gauche / haut du format fini."""
    out = []
    for item in [x for x in (spec_plis or '').split(',') if x.strip()]:
        sens, pos = item.strip().lower().split(':')
        if sens == 'v':
            x = (W / 2 if pos == 'centre' else float(pos)) + bl
            out.append(f'{x * MM:.3f} 0 m {x * MM:.3f} {(H + 2 * bl) * MM:.3f} l')
        else:
            y = (H / 2 if pos == 'centre' else float(pos)) + bl
            yy = (H + 2 * bl - y) * MM
            out.append(f'0 {yy:.3f} m {(W + 2 * bl) * MM:.3f} {yy:.3f} l')
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('source')
    a.add_argument('--produit', required=True, choices=[p for p in PRODUITS if p != 'sticker'])
    a.add_argument('--format', required=True, help='format fini en cm, largeur x hauteur (ex. 100x70)')
    a.add_argument('--quantite', type=int, default=1)
    a.add_argument('--nom', default=None, help='nom court du visuel (pour le nom de fichier)')
    a.add_argument('--decoupe', choices=['rectangle', 'aucune'], default=None,
                   help='trait de découpe CutContour au format fini (défaut selon le produit)')
    a.add_argument('--rayon', type=float, default=0, help='coins arrondis de la découpe, rayon en mm')
    a.add_argument('--plis', default='', help="lignes de pli en jaune : 'v:500' (vertical à 500 mm du bord gauche), "
                                              "'h:300' (horizontal à 300 mm du haut), 'v:centre' ; séparées par des virgules")
    a.add_argument('--adapter', choices=['completer', 'remplir'], default='completer',
                   help="proportions différentes : 'completer' (étire le bord) ou 'remplir' (recadre)")
    a.add_argument('--raster', action='store_true', help='forcer la sortie image (sans voie vectorielle)')
    a.add_argument('--dpi', type=int, default=None, help='résolution de la sortie image (défaut selon le produit)')
    a.add_argument('--sortie', default='.', help='dossier de sortie')
    o = a.parse_args()

    w_cm, h_cm = [float(v.replace(',', '.')) for v in o.format.lower().split('x')]
    sp = spec(o.produit, o.decoupe)
    W_mm, H_mm = w_cm * 10, h_cm * 10
    bl = sp['bleed']
    page_w, page_h = W_mm + 2 * bl, H_mm + 2 * bl
    cuts = [rect_arrondi(bl * MM, bl * MM, W_mm * MM, H_mm * MM, o.rayon * MM)] if sp['decoupe'] == 'rectangle' else []
    plis = plis_traces(o.plis, bl, W_mm, H_mm)
    os.makedirs(o.sortie, exist_ok=True)
    nom = o.nom or os.path.splitext(os.path.basename(o.source))[0]
    ech_prevue = 10 if max(page_w, page_h) * MM > 14400 else 1
    out = os.path.join(o.sortie, nom_fichier(sp['nom'], w_cm, h_cm, o.quantite, nom, ech_prevue))
    notes = []

    # ---------- voie vectorielle ----------
    voie = 'image'; note_vb = None
    gs = gs_dispo() if (o.source.lower().endswith('.pdf') and not o.raster and ech_prevue == 1) else None
    if o.source.lower().endswith('.pdf') and not o.raster and ech_prevue == 1 and not gs:
        notes.append('Ghostscript indisponible : textes convertis en image haute définition (aucune police, net à l\'impression)')
    if gs:
        mb, tb, bb = boites_pdf(o.source)
        trim_dif = any(abs(a_ - b_) > 0.5 for a_, b_ in zip(mb, tb))
        # zone à reprendre : TrimBox + 3 mm si le fichier a un vrai fond perdu, sinon la page entière
        if trim_dif and min(tb[0] - max(mb[0], bb[0]), tb[1] - max(mb[1], bb[1]), min(mb[2], bb[2]) - tb[2],
                            min(mb[3], bb[3]) - tb[3]) >= bl * MM - 0.3:
            e = bl * MM * (tb[2] - tb[0]) / (W_mm * MM)
            zone = [tb[0] - e, tb[1] - e, tb[2] + e, tb[3] + e]
        else:
            zone = mb
        # bords blancs parasites (marge de page d'un export écran) : on les retire
        try:
            with tempfile.TemporaryDirectory() as d:
                dpi_ap = max(20, int(1500 / ((mb[2] - mb[0]) / 72)))
                rasteriser_pdf(o.source, dpi_ap, os.path.join(d, 'p.png'))
                ap = Image.open(os.path.join(d, 'p.png')); ap.load()
            k = ap.size[0] / (mb[2] - mb[0])
            gx0, gy0 = (zone[0] - mb[0]) * k, (mb[3] - zone[3]) * k
            sous = ap.crop((int(gx0), int(gy0), int(gx0 + (zone[2] - zone[0]) * k), int(gy0 + (zone[3] - zone[1]) * k)))
            bg, bh_, bd, bb_ = [v / k for v in bords_blancs(sous)]
            if any((bg, bh_, bd, bb_)):
                zone = [zone[0] + bg, zone[1] + bb_, zone[2] - bd, zone[3] - bh_]
                note_vb = ('ATTENTION bord blanc parasite retiré (' + ', '.join(n for n, v in
                           zip(('gauche', 'haut', 'droite', 'bas'), (bg, bh_, bd, bb_)) if v) + ')')
                trim_dif = True
        except RasterIndisponible:
            notes.append('détection des bords blancs sautée (ni pdftoppm ni Ghostscript)')
        zw, zh = zone[2] - zone[0], zone[3] - zone[1]
        if abs(zw / zh - page_w / page_h) / (page_w / page_h) < 0.004:
            with tempfile.TemporaryDirectory() as d:
                import pikepdf
                src = pikepdf.open(o.source); src.pages[0].MediaBox = pikepdf.Array(zone)
                del src.pages[1:]; src.save(os.path.join(d, 'a.pdf'))
                mettre_au_format(os.path.join(d, 'a.pdf'), os.path.join(d, 'b.pdf'), page_w, page_h)
                vectoriser_cmjn(os.path.join(d, 'b.pdf'), os.path.join(d, 'c.pdf'))
                shutil.copyfile(os.path.join(d, 'c.pdf'), out)
            ajouter_traits_pdf(out, page_w, page_h, cuts, plis)
            voie = 'vectorielle'
            if note_vb: notes.append(note_vb)
            notes.append('fond perdu de 3 mm repris du visuel' if zone is not mb or trim_dif else
                         'page source = format imprimé (fond perdu compris)')
        elif abs(zw / zh - W_mm / H_mm) / (W_mm / H_mm) < 0.004:
            notes.append('le visuel n\'a pas de fond perdu : voie image avec fond perdu miroir '
                         '(mieux : refaire le visuel avec 3 mm de fond perdu)')
        else:
            notes.append('proportions différentes du format : voie image')

    # ---------- voie image ----------
    if voie == 'image':
        dpi = o.dpi or sp['dpi']
        if not o.dpi and o.source.lower().endswith(('.pdf', '.svg')):
            dpi = max(dpi, 300)          # source vectorielle rendue en image : 300 dpi pour des textes nets
        while (page_w / 25.4 * dpi) * (page_h / 25.4 * dpi) > MAX_PIXELS and dpi > sp['dpi_min']:
            dpi -= 10
        Wpx, Hpx = round(W_mm / 25.4 * dpi), round(H_mm / 25.4 * dpi)
        bpx = round(bl / 25.4 * dpi)
        img, rect, dispo, rdpi = charger_source(o.source, dpi)
        x0, y0, x1, y1 = rect
        reduc = max(1, (x1 - x0) / 1500)
        vue = img.crop(tuple(int(v) for v in rect)).convert('RGB')
        vue = vue.resize((max(1, int(vue.size[0] / reduc)), max(1, int(vue.size[1] / reduc))))
        bg, bh_, bd, bb_ = [v * reduc for v in bords_blancs(vue)]
        if any((bg, bh_, bd, bb_)):
            rect = (x0 + bg, y0 + bh_, x1 - bd, y1 - bb_)
            dispo = [0 if bg else dispo[0], 0 if bb_ else dispo[1], 0 if bd else dispo[2], 0 if bh_ else dispo[3]]
            mmpx = (W_mm + 2 * bl) / max(1, (x1 - x0))
            notes.append('ATTENTION bord blanc parasite retiré (' + ', '.join(f'{n} {v * mmpx:.0f} mm' for n, v in
                         zip(('gauche', 'haut', 'droite', 'bas'), (bg, bh_, bd, bb_)) if v) + ')')
        rw, rh = rect[2] - rect[0], rect[3] - rect[1]
        r_fp = page_w / page_h
        if max(dispo) == 0 and abs(rw / rh - r_fp) / r_fp < 0.004 and abs(rw / rh - W_mm / H_mm) / (W_mm / H_mm) > 0.002:
            e = rw * bl / page_w
            rect = (rect[0] + e, rect[1] + e, rect[2] - e, rect[3] - e); dispo = [e] * 4
        sortie_img, _, note = adapter(img, rect, dispo, Wpx, Hpx, bpx, o.adapter)
        notes.append(note)
        if rdpi is None:
            f = min if o.adapter == 'completer' else max
            eff = f(rw / (W_mm / 25.4), rh / (H_mm / 25.4))
            if eff < sp['dpi_min']:
                notes.append(f'ATTENTION résolution de la source ≈ {eff:.0f} dpi (minimum {sp["dpi_min"]}) : rendu flou')
        ecrire_pdf(out, rgb_vers_cmjn(sortie_img), page_w, page_h, cuts, dpi=dpi, traces_pli=plis)
        notes.append(f'image CMJN {Wpx + 2 * bpx} x {Hpx + 2 * bpx} px à {dpi} dpi, textes rastérisés (aucune police)')

    print(f'Fichier : {out}')
    print(f'  {o.produit} | format fini {w_cm:g} x {h_cm:g} cm | page {page_w:g} x {page_h:g} mm (fond perdu {bl} mm)'
          + (' | ÉCHELLE 1:10' if ech_prevue == 10 else ''))
    print(f'  Voie {voie} | ' + ' | '.join(notes))
    print('  Découpe : ' + (f'CutContour au format fini' + (f', coins R{o.rayon:g} mm' if o.rayon else '') if cuts else 'aucune')
          + (f' | Plis (Pliage, jaune) : {len(plis)}' if plis else ''))
    if cuts:
        n, probs = controle_fond_perdu(out, bl, 'fini')
        if n:
            print('  Fond perdu imprimé sur les 4 côtés : OK' if not probs else
                  '  ERREUR fond perdu non imprimé : ' + ', '.join(probs) + ' (étendre le fond du visuel jusqu\'au bord)')


if __name__ == '__main__':
    try:
        main()
    except RasterIndisponible as e:
        sys.exit(f'ERREUR : impossible de lire ce PDF ici — {e}\n'
                 'Autre solution : exporter le visuel en PNG haute résolution et relancer avec le PNG.')
