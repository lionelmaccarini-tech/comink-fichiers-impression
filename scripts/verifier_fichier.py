#!/usr/bin/env python3
"""Vérifie un PDF d'impression selon les spécifications Comink.

  python3 verifier_fichier.py fichier.pdf --produit panneau --format 100x70 [--decoupe aucune|rectangle] [--forme]

Affiche OK / ATTENTION / ERREUR par contrôle et renvoie le code 1 s'il y a une erreur.
--forme : découpe à la forme (stickers) : le format de page n'est pas contrôlé strictement."""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comink_pdf import PRODUITS, MM, spec, controle_fond_perdu
from pypdf import PdfReader
from pypdf.generic import ContentStream, NameObject

res = []
def ok(m): res.append(('OK', m))
def att(m): res.append(('ATTENTION', m))
def err(m): res.append(('ERREUR', m))


def resoudre(o):
    return o.get_object() if hasattr(o, 'get_object') else o


def parcourir(resources, vus, infos, ctm_page=None):
    """Inventaire récursif des ressources (polices, images, espaces de couleur, transparence)."""
    resources = resoudre(resources) or {}
    if id(resources) in vus: return
    vus.add(id(resources))
    for nom, f in (resoudre(resources.get('/Font')) or {}).items():
        f = resoudre(f); d = resoudre(f.get('/FontDescriptor'))
        if d is None and f.get('/DescendantFonts'):
            d = resoudre(resoudre(resoudre(f['/DescendantFonts'])[0]).get('/FontDescriptor'))
        incorporee = d is not None and any(k in d for k in ('/FontFile', '/FontFile2', '/FontFile3'))
        infos['polices'].append((str(f.get('/BaseFont', nom)), incorporee or f.get('/Subtype') == '/Type3'))
    for nom, cs in (resoudre(resources.get('/ColorSpace')) or {}).items():
        cs = resoudre(cs)
        if isinstance(cs, list) and cs and cs[0] in ('/Separation', '/DeviceN'):
            noms = [str(cs[1])] if cs[0] == '/Separation' else [str(n) for n in resoudre(cs[1])]
            infos['tons'] |= set(noms)
            if cs[0] == '/Separation' and str(cs[1]) == '/CutContour': infos['cc_noms'].add(str(nom))
        elif isinstance(cs, list) and cs and cs[0] == '/ICCBased' and resoudre(cs[1]).get('/N') == 3:
            infos['rvb'] += 1
        elif cs in ('/DeviceRGB', '/CalRGB'):
            infos['rvb'] += 1
    for nom, gs in (resoudre(resources.get('/ExtGState')) or {}).items():
        gs = resoudre(gs)
        if gs.get('/SMask') not in (None, '/None'): infos['transparence'] += 1
        if gs.get('/BM') not in (None, '/Normal', '/Compatible'): infos['transparence'] += 1
        if float(gs.get('/ca', 1)) < 1 or float(gs.get('/CA', 1)) < 1: infos['transparence'] += 1
    for nom, x in (resoudre(resources.get('/XObject')) or {}).items():
        x = resoudre(x)
        if '/OC' in x: infos['calques'] += 1
        if x.get('/Subtype') == '/Image':
            cs = resoudre(x.get('/ColorSpace'))
            if cs in ('/DeviceRGB', '/CalRGB') or (isinstance(cs, list) and cs and cs[0] == '/ICCBased'
                                                      and resoudre(cs[1]).get('/N') == 3):
                infos['rvb'] += 1
            if '/SMask' in x: infos['transparence'] += 1
            infos['images'][str(nom)] = (int(x['/Width']), int(x['/Height']))
        elif x.get('/Subtype') == '/Form':
            infos['formulaires'] += 1
            if '/Group' in x: infos['transparence'] += 1
            parcourir(x.get('/Resources'), vus, infos)


def mul(a, b):
    return [a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3], a[2]*b[0]+a[3]*b[2], a[2]*b[1]+a[3]*b[3],
            a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--produit', required=True, choices=list(PRODUITS))
    ap.add_argument('--format', required=True, help='format fini en cm, ex. 100x70')
    ap.add_argument('--decoupe', choices=['rectangle', 'aucune'], default=None)
    ap.add_argument('--forme', action='store_true')
    o = ap.parse_args()
    sp = spec(o.produit, o.decoupe)
    w_cm, h_cm = [float(v.replace(',', '.')) for v in o.format.lower().split('x')]
    r = PdfReader(o.pdf)
    ech = 10 if '_ECH1-10' in os.path.basename(o.pdf) else 1

    # 1. pages
    (ok if len(r.pages) == 1 else err)(f'{len(r.pages)} page(s) (une page par visuel attendue)')
    pg = r.pages[0]
    mb = [float(v) for v in pg.mediabox]
    pw, ph = (mb[2] - mb[0]) / MM * ech, (mb[3] - mb[1]) / MM * ech
    bl = sp['bleed']
    attendu = (w_cm * 10 + 2 * bl, h_cm * 10 + 2 * bl)
    if o.forme:
        ok(f'page {pw:.1f} x {ph:.1f} mm (découpe à la forme)')
    elif all(abs(a - b) <= 0.5 for a, b in zip((pw, ph), attendu)) or all(abs(a - b) <= 0.5 for a, b in zip((pw, ph), attendu[::-1])):
        ok(f'page {pw:.1f} x {ph:.1f} mm = format fini {w_cm:g} x {h_cm:g} cm' + (f' + {bl} mm de fond perdu' if bl else ''))
    else:
        err(f'page {pw:.1f} x {ph:.1f} mm, attendu {attendu[0]:.1f} x {attendu[1]:.1f} mm'
            + (f' (format fini + {bl} mm de fond perdu de chaque côté)' if bl else ' (format fini)'))
    if max(mb[2] - mb[0], mb[3] - mb[1]) > 14400:
        err('page de plus de 508 cm : refusée par le RIP, produire à l\'échelle 1:10 (_ECH1-10 dans le nom)')
    else:
        ok('page ≤ 508 cm' + (' (fichier à l\'échelle 1:10)' if ech == 10 else ''))

    # 2. inventaire
    infos = dict(polices=[], tons=set(), cc_noms=set(), rvb=0, transparence=0, calques=0, images={}, formulaires=0)
    parcourir(pg.get('/Resources'), set(), infos)
    if '/OCProperties' in r.trailer['/Root'] or infos['calques']:
        err('le fichier contient des calques : aplatir avant envoi')
    else: ok('pas de calques')
    non_inc = sorted({n for n, i in infos['polices'] if not i})
    if infos['polices']:
        err(f'{len(infos["polices"])} police(s) dans le fichier' + (f' dont NON incorporées : {", ".join(non_inc)}' if non_inc else '')
            + ' : vectoriser les textes (preparer_fichier.py le fait)')
    else: ok('aucune police')
    (err if infos['rvb'] else ok)(f'éléments RVB : {infos["rvb"]}' + (' (convertir en CMJN)' if infos['rvb'] else ''))
    autres = sorted(t for t in infos['tons'] if t not in ('/CutContour', '/Pliage', '/All', '/None'))
    (err if autres else ok)('autres tons directs : ' + (', '.join(autres) if autres else 'aucun'))
    (att if infos['transparence'] else ok)(f'transparence : {infos["transparence"]}' + (' (aplatir de préférence)' if infos['transparence'] else ''))
    (att if infos['formulaires'] else ok)(f'objets imbriqués (Form XObject) : {infos["formulaires"]}')

    # 3. CutContour : trait, jamais remplissage ; résolution des images
    cs = pg.get_contents()
    traits = rempl = 0; courant_trait = courant_rempl = False
    ctm = [1, 0, 0, 1, 0, 0]; pile = []; dpis = []
    for operandes, op in (cs.operations if cs is not None else []):
        op = op.decode() if isinstance(op, bytes) else op
        if op == 'q': pile.append(ctm)
        elif op == 'Q': ctm = pile.pop() if pile else ctm
        elif op == 'cm': ctm = mul([float(v) for v in operandes], ctm)
        elif op == 'CS': courant_trait = str(operandes[0]) in infos['cc_noms']
        elif op == 'cs': courant_rempl = str(operandes[0]) in infos['cc_noms']
        elif op in ('S', 's', 'B', 'B*', 'b', 'b*') and courant_trait: traits += 1
        elif op in ('f', 'F', 'f*', 'B', 'B*', 'b', 'b*') and courant_rempl: rempl += 1
        elif op == 'Do' and str(operandes[0]) in infos['images']:
            iw, ih = infos['images'][str(operandes[0])]
            lw = (ctm[0] ** 2 + ctm[1] ** 2) ** .5 / 72 * ech; lh = (ctm[2] ** 2 + ctm[3] ** 2) ** .5 / 72 * ech
            if lw and lh: dpis.append(min(iw / lw, ih / lh))
    if sp['cut'] or o.forme:
        if '/CutContour' not in infos['tons']: err('ton direct « CutContour » absent : pas de découpe possible')
        elif rempl: err(f'CutContour utilisé en remplissage ({rempl} fois) : il doit être en trait')
        elif not traits: err('CutContour défini mais aucun trait tracé')
        else: ok(f'CutContour : {traits} trait(s) de découpe')
    else:
        (att if '/CutContour' in infos['tons'] else ok)(
            'CutContour présent alors que ce produit est fini par l\'atelier' if '/CutContour' in infos['tons']
            else 'pas de CutContour (finition atelier)')
    if dpis:
        d = min(dpis)
        (ok if d >= sp['dpi_min'] - 0.5 else att)(f'résolution des images : {d:.0f} dpi (minimum {sp["dpi_min"]} dpi)'
            + ('' if d >= sp['dpi_min'] - 0.5 else ' : une photo sera floue ; un simple dégradé ou aplat n\'est pas concerné'))
    else:
        att('résolution : aucune image placée directement sur la page (non mesurée)')

    # 4. fond perdu réellement imprimé, côté par côté, autour de chaque trait de coupe
    if sp['cut'] in ('fini', 'bord') and not o.forme and '/CutContour' in infos['tons']:
        try:
            n, probs = controle_fond_perdu(o.pdf, sp['bleed'], sp['cut'])
            if probs:
                err(f'fond perdu non imprimé sur {len(probs)} côté(s) : ' + ', '.join(probs[:8]) + (' …' if len(probs) > 8 else '')
                    + (' : blanc juste à l\'intérieur du trait de fraisage' if sp['cut'] == 'bord' else ' : la couleur doit dépasser le trait de 3 mm'))
            elif n:
                ok(f'fond perdu imprimé sur les 4 côtés des {n} trait(s)')
            else:
                att('contrôle visuel du fond perdu sauté ici (installer poppler-utils ou ghostscript) — l\'atelier Comink le vérifiera')
        except Exception as e:
            att(f'contrôle du fond perdu impossible ({e})')
    for niveau, m in res: print(f'{niveau:9} {m}')
    n_err = sum(1 for n, _ in res if n == 'ERREUR')
    print('\nRÉSULTAT :', 'PRÊT POUR COMINK' if not n_err else f'{n_err} ERREUR(S) À CORRIGER')
    sys.exit(1 if n_err else 0)


if __name__ == '__main__':
    main()
