"""Bibliothèque commune : spécifications produits, conversion CMJN, fond perdu,
écriture du PDF d'impression simple (image CMJN pleine page + CutContour vectoriel).
Dépendances : Pillow, numpy. Aucune police, aucun calque, aucune transparence dans la sortie."""
import io, math, os, re, shutil, subprocess, tempfile, zlib
import numpy as np
from PIL import Image


def rasteriser_pdf(pdf_path, dpi, sortie_png, gris=False):
    """Rend la 1re page d'un PDF en PNG à `dpi`. Essaie pdftoppm (Poppler), puis
    Ghostscript. Lève RasterIndisponible si aucun des deux n'est présent."""
    if shutil.which('pdftoppm'):
        base = sortie_png[:-4] if sortie_png.lower().endswith('.png') else sortie_png
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', '-f', '1', '-l', '1',
                        pdf_path, base], check=True)
        if base + '.png' != sortie_png: os.replace(base + '.png', sortie_png)
        return sortie_png
    if shutil.which('gs'):
        dev = 'pnggray' if gris else 'png16m'
        subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', f'-sDEVICE={dev}',
                        f'-r{dpi}', '-dFirstPage=1', '-dLastPage=1', '-dTextAlphaBits=4',
                        '-dGraphicsAlphaBits=4', f'-sOutputFile={sortie_png}', pdf_path], check=True)
        return sortie_png
    raise RasterIndisponible(
        "ni pdftoppm (poppler-utils) ni Ghostscript ne sont installés — "
        "installer l'un des deux : apt-get install -y poppler-utils (ou ghostscript), brew install poppler")


class RasterIndisponible(RuntimeError):
    pass

Image.MAX_IMAGE_PIXELS = None
MM = 72 / 25.4                 # points par mm
PAGE_MAX_PT = 14400            # limite PDF : 200 pouces = 508 cm

# Fond perdu client : 3 mm sur les 4 côtés pour tous les produits.
# decoupe : découpe par défaut ('rectangle' au format fini, ou None) ; dpi : recommandé ; dpi_min : minimum
FOND_PERDU = 3
PRODUITS = {
    'panneau':   dict(nom='PANNEAU',   bleed=3, decoupe='rectangle', dpi=150, dpi_min=150, securite=10),
    'vinyle':    dict(nom='VINYLE',    bleed=3, decoupe='rectangle', dpi=300, dpi_min=150, securite=5),
    # Bâche / mesh : 60 mm de zone de sécurité — l'atelier pose ourlets et
    # œillets dans cette bande, tout texte ou logo y serait perforé/replié.
    'bache':     dict(nom='BACHE',     bleed=3, decoupe=None,        dpi=100, dpi_min=72,  securite=60),
    'mesh':      dict(nom='MESH',      bleed=3, decoupe=None,        dpi=100, dpi_min=72,  securite=60),
    'textile':   dict(nom='TEXTILE',   bleed=3, decoupe=None,        dpi=150, dpi_min=100, securite=20),
    'blackback': dict(nom='BLACKBACK', bleed=3, decoupe=None,        dpi=150, dpi_min=100, securite=20),
    'papier':    dict(nom='PAPIER',    bleed=3, decoupe='rectangle', dpi=300, dpi_min=300, securite=5),
    'sticker':   dict(nom='STICKER',   bleed=1, decoupe='forme',     dpi=300, dpi_min=150, securite=2),
}
# Tons directs reconnus par l'atelier
TONS = {'CutContour': (0, 1, 0, 0),    # découpe : 100 % magenta
        'Pliage':     (0, 0, 1, 0)}    # pli / rainage : 100 % jaune
MAX_PIXELS = 160_000_000       # garde-fou mémoire (~640 Mo en CMJN)


def spec(produit, decoupe=None):
    """decoupe : None = valeur par défaut du produit, 'aucune', 'rectangle'."""
    s = dict(PRODUITS[produit])
    if decoupe == 'aucune': s['decoupe'] = None
    elif decoupe: s['decoupe'] = decoupe
    s['cut'] = 'fini' if s['decoupe'] in ('rectangle', 'forme') else None   # compatibilité
    return s


def nom_fichier(produit_nom, w_cm, h_cm, qte, nom, echelle=1):
    f = lambda v: f'{v:g}'
    nom = re.sub(r'[^A-Za-z0-9_-]+', '-', nom or 'visuel').strip('-') or 'visuel'
    suffixe = '_ECH1-10' if echelle == 10 else ''
    return f'COMINK_{produit_nom}_{f(w_cm)}x{f(h_cm)}cm_{qte}ex_{nom}{suffixe}.pdf'


# ---------- conversion RVB -> CMJN (remplacement du gris par du noir) ----------
def rgb_vers_cmjn(img):
    """Image PIL RGB/RGBA/L -> CMJN. Si déjà CMJN, renvoyée telle quelle.
    Conversion par blocs : noir K = min(C,M,J), couleurs recalculées (C-K)/(1-K) pour garder la teinte,
    encrage total limité à 300 %. Pour un rendu couleur exact, fournir un visuel déjà en CMJN."""
    if img.mode == 'CMYK':
        return img
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
        fond = Image.new('RGBA', img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(fond, img)
    img = img.convert('RGB')
    w, h = img.size
    out = np.empty((h, w, 4), np.uint8)
    src = np.asarray(img)
    pas = max(1, 4_000_000 // max(w, 1))
    for y in range(0, h, pas):
        b = src[y:y + pas].astype(np.float32) / 255.0
        c, m, j = 1 - b[..., 0], 1 - b[..., 1], 1 - b[..., 2]
        k = np.minimum(np.minimum(c, m), j)
        d = np.maximum(1 - k, 1e-6)
        c, m, j = (c - k) / d, (m - k) / d, (j - k) / d        # remplacement complet du gris par du noir
        tot = c + m + j + k
        f = np.where(tot > 3.0, 3.0 / np.maximum(tot, 1e-6), 1.0)
        c, m, j = c * f, m * f, j * f
        out[y:y + pas] = np.clip(np.stack([c, m, j, k], -1) * 255 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(out, 'CMYK')


# ---------- lecture de la source ----------
def boites_pdf(path):
    """(MediaBox, TrimBox, BleedBox) de la 1re page, en points."""
    from pypdf import PdfReader
    p = PdfReader(path).pages[0]
    mb = [float(v) for v in p.mediabox]
    tb = [float(v) for v in (p.trimbox if '/TrimBox' in p else p.mediabox)]
    bb = [float(v) for v in (p.bleedbox if '/BleedBox' in p else p.mediabox)]
    return mb, tb, bb


def charger_source(path, dpi):
    """Renvoie (image PIL, rect_format_fini_px, fond_perdu_dispo_px par côté [g, b, d, h], dpi_effectif)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        mb, tb, bb = boites_pdf(path)
        with tempfile.TemporaryDirectory() as d:
            rasteriser_pdf(path, dpi, os.path.join(d, 'r.png'))
            img = Image.open(os.path.join(d, 'r.png')); img.load()
        k = dpi / 72
        H = img.size[1]
        x0, x1 = (tb[0] - mb[0]) * k, (tb[2] - mb[0]) * k
        y0, y1 = H - (tb[3] - mb[1]) * k, H - (tb[1] - mb[1]) * k
        dispo = [max(0, tb[0] - max(bb[0], mb[0])) * k, max(0, tb[1] - max(bb[1], mb[1])) * k,
                 max(0, min(bb[2], mb[2]) - tb[2]) * k, max(0, min(bb[3], mb[3]) - tb[3]) * k]
        return img, (x0, y0, x1, y1), dispo, dpi
    if ext == '.svg':
        try:
            import cairosvg
        except ImportError:
            raise SystemExit('Source SVG : installez cairosvg (pip install cairosvg) ou exportez en PDF/PNG.')
        png = cairosvg.svg2png(url=path, dpi=dpi)
        img = Image.open(io.BytesIO(png)); img.load()
        return img, (0, 0, img.size[0], img.size[1]), [0, 0, 0, 0], dpi
    img = Image.open(path); img.load()
    return img, (0, 0, img.size[0], img.size[1]), [0, 0, 0, 0], None


def adapter(img, rect, dispo, W, H, bleed_px, mode='completer'):
    """Met le visuel (rect = format fini dans img) au format W x H px (format fini),
    puis ajoute bleed_px de fond perdu : vrai fond perdu de la source s'il suffit, sinon miroir.
    mode 'completer' : pas de recadrage, on complète en étirant le bord ; 'remplir' : on recadre."""
    x0, y0, x1, y1 = rect
    sw, sh = x1 - x0, y1 - y0
    s = (min if mode == 'completer' else max)(W / sw, H / sh)
    exact = abs(W / sw - H / sh) / max(W / sw, H / sh) < 0.005
    marge_src = [d * s for d in dispo]
    if exact and min(marge_src) >= bleed_px - 0.5 and bleed_px > 0:
        # vrai fond perdu disponible : on recadre format fini + fond perdu directement
        bx = bleed_px / s
        box = (x0 - bx, y0 - bx, x1 + bx, y1 + bx)
        out = img.crop(tuple(int(round(v)) for v in box)).resize((W + 2 * bleed_px, H + 2 * bleed_px), Image.LANCZOS)
        return out, s, 'fond perdu du fichier source'
    vis = img.crop(tuple(int(round(v)) for v in (x0, y0, x1, y1)))
    nw, nh = max(1, round(sw * s)), max(1, round(sh * s))
    vis = vis.resize((nw, nh), Image.LANCZOS)
    a = np.asarray(vis.convert('RGBA') if vis.mode in ('P', 'LA') else vis)
    if mode == 'completer':
        px, py = W - nw, H - nh
        pad = ((py // 2, py - py // 2), (px // 2, px - px // 2)) + ((0, 0),) * (a.ndim - 2)
        a = np.pad(a, pad, mode='edge')
    else:
        ox, oy = (nw - W) // 2, (nh - H) // 2
        a = a[oy:oy + H, ox:ox + W]
    note = 'format exact' if exact else ('complété (bords étirés)' if mode == 'completer' else 'recadré')
    if bleed_px:
        pad = ((bleed_px, bleed_px), (bleed_px, bleed_px)) + ((0, 0),) * (a.ndim - 2)
        a = np.pad(a, pad, mode='symmetric')
        note += ', fond perdu miroir'
    return Image.fromarray(np.ascontiguousarray(a)), s, note


# ---------- tracés ----------
def rect_arrondi(x, y, w, h, r):
    """Tracé PDF (points) d'un rectangle à coins arrondis (r=0 : rectangle)."""
    if r <= 0:
        return f'{x:.3f} {y:.3f} {w:.3f} {h:.3f} re'
    r = min(r, w / 2, h / 2); k = 0.5523 * r
    p = [f'{x + r:.3f} {y:.3f} m', f'{x + w - r:.3f} {y:.3f} l',
         f'{x + w - r + k:.3f} {y:.3f} {x + w:.3f} {y + r - k:.3f} {x + w:.3f} {y + r:.3f} c',
         f'{x + w:.3f} {y + h - r:.3f} l',
         f'{x + w:.3f} {y + h - r + k:.3f} {x + w - r + k:.3f} {y + h:.3f} {x + w - r:.3f} {y + h:.3f} c',
         f'{x + r:.3f} {y + h:.3f} l',
         f'{x + r - k:.3f} {y + h:.3f} {x:.3f} {y + h - r + k:.3f} {x:.3f} {y + h - r:.3f} c',
         f'{x:.3f} {y + r:.3f} l',
         f'{x:.3f} {y + r - k:.3f} {x + r - k:.3f} {y:.3f} {x + r:.3f} {y:.3f} c', 'h']
    return ' '.join(p)


# ---------- écriture du PDF ----------
def contenu_traits(cuts=None, plis=None, ech=1):
    """Opérateurs PDF des traits techniques (tracés en points, repère page 1:1) :
    CutContour (magenta) pour la découpe, Pliage (jaune) pour les plis. Trait 0,25 pt, surimpression."""
    c = ''
    for nom, traces in (('CutContour', cuts), ('Pliage', plis)):
        if traces:
            c += (f'q {1 / ech:.6f} 0 0 {1 / ech:.6f} 0 0 cm /GSop gs /CS{nom} CS 1 SCN {0.25 * ech:g} w 0 j 1 J\n'
                  + '\n'.join(t + ' S' for t in traces) + '\nQ\n')
    return c


def fonction_teinte(cmjn):
    c, m, j, k = cmjn
    return ('{' + ' '.join(f'dup {v:g} mul exch' for v in (c, m, j)) + f' {k:g} mul' + '}').encode() if any(cmjn) else b'{pop 0 0 0 0}'


def ecrire_pdf(out, img_cmjn, page_w_mm, page_h_mm, traces_cut=None, qualite=92, dpi=None, traces_pli=None):
    """PDF 1.4 minimal : 1 image CMJN (JPEG) pleine page + traits CutContour / Pliage vectoriels.
    Si la page dépasse 508 cm, tout est écrit à l'échelle 1:10."""
    W, H = page_w_mm * MM, page_h_mm * MM
    ech = 10 if max(W, H) > PAGE_MAX_PT else 1
    W, H = W / ech, H / ech
    buf = io.BytesIO()
    img_cmjn.save(buf, 'JPEG', quality=qualite, dpi=(dpi or 72, dpi or 72))
    jpeg = buf.getvalue()
    iw, ih = img_cmjn.size
    contenu = (f'q {W:.4f} 0 0 {H:.4f} 0 0 cm /Im0 Do Q\n' + contenu_traits(traces_cut, traces_pli, ech)).encode()
    contenu = zlib.compress(contenu)
    tons = [n for n, t in (('CutContour', traces_cut), ('Pliage', traces_pli)) if t]
    res_cs = ''.join(f'/CS{n} [/Separation /{n} /DeviceCMYK {6 + i} 0 R] ' for i, n in enumerate(tons))
    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W:.4f} {H:.4f}] /TrimBox [0 0 {W:.4f} {H:.4f}] '
         f'/BleedBox [0 0 {W:.4f} {H:.4f}] /Resources << /XObject << /Im0 5 0 R >> '
         + (f'/ColorSpace << {res_cs}>> /ExtGState << /GSop << /Type /ExtGState /OP true /op true /OPM 1 >> >> ' if tons else '')
         + '>> /Contents 4 0 R >>').encode(),
        b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(contenu) + contenu + b'\nendstream',
        (f'<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} /ColorSpace /DeviceCMYK '
         f'/BitsPerComponent 8 /Filter /DCTDecode /Decode [1 0 1 0 1 0 1 0] /Length {len(jpeg)} >>\nstream\n').encode()
        + jpeg + b'\nendstream',
    ]
    for n in tons:
        fn = fonction_teinte(TONS[n])
        objs.append(b'<< /FunctionType 4 /Domain [0 1] /Range [0 1 0 1 0 1 0 1] /Length %d >>\nstream\n' % len(fn) + fn + b'\nendstream')
    pdf = io.BytesIO(); pdf.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'); offs = []
    for i, o in enumerate(objs, 1):
        offs.append(pdf.tell()); pdf.write(b'%d 0 obj\n' % i + o + b'\nendobj\n')
    x = pdf.tell()
    pdf.write(b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1))
    for o in offs: pdf.write(b'%010d 00000 n \n' % o)
    pdf.write(b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, x))
    with open(out, 'wb') as f: f.write(pdf.getvalue())
    return ech


# ---------- voie vectorielle (Ghostscript) : polices vectorisées, CMJN ----------
def gs_dispo(installer=True):
    """Chemin de Ghostscript ; s'il manque, tente de l'installer (apt-get, brew, apk).
    Renvoie None si impossible : l'appelant passe alors en sortie image (sans police)."""
    import shutil
    if shutil.which('gs') or not installer:
        return shutil.which('gs')
    essais = []
    if shutil.which('apt-get'):
        pre = [] if os.geteuid() == 0 else (['sudo', '-n'] if shutil.which('sudo') else None)
        if pre is not None:
            essais += [pre + ['apt-get', 'update', '-qq'], pre + ['apt-get', 'install', '-y', '-qq', 'ghostscript']]
    if shutil.which('brew'): essais.append(['brew', 'install', 'ghostscript'])
    if shutil.which('apk'): essais.append(['apk', 'add', '--no-cache', 'ghostscript'])
    if essais: print('  Ghostscript absent : tentative d\'installation…', flush=True)
    for cmd in essais:
        try:
            subprocess.run(cmd, check=False, timeout=240, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'))
        except Exception:
            pass
        if shutil.which('gs'):
            print('  Ghostscript installé.'); return shutil.which('gs')
    return shutil.which('gs')


def mettre_au_format(src, out, page_w_mm, page_h_mm):
    """Recale la 1re page d'un PDF au format imprimé exact (mise à l'échelle uniforme, centrée)."""
    import pikepdf
    pdf = pikepdf.open(src); pg = pdf.pages[0]
    mb = [float(v) for v in pg.mediabox]
    sw, sh = mb[2] - mb[0], mb[3] - mb[1]
    W, H = page_w_mm * MM, page_h_mm * MM
    s = min(W / sw, H / sh); dx = (W - sw * s) / 2 - mb[0] * s; dy = (H - sh * s) / 2 - mb[1] * s
    pg.contents_coalesce()
    pg.Contents = pdf.make_stream(f'q {s:.6f} 0 0 {s:.6f} {dx:.4f} {dy:.4f} cm\n'.encode() + pg.Contents.read_bytes() + b'\nQ\n')
    for k in ('/CropBox', '/ArtBox', '/BleedBox', '/TrimBox', '/Rotate'):
        if k in pg.obj: del pg.obj[k]
    pg.MediaBox = pikepdf.Array([0, 0, W, H])
    del pdf.pages[1:]
    pdf.save(out)


def vectoriser_cmjn(src, out):
    """Ghostscript : textes convertis en tracés (aucune police), couleurs converties en CMJN,
    images conservées, PDF 1.4. Les dégradés et transparences restent vectoriels."""
    subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite', '-dNoOutputFonts',
                    '-sColorConversionStrategy=CMYK', '-sProcessColorModel=DeviceCMYK', '-dCompatibilityLevel=1.4',
                    '-dAutoRotatePages=/None', '-dDownsampleColorImages=false', '-dDownsampleGrayImages=false',
                    '-dPassThroughJPEGImages=false', f'-sOutputFile={out}', src], check=True)


def ajouter_traits_pdf(path, page_w_mm, page_h_mm, cuts=None, plis=None):
    """Ajoute CutContour / Pliage en vectoriel par-dessus la page et fixe les boîtes."""
    import pikepdf
    from pikepdf import Name, Dictionary, Array
    pdf = pikepdf.open(path, allow_overwriting_input=True); pg = pdf.pages[0]
    W, H = page_w_mm * MM, page_h_mm * MM
    if '/Resources' not in pg.obj: pg.obj.Resources = Dictionary()
    res = pg.obj.Resources
    for k in ('/ColorSpace', '/ExtGState'):
        if k not in res: res[k] = Dictionary()
    for n in ('CutContour', 'Pliage'):
        f = pdf.make_stream(fonction_teinte(TONS[n])); f.FunctionType = 4; f.Domain = Array([0, 1]); f.Range = Array([0, 1] * 4)
        res.ColorSpace[Name('/CS' + n)] = Array([Name.Separation, Name('/' + n), Name.DeviceCMYK, f])
    res.ExtGState[Name('/GSop')] = Dictionary(Type=Name.ExtGState, OP=True, op=True, OPM=1)
    pg.contents_coalesce()
    pg.Contents = pdf.make_stream(b'q\n' + pg.Contents.read_bytes() + b'\nQ\n' + contenu_traits(cuts, plis).encode())
    for k in ('/CropBox', '/ArtBox', '/Rotate'):
        if k in pg.obj: del pg.obj[k]
    box = Array([0, 0, W, H]); pg.MediaBox = box; pg.BleedBox = box; pg.TrimBox = box
    pdf.save(path)


# ---------- contrôle du fond perdu réellement imprimé ----------
def traits_cut(pdf_path):
    """Boîtes englobantes (points, repère page) des tracés CutContour de la page."""
    from pypdf import PdfReader
    pg = PdfReader(pdf_path).pages[0]
    data = pg.get_contents().get_data().decode('latin1')
    cles = []
    for k, v in (pg['/Resources'].get_object().get('/ColorSpace') or {}).items():
        v = v.get_object()
        if isinstance(v, list) and len(v) > 1 and v[0] == '/Separation' and str(v[1]) == '/CutContour':
            cles.append(str(k))
    boites = []
    for cle in cles:
        for m in re.finditer(re.escape(cle) + r'\s+CS', data):
            qs = list(re.finditer(r'(?<![\w/])q(?![\w])', data[:m.start()]))
            debut = qs[-1].start() if qs else 0
            mm_ = re.search(r'([-\d.]+)\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+cm', data[debut:m.start()])
            k = float(mm_.group(1)) if mm_ else 1.0
            fin = re.search(r'(?<![\w/])Q(?![\w])', data[m.end():])
            bloc = data[m.end(): m.end() + (fin.start() if fin else len(data))]
            pile, pts = [], []
            for t in re.findall(r'(?<![\w/])(?:[-\d.]+|[A-Za-z*]+)(?![\w])', bloc):
                if re.fullmatch(r'[-\d.]+', t): pile.append(float(t)); continue
                if t == 're' and len(pile) >= 4:
                    x, y, w, h = pile[-4:]; pts += [(x, y), (x + w, y + h)]
                elif t in ('m', 'l') and len(pile) >= 2: pts.append(tuple(pile[-2:]))
                elif t == 'c' and len(pile) >= 6: pts += [tuple(pile[-6:-4]), tuple(pile[-4:-2]), tuple(pile[-2:])]
                elif t in ('S', 's'):
                    if pts:
                        xs, ys = [p[0] * k for p in pts], [p[1] * k for p in pts]
                        boites.append((min(xs), min(ys), max(xs), max(ys)))
                    pts = []
                pile = []
    return boites, pg


def controle_fond_perdu(pdf_path, bleed_mm=3.0, coupe='fini'):
    """Vérifie, côté par côté, que la couleur dépasse réellement le trait de coupe (coupe='fini')
    ou qu'il n'y a pas de blanc juste à l'intérieur du trait (coupe='bord', fraisage).
    Renvoie (nb_traits, liste de problèmes 'trait n : côté')."""
    boites, pg = traits_cut(pdf_path)
    if not boites: return 0, []
    W, H = float(pg.mediabox.width), float(pg.mediabox.height)
    dpi = max(40, min(100, int((150e6 / ((W / 72) * (H / 72))) ** 0.5)))
    try:
        with tempfile.TemporaryDirectory() as d:
            rasteriser_pdf(pdf_path, dpi, os.path.join(d, 'r.png'), gris=True)
            im = np.asarray(Image.open(os.path.join(d, 'r.png')).convert('L')).astype(np.int16)
    except RasterIndisponible:
        # Environnement sans Poppler ni Ghostscript : on ne bloque pas, le
        # contrôle visuel du fond perdu est simplement sauté.
        print('  (contrôle visuel du fond perdu sauté : ni pdftoppm ni Ghostscript installés)')
        return 0, []
    px = dpi / 25.4; s = dpi / 72
    if coupe == 'bord':
        a_ext, b_ext, a_int, b_int = -1.5, -0.3, -4.0, -2.8      # à l'intérieur : bande collée au trait vs plus loin
    else:
        a_ext, b_ext, a_int, b_int = 0.5, min(1.5, bleed_mm - 0.3), -1.5, -0.5
    probs = []
    for n, (x0, y0, x1, y1) in enumerate(boites, 1):
        X0, X1 = x0 * s, x1 * s; Y0, Y1 = (H - y1) * s, (H - y0) * s      # pixels, origine en haut
        mx, my = (X1 - X0) * 0.2, (Y1 - Y0) * 0.2
        def band(xa, xb, ya, yb):
            xa, xb = sorted((int(round(xa)), int(round(xb)))); ya, yb = sorted((int(round(ya)), int(round(yb))))
            return im[max(0, ya):max(0, yb) + 1, max(0, xa):max(0, xb) + 1]
        cotes = {
            'gauche': (band(X0 - b_ext * px, X0 - a_ext * px, Y0 + my, Y1 - my), band(X0 - b_int * px, X0 - a_int * px, Y0 + my, Y1 - my)),
            'droite': (band(X1 + a_ext * px, X1 + b_ext * px, Y0 + my, Y1 - my), band(X1 + a_int * px, X1 + b_int * px, Y0 + my, Y1 - my)),
            'haut':   (band(X0 + mx, X1 - mx, Y0 - b_ext * px, Y0 - a_ext * px), band(X0 + mx, X1 - mx, Y0 - b_int * px, Y0 - a_int * px)),
            'bas':    (band(X0 + mx, X1 - mx, Y1 + a_ext * px, Y1 + b_ext * px), band(X0 + mx, X1 - mx, Y1 + a_int * px, Y1 + b_int * px)),
        }
        for cote, (ext, inte) in cotes.items():
            if ext.size == 0 or inte.size == 0:
                continue
            n_ = min(ext.size, inte.size)
            e, i = ext.reshape(-1)[:n_], inte.reshape(-1)[:n_]
            if (i < 200).mean() > 0.3 and ((i < 200) & (e > 245)).mean() > 0.2:
                probs.append(f'trait {n} : {cote}')
    return len(boites), probs


# ---------- bords blancs parasites (export Claude Design, marge de page, cadre) ----------
def bords_blancs(img, seuil=248, min_frac=0.003):
    """Détecte les bandes blanches uniformes collées aux bords d'un visuel dont le fond est coloré.
    Renvoie (gauche, haut, droite, bas) en pixels (0 si pas de bande parasite).
    Une bande n'est retenue que si la première ligne/colonne non blanche est majoritairement colorée
    (= bord d'un fond coloré), pour ne pas rogner un visuel volontairement sur fond blanc."""
    g = np.asarray(img.convert('L')).astype(np.int16)
    h, w = g.shape
    blanc = g >= seuil
    def mesure(lignes):                     # lignes : itérable de vecteurs du bord vers l'intérieur
        n = 0
        for v in lignes:
            if v.mean() > 0.995: n += 1; continue
            return n if (1 - v.mean()) > 0.6 else 0
        return 0
    res = [mesure(blanc[:, x] for x in range(w)), mesure(blanc[y, :] for y in range(h)),
           mesure(blanc[:, x] for x in range(w - 1, -1, -1)), mesure(blanc[y, :] for y in range(h - 1, -1, -1))]
    lim = [w, h, w, h]
    return [r if r >= max(2, min_frac * lim[i]) and r < 0.25 * lim[i] else 0 for i, r in enumerate(res)]
