#!/usr/bin/env python3
"""Exporte un visuel HTML (créé avec Claude, par ex. depuis gabarit.py) en PDF au format exact,
fond perdu compris, fonds et images inclus. Utilise Chromium via Playwright.

  python3 exporter_html.py visuel.html visuel.pdf --largeur 1004 --hauteur 704   (mm, fond perdu compris)

Si Playwright n'est pas disponible : ouvrir le HTML dans Chrome > Imprimer > Enregistrer en PDF,
Marges : Aucune, Graphiques d'arrière-plan : coché, taille de papier personnalisée au format imprimé.
Le PDF obtenu passe ensuite dans preparer_fichier.py (avec --avec-fond-perdu)."""
import argparse, os, sys


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('html'); a.add_argument('pdf')
    a.add_argument('--largeur', type=float, required=True, help='largeur imprimée en mm (format fini + 2 x fond perdu)')
    a.add_argument('--hauteur', type=float, required=True, help='hauteur imprimée en mm')
    o = a.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('Playwright absent : pip install playwright && playwright install chromium '
                 '(ou exporter depuis Chrome, voir l\'aide de ce script).')
    url = 'file://' + os.path.abspath(o.html)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(url, wait_until='networkidle')
        pg.add_style_tag(content='.reperes, #REPERES-A-SUPPRIMER-AVANT-EXPORT { display: none !important; }')
        pg.pdf(path=o.pdf, width=f'{o.largeur}mm', height=f'{o.hauteur}mm', print_background=True,
               margin=dict(top='0', right='0', bottom='0', left='0'), prefer_css_page_size=False)
        b.close()
    from pypdf import PdfReader
    r = PdfReader(o.pdf); mb = r.pages[0].mediabox
    w, h = float(mb.width) / 72 * 25.4, float(mb.height) / 72 * 25.4
    print(f'PDF : {o.pdf} | {len(r.pages)} page(s) | {w:.1f} x {h:.1f} mm')
    if len(r.pages) > 1: print('ATTENTION : plusieurs pages, le contenu déborde du format : réduire le contenu.')
    if abs(w - o.largeur) > 0.5 or abs(h - o.hauteur) > 0.5:
        print('ATTENTION : format différent de celui demandé (Chromium arrondit au pixel) ; preparer_fichier.py le recale.')


if __name__ == '__main__':
    main()
