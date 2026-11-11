#!/usr/bin/env python3
"""Sticker / lettrage découpé à la forme depuis un PNG détouré (fond transparent).

  python3 sticker_contour.py logo.png --hauteur 7 --quantite 50 --nom logo [--marge-blanche 0] [--fond-perdu 1]

- Un CutContour fermé et lissé par élément (chaque lettre ou forme séparée a son trait ; les contre-formes,
  l'intérieur d'un « o » par exemple, sont aussi découpées).
- --fond-perdu (mm, défaut 1) : le visuel est agrandi de cette valeur autour de sa forme ; le trait suit
  la forme d'origine, la couleur dépasse donc le trait (pas de liseré blanc).
- --marge-blanche (mm, défaut 0) : trait placé à X mm autour de la forme, avec un bord blanc
  (les éléments proches fusionnent alors en une seule forme)."""
import argparse, math, os, subprocess, sys
import numpy as np
try:
    import cv2
except ModuleNotFoundError:
    print('Module OpenCV manquant — installation en cours (opencv-python-headless)…')
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'opencv-python-headless'])
    if r.returncode != 0:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', '--user', 'opencv-python-headless'])
    try:
        import cv2
    except ModuleNotFoundError:
        sys.exit("ERREUR : OpenCV est nécessaire pour tracer le contour de découpe.\n"
                 "Installer avec : pip install opencv-python-headless")
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comink_pdf import MM, nom_fichier, rgb_vers_cmjn, ecrire_pdf

Image.MAX_IMAGE_PIXELS = None


def rdp(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1e-9
    d = [abs(dy * (p[0] - a[0]) - dx * (p[1] - a[1])) / L for p in pts[1:-1]]
    i = int(np.argmax(d)) + 1
    if d[i - 1] > eps: return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [a, b]


def lisser(pts, eps, angle_vif=55):
    """Polyligne fermée -> courbe de Bézier fermée (tracé PDF), angles vifs conservés."""
    far = max(range(len(pts)), key=lambda i: math.dist(pts[0], pts[i]))
    P = rdp(pts[:far + 1], eps)[:-1] + rdp(pts[far:] + [pts[0]], eps)[:-1]
    n = len(P)
    if n < 3: return None
    def ang(i):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        v1 = (b[0] - a[0], b[1] - a[1]); v2 = (c[0] - b[0], c[1] - b[1])
        return abs(math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])))
    vif = [ang(i) > angle_vif for i in range(n)]
    tg = []
    for i in range(n):
        a, c = P[i - 1], P[(i + 1) % n]; t = (c[0] - a[0], c[1] - a[1]); L = math.hypot(*t) or 1e-9
        tg.append((t[0] / L, t[1] / L))
    out = [f'{P[0][0]:.3f} {P[0][1]:.3f} m']
    for i in range(n):
        j = (i + 1) % n; p0, p1 = P[i], P[j]; L = math.dist(p0, p1)
        l0 = min(L, math.dist(P[i - 1], p0)) / 3; l1 = min(L, math.dist(p1, P[(j + 1) % n])) / 3
        c1 = (p0[0] + (p1[0] - p0[0]) / 3, p0[1] + (p1[1] - p0[1]) / 3) if vif[i] else (p0[0] + tg[i][0] * l0, p0[1] + tg[i][1] * l0)
        c2 = (p1[0] - (p1[0] - p0[0]) / 3, p1[1] - (p1[1] - p0[1]) / 3) if vif[j] else (p1[0] - tg[j][0] * l1, p1[1] - tg[j][1] * l1)
        out.append(f'{c1[0]:.3f} {c1[1]:.3f} {c2[0]:.3f} {c2[1]:.3f} {p1[0]:.3f} {p1[1]:.3f} c')
    return ' '.join(out) + ' h'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('png')
    ap.add_argument('--hauteur', type=float, help='hauteur du visuel en cm')
    ap.add_argument('--largeur', type=float, help='largeur du visuel en cm (si pas de hauteur)')
    ap.add_argument('--quantite', type=int, default=1)
    ap.add_argument('--nom', default=None)
    ap.add_argument('--fond-perdu', type=float, default=1.0, help='mm de couleur au-delà du trait (défaut 1)')
    ap.add_argument('--marge-blanche', type=float, default=0.0, help='mm de bord blanc entre le visuel et le trait')
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--sortie', default='.')
    o = ap.parse_args()
    if not (o.hauteur or o.largeur): ap.error('indiquer --hauteur ou --largeur (cm)')

    src = Image.open(o.png).convert('RGBA')
    al = np.asarray(src)[..., 3]
    if al.min() > 200: raise SystemExit('Le PNG n\'a pas de transparence : détourez le visuel (fond transparent) d\'abord.')
    ys, xs = np.where(al > 127)
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    vis_mm = (o.hauteur * 10, bh) if o.hauteur else (o.largeur * 10, bw)
    dpi = o.dpi
    k = vis_mm[0] / vis_mm[1] / 25.4 * dpi            # facteur de rééchelle source -> sortie
    eff_dpi = dpi / k
    marge_mm = o.marge_blanche + o.fond_perdu + 2   # cadre autour du visuel
    pad = int(math.ceil(marge_mm / 25.4 * dpi))
    crop = src.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    W, H = max(1, round(bw * k)), max(1, round(bh * k))
    crop = crop.resize((W, H), Image.LANCZOS)
    rgba = np.zeros((H + 2 * pad, W + 2 * pad, 4), np.uint8); rgba[pad:pad + H, pad:pad + W] = np.asarray(crop)
    forme = (rgba[..., 3] > 127).astype(np.uint8)
    px = lambda mm: max(0, int(round(mm / 25.4 * dpi)))
    disque = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))

    # trait : forme d'origine (ou dilatée de la marge blanche)
    trait = cv2.dilate(forme, disque(px(o.marge_blanche))) if o.marge_blanche > 0 else forme
    # visuel : agrandi du fond perdu au-delà du trait, en prolongeant la couleur la plus proche
    zone = cv2.dilate(trait, disque(px(o.fond_perdu))) if o.fond_perdu > 0 else trait
    opaque = rgba[..., 3] > 127
    coeur = rgba[..., 3] >= 250                       # pixels pleinement opaques : couleur de référence
    if not coeur.any(): coeur = opaque
    _, lab = cv2.distanceTransformWithLabels((~coeur).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    zy, zx = np.where(coeur); table = np.zeros((lab.max() + 1, 2), np.int64); table[lab[zy, zx]] = np.stack([zy, zx], 1)
    rgb = rgba[..., :3]
    proche = rgb[table[lab][..., 0], table[lab][..., 1]]   # couleur opaque la plus proche (bords sans halo blanc)
    if o.marge_blanche > 0:
        img = np.where(opaque[..., None], np.where(coeur[..., None], rgb, proche), 255).astype(np.uint8)
    else:
        img = np.where(coeur[..., None], rgb, np.where((zone > 0)[..., None], proche, 255)).astype(np.uint8)
    page_h_px, page_w_px = img.shape[:2]
    page_w_mm, page_h_mm = page_w_px / dpi * 25.4, page_h_px / dpi * 25.4

    # contours -> tracés PDF (origine en bas à gauche, en points)
    cnts, hier = cv2.findContours(trait, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    s = 72 / dpi; traces = []
    for c in cnts:
        if cv2.contourArea(c) < (px(0.8)) ** 2: continue
        pts = [(float(p[0][0]) * s, (page_h_px - float(p[0][1])) * s) for p in c]
        t = lisser(pts, 0.25 * MM)
        if t: traces.append(t)

    os.makedirs(o.sortie, exist_ok=True)
    nom = o.nom or os.path.splitext(os.path.basename(o.png))[0]
    w_cm, h_cm = round(page_w_mm / 10, 1), round(page_h_mm / 10, 1)
    out = os.path.join(o.sortie, nom_fichier('STICKER', w_cm, h_cm, o.quantite, nom))
    ecrire_pdf(out, rgb_vers_cmjn(Image.fromarray(img)), page_w_mm, page_h_mm, traces, dpi=dpi)
    print(f'Fichier : {out}')
    print(f'  Visuel {bw * k / dpi * 25.4:.1f} x {bh * k / dpi * 25.4:.1f} mm | page {page_w_mm:.1f} x {page_h_mm:.1f} mm | {len(traces)} tracé(s) CutContour')
    print(f'  Fond perdu {o.fond_perdu:g} mm au-delà du trait | marge blanche {o.marge_blanche:g} mm')
    print(f'  Résolution réelle de la source ≈ {eff_dpi:.0f} dpi' + ('  ATTENTION : < 150 dpi, rendu flou probable' if eff_dpi < 150 else ' : OK'))


if __name__ == '__main__':
    main()
