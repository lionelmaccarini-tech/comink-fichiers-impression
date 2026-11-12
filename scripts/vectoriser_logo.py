#!/usr/bin/env python3
"""Vectorise un logo bitmap (PNG/JPG) en SVG : des tracés nets, agrandissables
à l'infini. Pour les logos à APLATS (2-8 couleurs franches, typo, pictos).
Ne convient PAS aux photos ni aux dégradés complexes — dans ce cas, demander
une source haute résolution au client.

  python3 vectoriser_logo.py logo.png [--couleurs 6] [--sortie logo_vecto.svg] [--apercu]

- --couleurs N : réduit d'abord l'image à N couleurs (nettoie le bruit JPEG).
  Par défaut : 8 pour un JPG, aucune réduction pour un PNG propre.
- --apercu : génère un PNG avant/après pour validation par le client.

Le SVG produit s'utilise ensuite comme n'importe quelle source :
  python3 preparer_fichier.py logo_vecto.svg --produit panneau --format 100x70 ...
"""
import argparse, os, subprocess, sys, tempfile
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def assurer_vtracer():
    try:
        import vtracer  # noqa: F401
        return True
    except ModuleNotFoundError:
        print('Module vtracer manquant — installation en cours…')
        for args in (['install', '--quiet', 'vtracer'], ['install', '--quiet', '--user', 'vtracer']):
            r = subprocess.run([sys.executable, '-m', 'pip'] + args)
            if r.returncode == 0:
                try:
                    import vtracer  # noqa: F401
                    return True
                except ModuleNotFoundError:
                    pass
        return False


def vectoriser_opencv(img, out, n_couleurs=8):
    """Repli sans vtracer : vectorisation par couches de couleur avec OpenCV.
    Quantifie l'image, puis trace chaque couleur (contours + trous, règle evenodd).
    Suréchantillonne x4 avant traçage pour des bords lisses."""
    import numpy as np
    try:
        import cv2
    except ModuleNotFoundError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'opencv-python-headless'])
        import cv2

    K = 4
    big = img.resize((img.width * K, img.height * K), Image.LANCZOS)
    alpha = np.asarray(big.getchannel('A'))
    rgb = big.convert('RGB')
    q = rgb.quantize(colors=n_couleurs, method=Image.MEDIANCUT)
    pal = q.getpalette()
    idx = np.asarray(q)
    visible = alpha > 127

    couches = []
    for c in np.unique(idx[visible]) if visible.any() else []:
        mask = ((idx == c) & visible).astype('uint8') * 255
        aire = int(mask.sum() / 255)
        if aire < (K * 3) ** 2:
            continue
        r_, g_, b_ = pal[c * 3], pal[c * 3 + 1], pal[c * 3 + 2]
        couches.append((aire, f'#{r_:02x}{g_:02x}{b_:02x}', mask))
    couches.sort(key=lambda t: -t[0])  # grandes zones dessous

    paths = []
    for _, coul, mask in couches:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), 'uint8'))
        cont, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
        d_parts = []
        for cnt in cont:
            if cv2.contourArea(cnt) < (K * 2) ** 2:
                continue
            approx = cv2.approxPolyDP(cnt, 0.8 * K / 2, True)
            pts = approx.reshape(-1, 2) / K
            if len(pts) < 3:
                continue
            d_parts.append('M' + ' '.join(f'{x:.2f},{y:.2f}' for x, y in pts) + 'Z')
        if d_parts:
            paths.append(f'<path d="{" ".join(d_parts)}" fill="{coul}" fill-rule="evenodd"/>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{img.width}" height="{img.height}" '
           f'viewBox="0 0 {img.width} {img.height}">' + ''.join(paths) + '</svg>')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(svg)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('source')
    a.add_argument('--couleurs', type=int, default=0, help='réduire à N couleurs avant traçage (0 = auto)')
    a.add_argument('--sortie', default=None)
    a.add_argument('--apercu', action='store_true', help='générer un PNG avant/après')
    o = a.parse_args()

    if not assurer_vtracer():
        print('  vtracer non installable ici — le traçage OpenCV de secours sera utilisé')

    src = o.source
    base = os.path.splitext(os.path.basename(src))[0]
    out = o.sortie or f'{base}_vecto.svg'

    img = Image.open(src)
    a_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
    img = img.convert('RGBA')
    w, h = img.size
    if max(w, h) < 200:
        # Trop petit = tracés baveux : on agrandit d'abord (le traçage lisse ensuite)
        k = 200 / max(w, h)
        img = img.resize((int(w * k), int(h * k)), Image.LANCZOS)
        print(f'  Source {w}x{h} px agrandie x{k:.1f} avant traçage')

    est_jpg = os.path.splitext(src)[1].lower() in ('.jpg', '.jpeg')
    n = o.couleurs or (8 if est_jpg else 0)
    if n:
        # Quantification : élimine le bruit de compression, regroupe les aplats
        alpha = img.getchannel('A')
        q = img.convert('RGB').quantize(colors=n, method=Image.MEDIANCUT).convert('RGB')
        img = q.convert('RGBA'); img.putalpha(alpha)
        print(f'  Couleurs réduites à {n} (nettoyage des aplats)')

    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, 'prep.png')
        img.save(tmp)
        # vtracer en SOUS-PROCESSUS : sur certains Python le module natif plante
        # (segfault) — isolé ainsi, l'échec est rattrapé et le repli OpenCV prend
        # le relais sans interrompre le client.
        code = (
            "import vtracer,sys;"
            "vtracer.convert_image_to_svg_py(sys.argv[1],sys.argv[2],"
            "colormode='color',hierarchical='stacked',mode='spline',"
            "filter_speckle=8,color_precision=7,layer_difference=24,"
            "corner_threshold=60,length_threshold=4.0,splice_threshold=45,path_precision=3)"
        )
        r = subprocess.run([sys.executable, '-c', code, tmp, out],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        if r.returncode != 0 or not os.path.exists(out) or os.path.getsize(out) < 100:
            print('  vtracer indisponible sur cette machine — traçage OpenCV de secours')
            vectoriser_opencv(img, out, o.couleurs or 8)

    svg = open(out, encoding='utf-8', errors='replace').read()
    n_paths = svg.count('<path')
    couleurs = len(set(p.split('"')[1] for p in svg.split('fill=')[1:] if '"' in p))
    print(f'Fichier : {out}')
    print(f'  {n_paths} tracé(s) vectoriel(s), {couleurs} couleur(s)')
    if n_paths > 300:
        print('  ATTENTION beaucoup de tracés : la source ressemble à une photo ou un dégradé —')
        print('  la vectorisation ne conviendra probablement pas. Vérifier l\'aperçu, ou demander')
        print('  le logo original (PDF/AI/SVG) au client.')
    if a_alpha:
        print('  Fond transparent conservé.')

    if o.apercu:
        try:
            import cairosvg
            ap = f'{base}_vecto_apercu.png'
            with tempfile.TemporaryDirectory() as d:
                p2 = os.path.join(d, 'v.png')
                cairosvg.svg2png(url=out, write_to=p2, output_width=max(600, img.size[0]))
                av = img.convert('RGB'); ap_img = Image.open(p2).convert('RGB')
                H = 400
                av = av.resize((int(av.width * H / av.height), H))
                ap_img = ap_img.resize((int(ap_img.width * H / ap_img.height), H))
                cmp_ = Image.new('RGB', (av.width + ap_img.width + 30, H + 30), (255, 255, 255))
                cmp_.paste(av, (10, 15)); cmp_.paste(ap_img, (av.width + 20, 15))
                cmp_.save(ap)
            print(f'  Aperçu avant/après : {ap} (gauche = original, droite = vectorisé)')
        except ImportError:
            print('  (aperçu sauté : cairosvg non installé — pip install cairosvg)')

    print('\nÉtape suivante : utiliser ce SVG comme source du PDF d\'impression, ex. :')
    print(f'  python3 preparer_fichier.py {out} --produit panneau --format 100x70 --quantite 1 --nom {base}')


if __name__ == '__main__':
    main()
