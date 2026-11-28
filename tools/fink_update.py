"""Puts Fink's newest single-sheet PDFs on html/fink/ and moves the previous state into the archive.

Run from the repo root:  python tools/fink_update.py "<folder with TIB_Fink_NN_*.pdf>" <YYYY-MM-DD> <version, e.g. v6-5>
Sheets: TIB_Fink_<NN>_<Inhalt>[_M1-<n>]_A3_<ver>.pdf; NN=00 is the combined set (linked, not shown).
"""
import glob, html, io, os, re, shutil, sys
import fitz
from PIL import Image

SRC, DATE, VER = sys.argv[1:4]
OUT = "html/fink"
A, Z = "<!--aktuell-->", "<!--/aktuell-->"
AR, ARZ = "<!--archiv-->", "<!--/archiv-->"


def title_scale(stem):
    m = re.match(r"TIB_Fink_\d\d_(.+?)(?:_M1-(\d+))?_A\d_", stem)
    t = m.group(1)
    t = t.replace("Suedost", "von Südosten").replace("Sued", "Süd").replace("+", " + ").replace("-", " ")
    t = re.sub(r"Schnitt ([A-Z])\1\b", r"Schnitt \1-\1", t)
    return t, f"M 1:{m.group(2)}" if m.group(2) else ""


def webp(pix_png, long, path, lossless):
    im = Image.open(io.BytesIO(pix_png)).convert("RGB")
    s = long / max(im.size)
    if s < 1:
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    im.save(path, "WEBP", lossless=lossless, quality=84 if not lossless else 80, method=4)
    return im.size


figs, gesamt = [], None
for pdf in sorted(glob.glob(os.path.join(SRC, "TIB_Fink_*.pdf"))):
    name = os.path.basename(pdf)
    shutil.copy2(pdf, f"{OUT}/pdf/{name}")
    if re.match(r"TIB_Fink_00_", name):
        gesamt = name
        continue
    title, scale = title_scale(name[:-4])
    key = f"{VER}-{name[9:11]}-" + re.sub(r"[^a-z0-9]+", "-", title.lower().replace("ü", "ue")).strip("-")
    page = fitz.open(pdf)[0]
    png = page.get_pixmap(dpi=round(3000 / max(page.rect.width, page.rect.height) * 72)).tobytes("png")
    w, h = webp(png, 3000, f"{OUT}/img/{key}-l.webp", True)
    webp(png, 900, f"{OUT}/img/{key}-s.webp", False)
    e = lambda s: html.escape(s, quote=True)
    alt = title + (f", {scale}" if scale else "")
    figs.append(
        f'<figure class="" data-title="{e(title)}" data-scale="{scale}">'
        f'<button type="button" class="sheet" aria-label="{e(title)} groß öffnen">'
        f'<img src="img/{key}-s.webp" srcset="img/{key}-s.webp 900w, img/{key}-l.webp {max(w, h)}w" '
        f'sizes="(max-width:760px) 100vw, 460px" width="{w}" height="{h}" loading="lazy" decoding="async" '
        f'alt="{e(alt)}" data-large="img/{key}-l.webp"></button>'
        f'<figcaption><b>{e(title)}</b>' + (f'<span class="scale">{scale}</span>' if scale else "")
        + f'<a class="pdf" href="pdf/{name}">PDF</a></figcaption></figure>')
assert figs, f"no sheets in {SRC}"

label = f"Stand {DATE} · Pläne {VER}"
link = f' <a href="pdf/{gesamt}">Alle Blätter als PDF</a>' if gesamt else ""
new = (f'{A}<section id="aktuell" aria-labelledby="h-aktuell"><h2 id="h-aktuell">Aktuelle Pläne</h2>'
       f'<p class="kicker">{label}{link}</p><div class="grid g-plan">{"".join(figs)}</div></section>{Z}')

p = open(f"{OUT}/index.html", encoding="utf-8").read()
if A not in p:  # first run: the old drawing sections become the first archive entry
    m = re.search(r'<section id="grundrisse".*?(?=<section id="modellbilder")', p, re.S)
    old_label = re.search(r'<p class="kicker">(Stand [^<]*)</p>', p).group(1)
    p = p.replace(m.group(0), "")
    p = p.replace("</main>", f'{AR}<section id="archiv" aria-labelledby="h-archiv"><h2 id="h-archiv">Archiv</h2>'
                  f'<details><summary>{old_label}</summary>{m.group(0)}</details></section>{ARZ}\n</main>')
    p = p.replace('<section id="modellbilder"', f"{new}\n<section id=\"modellbilder\"", 1)
    p = re.sub(r'<div class="chips".*?</div>', "", p, count=1, flags=re.S)
    p = re.sub(r'<nav aria-label="Inhalt">.*?</nav>', '<nav aria-label="Inhalt"><a href="#aktuell">Aktuelle Pläne</a>'
               '<a href="#modellbilder">Modellbilder</a><a href="#archiv">Archiv</a></nav>', p, count=1, flags=re.S)
    p = p.replace("</style>", "details{margin-bottom:14px}summary{cursor:pointer;font-size:17px;padding:8px 0}"
                  "details section{padding:24px 0}details h2{font-size:24px}</style>", 1)
else:  # later runs: the current block moves to the top of the archive
    old = p[p.index(A):p.index(Z) + len(Z)]
    old_label = re.search(r'<p class="kicker">(Stand [^<]*?)(?: <a|</p>)', old).group(1)
    body = old[len(A):-len(Z)].replace('id="aktuell"', f'id="a-{DATE}"').replace('id="h-aktuell"', f'id="h-a-{DATE}"') \
        .replace('aria-labelledby="h-aktuell"', f'aria-labelledby="h-a-{DATE}"')
    p = p.replace(old, new)
    p = p.replace('<h2 id="h-archiv">Archiv</h2>', f'<h2 id="h-archiv">Archiv</h2><details><summary>{old_label}</summary>{body}</details>', 1)
p = re.sub(r'(<section class="hero".*?<p class="kicker">)Stand [^<]*(</p>\s*</section>)', rf"\g<1>{label}\g<2>", p, count=1, flags=re.S)
open(f"{OUT}/index.html", "w", encoding="utf-8", newline="\n").write(p)
print(f"{len(figs)} sheets, {label}")
