#!/usr/bin/env python3
"""Gabarit de création : donne les dimensions exactes du visuel à dessiner (mm et pixels) et crée
un modèle HTML (ou SVG) au bon format, fond perdu compris, avec les repères de coupe et de sécurité.

  python3 gabarit.py --produit panneau --format 100x70 [--html gabarit.html] [--svg gabarit.svg]

Le modèle HTML est en millimètres (unités CSS mm) : il s'exporte en PDF au format exact
avec exporter_html.py. Les repères (classe .reperes) ne sont jamais imprimés."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comink_pdf import PRODUITS, spec

HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{titre}</title>
<style>
  /* Format imprimé = format fini {w:g} x {h:g} mm + fond perdu {b:g} mm de chaque côté */
  @page {{ size: {pw:g}mm {ph:g}mm; margin: 0; }}
  html, body {{ margin: 0; padding: 0; }}
  .page {{ position: relative; width: {pw:g}mm; height: {ph:g}mm; overflow: hidden;
          background: #ffffff; /* LE FOND DOIT COUVRIR TOUTE LA PAGE, fond perdu compris */ }}
  /* Zone de sécurité : textes et logos importants à l'intérieur */
  .securite {{ position: absolute; left: {sx:g}mm; top: {sx:g}mm; width: {sw:g}mm; height: {sh:g}mm; }}
  .reperes div {{ position: absolute; box-sizing: border-box; pointer-events: none; }}
  .reperes .coupe {{ left: {b:g}mm; top: {b:g}mm; width: {w:g}mm; height: {h:g}mm; border: 0.3mm dashed #e4007c; }}
  .reperes .secu {{ left: {sx:g}mm; top: {sx:g}mm; width: {sw:g}mm; height: {sh:g}mm; border: 0.3mm dotted #00a0e0; }}
  @media print {{ .reperes {{ display: none; }} }}
</style></head>
<body>
  <div class="page">
    <!-- Fond : étendre jusqu'au bord de .page (fond perdu compris) -->
    <div class="securite">
      <!-- Contenu important ici -->
    </div>
    <div class="reperes"><div class="coupe"></div><div class="secu"></div></div>
  </div>
</body></html>
"""

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="{pw:g}mm" height="{ph:g}mm" viewBox="0 0 {pw:g} {ph:g}">
  <!-- Format imprimé {pw:g} x {ph:g} mm = format fini {w:g} x {h:g} mm + fond perdu {b:g} mm. Unités du viewBox : mm. -->
  <rect id="fond" x="0" y="0" width="{pw:g}" height="{ph:g}" fill="#ffffff"/>
  <!-- Contenu important entre x={sx:g} et {sx2:g}, y={sx:g} et {sy2:g} -->
  <g id="REPERES-A-SUPPRIMER-AVANT-EXPORT" fill="none" stroke-width="0.3">
    <rect x="{b:g}" y="{b:g}" width="{w:g}" height="{h:g}" stroke="#e4007c" stroke-dasharray="2 1"/>
    <rect x="{sx:g}" y="{sx:g}" width="{sw:g}" height="{sh:g}" stroke="#00a0e0" stroke-dasharray="0.6 0.6"/>
  </g>
</svg>
"""


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--produit', required=True, choices=[p for p in PRODUITS if p != 'sticker'])
    a.add_argument('--format', required=True, help='format fini en cm, ex. 100x70')
    a.add_argument('--html'); a.add_argument('--svg')
    o = a.parse_args()
    sp = spec(o.produit)
    w, h = [float(v.replace(',', '.')) * 10 for v in o.format.lower().split('x')]
    b = sp['bleed']; pw, ph = w + 2 * b, h + 2 * b
    sx = b + sp['securite']; sw, sh = w - 2 * sp['securite'], h - 2 * sp['securite']
    print(f'Produit : {o.produit} | format fini {w:g} x {h:g} mm')
    print(f'Document à créer : {pw:g} x {ph:g} mm' + (f' (fond perdu {b:g} mm de chaque côté, le fond va jusqu\'au bord)' if b else ' (sans fond perdu)'))
    f = 4 if max(pw, ph) <= 1500 else (2 if max(pw, ph) <= 3000 else 1)
    print(f'Toile Claude Design / écran (mêmes proportions, {f} px par mm) : {round(pw * f)} x {round(ph * f)} px, '
          'sans marge, fond jusqu\'au bord')
    print(f'Zone de sécurité : {sp["securite"]} mm à l\'intérieur du format fini ({sw:g} x {sh:g} mm)')
    print('Pixels nécessaires pour les images pleine page :')
    for dpi in sorted({sp['dpi_min'], sp['dpi'], 300} if sp['dpi'] < 300 else {sp['dpi_min'], sp['dpi']}):
        tag = 'minimum' if dpi == sp['dpi_min'] else ('recommandé' if dpi == sp['dpi'] else 'confort')
        print(f'  {dpi:>3} dpi ({tag}) : {round(pw / 25.4 * dpi)} x {round(ph / 25.4 * dpi)} px')
    print('Règle simple : une photo de N pixels de large couvre au plus N / ' f'{sp["dpi_min"]} x 2,54 cm de large.')
    vals = dict(w=w, h=h, b=b, pw=pw, ph=ph, sx=sx, sw=sw, sh=sh, sx2=sx + sw, sy2=sx + sh,
                titre=f'Comink {o.produit} {w / 10:g}x{h / 10:g} cm')
    if o.html:
        open(o.html, 'w').write(HTML.format(**vals)); print(f'Modèle HTML : {o.html}')
    if o.svg:
        open(o.svg, 'w').write(SVG.format(**vals)); print(f'Modèle SVG : {o.svg}')


if __name__ == '__main__':
    main()
