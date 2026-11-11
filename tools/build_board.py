"""Build board.json + thumbnails from the local 'Übersicht Main Datein' tree (already synced to Seafile).

- SECTIONS below decides what lies open on the board and what goes into stacks.
- Positions/sizes you changed on the board (edit mode, saved into board.json) are kept; everything else is re-flowed.
- PDFs and 3D files get one Seafile share link each: only /seafhttp/f/<token>/ allows the page to fetch them (CORS).
Run: uv run --no-project --python 3.12 --with mcp==1.27.2 --with pymupdf --with pillow python build_board.py
Add --layout to only re-sort board.json after changing GRID (no Seafile, no new files; new SECTIONS need a full run).
The board is also edited online (?edit saves board.json + uploads/ to GitHub): the run pulls first and keeps
those uploads, so commit + push board.json right after it.
"""
import fnmatch, hashlib, json, re, shutil, subprocess, sys, time
from pathlib import Path
from urllib.parse import quote

import fitz
from PIL import Image

sys.path.insert(0, "D:/Claude_Workspaces/CX-NEA/Seafile-MCP")
import server as sf  # noqa: E402

LOCAL = Path("D:/UNI/Bachelor/Übersicht Main Datein")
LIB, REMOTE = "Neuer Start", "/Bachelor Kempe/Übersicht Main Datein"
FOLDER_LINK = "https://seafile.cloud.uni-hannover.de/d/f0c8b2c7fd8b43f4bbd5/"
REPO = Path(__file__).resolve().parent.parent
THUMBS = REPO / "thumbs"

KIND = {".pdf": "pdf", ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
        ".stl": "model", ".glb": "model", ".html": "html"}  # .3mf: Bambu project files break three's 3MFLoader -> download card
# HTML previews are served from the repo itself (Seafile forbids framing): local path -> repo path
HTML = {"5_3D-Modelle/Modell-Ansichten_Web/index.html": "html/modell-ansichten/index.html",
        "2_Bestand_eigene-Pläne/Detail_Treppe-Kern335/Treppe_Kern335_Detailmappe_2.html": "html/kern335-detailmappe.html",
        "2_Bestand_eigene-Pläne/Raumprogramm/TIB_1102_D_Flaechen-Editor_10.html": "html/flaechen-editor.html"}

# Sections are named like the subfolders; the university's plans + archive stay folded into one box by the brief.
# Older versions live in each folder's "Ältere Versionen" subfolder (D:/UNI/_ordnung/plan_2026-10-31.csv), so no
# version guessing here: what lies in a folder is open, the subfolder is one stack.
# (title, [entries]); entry = ("open", globs) | ("latest", globs) | ("pick", globs) | ("stack", title, globs) | ("box", title, [entries])
# "pick": like "latest", but older versions stay free for a later entry.
# "latest": newest version open (name_v3 / name_2 beats name), older ones go into one "Ältere Versionen" stack.
U, E, F, D, M, P, O = ("1_Bestand_von-der-Uni", "2_Bestand_eigene-Pläne", "3_Bestand_Fotos", "4_Entwurf", "5_3D-Modelle",
                       "6_3D-Druck", "Ältere Versionen")
R = "7_Referenzen"  # chosen references as A3 sheets, big next to the reference page
PLATES = sorted(p.name for p in (LOCAL / P / "Entwurf_Platten").iterdir() if p.is_dir())
SECTIONS = [
    ("Aufgabenstellung", [
        ("open", ["0_Aufgabe/*.pdf"]),
        ("box", "Bestand · Pläne Uni", [
            ("open", [f"{U}/{t}/*.pdf" for t in ("Grundrisse", "Schnitte", "Ansichten", "Lageplan")]
             + [f"{U}/Archiv_1960-2013/1961_*Moeblierung*"]),  # + the original 1961 furniture plan
            ("stack", "Wettbewerb 1982/83", [f"{U}/Wettbewerb_1982-83/*"]),
            ("stack", "Archiv 1960–2013", [f"{U}/Archiv_1960-2013/*"]),
            ("stack", "Nachbargebäude · Marstall 1103", [f"{U}/Nachbargebäude_Marstall-1103/*"]),
            ("stack", "Nachbargebäude · Garage 1114", [f"{U}/Nachbargebäude_Garage-1114/*"]),
            ("stack", "Buchscans", [f"{U}/Buchscans/*"]),
            ("stack", "CAD + Raumliste", [f"{U}/*/*"]),
        ]),
    ]),
    ("Grundrisse", [
        ("open", [f"{E}/Grundrisse/*_M1-200.pdf"]),
        ("stack", "A3 · M 1:250", [f"{E}/Grundrisse/*_A3.pdf"]),
        ("stack", "CAD", [f"{E}/Grundrisse/*"]),
    ]),
    ("Schnitte", [
        ("open", [f"{E}/Schnitte/*_Schnitt*_Skizze*.pdf", f"{E}/Schnitte/TIB_*.pdf"]),  # same look as the Lageplan
        ("stack", "Weitere Stile", [f"{E}/Schnitte/*.pdf"]),
        ("stack", O, [f"{E}/Schnitte/{O}/*"]),
        ("stack", "CAD", [f"{E}/Schnitte/*"]),
    ]),
    ("Ansichten", [("open", [f"{E}/Ansichten/*"])]),
    ("Lageplan", [
        ("open", [f"{E}/Lageplan/*_Lageplan_Skizze*.pdf"]),  # the chosen style
        ("stack", "Weitere Stile", [f"{E}/Lageplan/*_Lageplan_*.pdf"]),
        ("stack", "Alle Pläne (Sammel-PDF)", [f"{E}/Lageplan/*alle_Plaene*"]),
        ("stack", O, [f"{E}/Lageplan/{O}/*"]),
        ("stack", "CAD", [f"{E}/Lageplan/*"]),
    ]),
    ("Details", [
        ("open", [f"{E}/Detail_*/*.pdf", f"{E}/Detail_Treppe-Kern335/*.html"]),
        ("stack", "Treppe Kern 335 · Fotos", [f"{E}/Detail_Treppe-Kern335/WhatsApp*"]),
        ("stack", "Grafiken + CAD", [f"{E}/Detail_*/*"]),
        ("stack", O, [f"{E}/Detail_*/{O}/*"]),
    ]),
    ("Möblierung + Nutzung", [
        ("open", [f"{E}/Möblierung+Nutzung/*.pdf"]),
        ("stack", "CAD", [f"{E}/Möblierung+Nutzung/*"]),
    ]),
    ("Möbelbestand", [
        ("latest", [f"{E}/Möbelbestand/*Inventar_A3*.pdf", f"{E}/Möbelbestand/*_Moebel_M1-250_A3_*.pdf"]),
        ("stack", "CAD + Einzelliste", [f"{E}/Möbelbestand/*"]),
        ("stack", O, [f"{E}/Möbelbestand/{O}/*"]),
    ]),
    ("Raumprogramm", [
        ("open", [f"{E}/Raumprogramm/*.pdf", f"{E}/Raumprogramm/*.html"]),
        ("stack", "Grafiken, Excel, CAD", [f"{E}/Raumprogramm/*"]),
        ("stack", O, [f"{E}/Raumprogramm/{O}/*"]),
    ]),
    ("Fotos", [("stack", t.replace("_2026-10-20", " 20.10."), [f"{F}/{t}/*"]) for t in
               ("Fassade", "Innen", "Innenhöfe", "Details", "Historisch", "Luftbilder", "Modellfotos_2026-10-20")]),
    # Vorübung 2, archived: one folded box at the bottom (the design is one design, no variants)
    ("Entwurf · Volumenstudien", [("box", "Volumenstudie · Vorübung 2", [
        ("open", [f"{D}/Vergleiche/*"]),
        ("stack", "Varianten Andis", [f"{D}/Varianten_Andis/*"]),
        ("stack", "Varianten Luca", [f"{D}/Varianten_Luca/*"]),
        ("stack", "Optionen 1–15", [f"{D}/Optionen_1-15/*"]),
        ("stack", "Lagepläne Varianten", [f"{D}/Lagepläne_Varianten/*"]),
        ("stack", "Flächenbedarf (Rhino)", [f"{D}/Flächenbedarf/*"]),
        ("stack", O, [f"{D}/Vergleiche/{O}/*", f"{D}/Lagepläne_Varianten/{O}/*"]),
    ])]),
    # the rows line up with the Bestand rows of the same name; the exploded Umbau axo lies with the Umbau plans
    *[(f"Entwurf · {t}", [("open", [f"{D}/{t}/*"] + [f"{D}/Axonometrie/*"] * (t == "Grundrisse")),
                          ("stack", O, [f"{D}/{t}/{O}/*", *[f"{D}/Axonometrie/{O}/*"] * (t == "Grundrisse")])])
      for t in ("Erweiterung", "Grundrisse", "Schnitte", "Ansichten", "Lageplan", "Details")],
    ("3D-Modelle", [
        ("open", [f"{M}/Modell-Ansichten_Web/index.html", f"{M}/Bestandsmodell/*.png"]),
        ("stack", "Modell Uni · Ansichten", [f"{M}/Bestandsmodell_Uni/*.png"]),
        ("stack", "Rhino, IFC + Bericht", [f"{M}/*/*"]),
        ("stack", O, [f"{M}/Bestandsmodell/{O}/*"]),
    ]),
    # existing building and design variants are separate prints, never one row
    ("3D-Druck · Bestand", [("open", [f"{P}/Bestand_M1-500/*"])]),
    # prints of the Volumenstudie variants 12.2, A3, A2.2 (27.10.), archived with it
    ("3D-Druck · Entwurf", [("box", "Varianten 12.2 · A3 · A2.2", [
        ("open", [f"{P}/Entwurf_M1-500/*"]),  # complete variants, assembly sheet, LIESMICH
        # one stack per print plate instead of one 70-part pile ("A1_Platte-2" -> "A1 · Platte 2")
        *[("stack", p.replace("_", " · ").replace("-", " "), [f"{P}/Entwurf_Platten/{p}/*"]) for p in PLATES],
        ("stack", O, [f"{P}/Entwurf_M1-500/{O}/*"]),
    ])]),
]

REFS = {"id": "html/referenzen/index.html", "kind": "html", "title": "Referenzen · Bibliotheken", "ext": "html",
        "size": 0, "dl": "html/referenzen/index.html", "raw": "html/referenzen/index.html",
        "url": "html/referenzen/index.html"}
GESCHOSSE = {"id": "html/geschossverbindungen/index.html", "kind": "html", "title": "Geschosse verbinden · 25 Referenzen", "ext": "html",
            "size": 0, "dl": "html/geschossverbindungen/index.html", "raw": "html/geschossverbindungen/index.html",
            "url": "html/geschossverbindungen/index.html", "thumb": "thumbs/geschossverbindungen.svg", "ar": 1.4142}
VORPLATZ = {"id": "html/vorplatz/index.html", "kind": "html", "title": "Vorplatz und Hof · 44 Referenzen", "ext": "html", "size": 0, "dl": "html/vorplatz/index.html", "raw": "html/vorplatz/index.html", "url": "html/vorplatz/index.html", "thumb": "thumbs/vorplatz.svg", "ar": 1.4142}
KT = {"id": "html/kempe-thill/index.html", "kind": "html", "title": "Kempe Thill · Büro + Haltung", "ext": "html",
      "size": 0, "dl": "html/kempe-thill/index.html", "raw": "html/kempe-thill/index.html",
      "url": "html/kempe-thill/index.html", "thumb": "thumbs/kempe-thill.webp", "ar": 1.4286}
# dates from the brief, a repo-only page shown live in its card ("live"): one big column left of everything (LEFT)
ZEITPLAN = {"id": "html/zeitplan.html", "kind": "html", "title": "Zeitplan · Termine", "ext": "html", "size": 0,
            "dl": "html/zeitplan.html", "raw": "html/zeitplan.html", "url": "html/zeitplan.html", "live": True, "ar": 0.3015}
LEFT = "Zeitplan"
KT_SEC = "Studio Kempe Thill"  # office background page: its own card left of the Zeitplan, opens only on click (no "live")

# rows of (Grundlagen | Entwurf); a row starts below the taller cell of the row above, so the Entwurf plans sit
# level with the Bestand plans of the same name
GRID = [
    ("Aufgabenstellung", None),
    ("Referenzen", "Entwurf · Erweiterung"),
    *[(t, f"Entwurf · {t}") for t in ("Grundrisse", "Schnitte", "Ansichten", "Lageplan", "Details")],
    ("Möblierung + Nutzung", None),
    ("Möbelbestand", None),
    ("Raumprogramm", None),
    ("Fotos", None),
    ("3D-Modelle", None),
    ("3D-Druck · Bestand", "Entwurf · Volumenstudien"),  # archive (Vorübung 2) at the bottom
    (None, "3D-Druck · Entwurf"),
]

# current plans lie open and big (4x a normal card): the design's plan PDFs + the newest furniture inventory sheet
BIG = [f"{D}/*/*.pdf", f"{E}/Möbelbestand/*Inventar_A3*.pdf", f"{R}/*.pdf"]
# reading order of the design plans (instead of newest first): floors bottom-up, per floor Grundriss, Nutzung, Rot-Gelb
READ = ("Uebersicht", "_Grundriss_", "_Nutzung_", "_RotGelb_", "_RotGelb-Nutzung_", "RotGelb", "Nutzung", "Axo", "Ausschnitt", "Vorplatz")
FLOORS = ("-2UG_", "-1UG_", "-EG_", "-EG-V2_", "-1OG_", "-2OG_", "-3OG_")
FLOOR_SEC = "Entwurf · Grundrisse"
FLOOR_NAME = {"-2UG_": "UG2", "-1UG_": "UG1", "-EG_": "EG", "-EG-V2_": "EG V2", "-1OG_": "OG1", "-2OG_": "OG2", "-3OG_": "OG3"}


def reading(rel):
    n = Path(rel).name
    return (next((i for i, t in enumerate(FLOORS) if t in n), 9), next((i for i, t in enumerate(READ) if t in n), len(READ)), n)


VER = re.compile(r"_(?:v)?(\d+)$")


def version(rel):
    stem = Path(rel).stem
    m = VER.search(stem)
    return (VER.sub("", stem), int(m.group(1)) if m else 1)


def match(rel, globs):
    # fnmatch '*' also crosses '/', so a plain '*' segment would swallow subfolders: compare segment counts
    for g in globs:
        if g.endswith("/**"):
            if rel.startswith(g[:-2]):
                return True
        elif fnmatch.fnmatch(rel, g) and rel.count("/") == g.count("/"):
            return True
    return False


STAMP = re.compile(r"(20\d{6})_(\d{6}|\d{2}\b)")  # PXL_20261021_081119857 / WA_20261102_07 (index keeps chat order)


# WhatsApp photos carry no capture time: each is placed right after the most similar dated photo (DINOv2 match)
ANCHORS = json.loads(Path(__file__).with_name("photo_anchors.json").read_text(encoding="utf-8"))


def shot(rel):
    """Capture time for sorting photo stacks: EXIF, else the date in the name, else file mtime."""
    if rel in ANCHORS:
        return shot(ANCHORS[rel]) + "~" + rel
    try:
        ex = Image.open(LOCAL / rel).getexif()
        t = ex.get_ifd(0x8769).get(36867) or ex.get(306)
        if t:
            return t.replace(":", "").replace(" ", "")[:14]
    except OSError:
        pass
    m = STAMP.search(Path(rel).stem)
    if m:
        return m.group(1) + m.group(2).ljust(6, "0")
    return time.strftime("%Y%m%d%H%M%S", time.localtime((LOCAL / rel).stat().st_mtime))


def age(rel):
    """Sort key: newest file first (mtime; stage.py copies with copy2, so it is the source file's date)."""
    return -(LOCAL / rel).stat().st_mtime, rel


def thumb(rel, kind):
    """Thumbnail in the repo; returns (path, width/height)."""
    src = LOCAL / rel
    out = THUMBS / (hashlib.sha1(rel.encode()).hexdigest()[:16] + ".webp")
    if not out.exists():
        if kind == "pdf":
            page = fitz.open(src)[0]
            z = 1100 / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        else:
            im = Image.open(src)
            im.thumbnail((720, 720))
            im = im.convert("RGB")
        im.save(out, "WEBP", quality=82)
    w, h = Image.open(out).size
    return out.relative_to(REPO).as_posix(), round(w / h, 4)


def main():
    files = sorted(p.relative_to(LOCAL).as_posix() for p in LOCAL.rglob("*") if p.is_file()
                   and "Modell-Ansichten_Web/" not in p.relative_to(LOCAL).as_posix()
                   or p.relative_to(LOCAL).as_posix() in HTML)
    THUMBS.mkdir(exist_ok=True)
    repo = sf._repo(LIB)
    cache = Path(__file__).with_name("links.json")  # path -> share token, so re-runs never create duplicates
    links = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    remote = {f"{f['parent_dir'].rstrip('/')}/{f['name']}"
              for f in sf.api("GET", f"/api2/repos/{repo}/dir/", params={"p": REMOTE, "t": "f", "recursive": 1})}

    def item(rel):
        ext = Path(rel).suffix.lower()
        kind = KIND.get(ext, "file")
        if kind == "html" and rel not in HTML:
            kind = "file"
        it = {"id": rel, "kind": kind, "title": Path(rel).stem.replace("_", " "), "ext": ext[1:],
              "size": (LOCAL / rel).stat().st_size,
              "date": time.strftime("%d.%m.%Y", time.localtime((LOCAL / rel).stat().st_mtime)),
              "dl": f"{FOLDER_LINK}files/?p={quote('/' + rel)}&dl=1",
              "raw": f"{FOLDER_LINK}files/?p={quote('/' + rel)}&raw=1"}
        if kind in ("pdf", "image"):
            it["thumb"], it["ar"] = thumb(rel, kind)
        if kind in ("pdf", "model"):
            path = f"{REMOTE}/{rel}"
            if path not in remote:
                print("not on Seafile yet, skipped link:", rel)
            else:
                if path not in links:
                    have = sf.api("GET", "/api/v2.1/share-links/", params={"repo_id": repo, "path": path})
                    links[path] = have[0]["token"] if have else \
                        sf.api("POST", "/api/v2.1/share-links/", json={"repo_id": repo, "path": path})["token"]
                    cache.write_text(json.dumps(links, ensure_ascii=False, indent=1), encoding="utf-8")
                it["url"] = f"{sf.SERVER}/seafhttp/f/{links[path]}/"
        if kind == "html":
            it["url"] = HTML[rel]
            it["title"] = {"html/modell-ansichten/index.html": "Modell-Ansichten (interaktiv)"}.get(HTML[rel], it["title"])
        return it

    used = set()

    def build(title, entries):
        cards, stacks = [], []
        for e in entries:
            if e[0] == "box":  # a whole group folded into one stack (stacks inside it open as sub-levels)
                inner = build(f"{title}:{e[1]}", e[2])
                if inner:
                    stacks.append({"id": f"stack:{title}:{e[1]}", "kind": "stack", "title": e[1], "items": inner,
                                   "ar": 2})  # wide enough for its heading
                continue
            if e[0] == "stack":
                rels = [r for r in files if r not in used and match(r, e[2])]
                if rels:
                    used.update(rels)
                    if all(KIND.get(Path(r).suffix.lower()) == "image" for r in rels):
                        rels.sort(key=shot)
                    else:
                        rels.sort(key=age)
                    stacks.append({"id": f"stack:{title}:{e[1]}", "kind": "stack", "title": e[1],
                                   "items": [item(r) for r in rels]})
                continue
            rels = [r for r in files if r not in used and match(r, e[1])]
            used.update(rels)
            if e[0] in ("latest", "pick"):
                best = {}
                for r in rels:
                    k, v = version(r)
                    if k not in best or (v, (LOCAL / r).stat().st_mtime) > best[k][0]:
                        best[k] = ((v, (LOCAL / r).stat().st_mtime), r)
                newest = {r for _, r in best.values()}
                older = [r for r in rels if r not in newest]
                rels = [r for r in rels if r in newest]
                if e[0] == "pick":
                    used.difference_update(older)  # left for a later entry (e.g. a box)
                elif older:  # one "Ältere Versionen" stack per section, however many "latest" entries
                    old = next((s for s in stacks if s["title"] == "Ältere Versionen"), None)
                    if not old:
                        old = {"id": f"stack:{title}:old:{len(stacks)}", "kind": "stack", "title": "Ältere Versionen", "items": []}
                        stacks.append(old)
                    old["items"] = sorted(old["items"] + [item(r) for r in older], key=lambda i: age(i["id"]))
            cards += [item(r) for r in rels]
        return sorted(cards, key=lambda i: (reading(i["id"]) if match(i["id"], [f"{D}/*/*.pdf", f"{R}/*.pdf"]) else (), age(i["id"]))) + stacks

    sections = [{"title": t, "items": build(t, es)} for t, es in SECTIONS]

    # reference page lives only in the repo (built by build_refs.py), not in the Seafile tree
    preview = next(THUMBS.glob("referenzen-*.webp"))  # name carries a content hash, written by build_refs.py
    w, h = Image.open(preview).size
    sections.append({"title": "Referenzen", "items": [REFS | {"thumb": preview.relative_to(REPO).as_posix(), "ar": round(w / h, 4)}]
                     + build("Referenzen", [("open", [f"{R}/*.pdf"]),
                                                          ("stack", "Raumpilot · Grundlagen, Wohnen, Lernen, Arbeiten", [f"{R}/Raumpilot/*.pdf"])]) + [dict(GESCHOSSE), dict(VORPLATZ)]})
    sections.append({"title": LEFT, "items": [dict(ZEITPLAN)]})
    sections.append({"title": KT_SEC, "items": [dict(KT)]})

    left = [r for r in files if r not in used]
    if left:
        sections.append({"title": "Neu / unsortiert", "items": [item(r) for r in left]})

    for rel, dst in HTML.items():
        src, out = LOCAL / rel, REPO / dst
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith("Modell-Ansichten_Web/index.html"):
            shutil.copytree(src.parent, out.parent, dirs_exist_ok=True)
        else:
            shutil.copy2(src, out)

    layout(sections)
    print(sum(len(s["items"]) for s in sections), "board items in", len(sections), "sections")


def layout(sections):
    """Keep what was moved in edit mode (and renamed labels); flow everything else in justified rows per section."""
    board = REPO / "board.json"
    subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only", "-q"], check=True)  # latest online moves + uploads
    old = json.loads(board.read_text(encoding="utf-8")) if board.exists() else {}
    pos = {i["id"]: i for i in old.get("items", []) + old.get("labels", []) if i.get("moved")}
    texts = {l["id"]: l["text"] for l in old.get("labels", [])}
    items, labels = [], []
    ROW_H, MAX_W, GAP = 300, 5200, 40

    def flow(s, x0, y):
        lid = "label:" + s["title"]
        labels.append(pos.get(lid) or {"id": lid, "text": texts.get(lid, s["title"]), "x": x0, "y": y})
        y += 250  # room for the 180px section title
        # photo stacks are the content there, so show them bigger; the references tile is a page preview
        h = {"Fotos": ROW_H * 2, "Referenzen": ROW_H * 4, LEFT: ROW_H * 26, KT_SEC: ROW_H * 4}.get(s["title"], ROW_H)
        x, row = 0, h  # row: height of the current row (a big card makes it taller)
        # design floor plans: one row per floor (2UG at the top), a big floor name left of each row
        fl = (lambda it: next((t for t in FLOORS if t in Path(it["id"]).name), None)) if s["title"] == FLOOR_SEC else (lambda it: None)
        last = None
        for it in sorted(s["items"], key=lambda it: fl(it) is None) if s["title"] == FLOOR_SEC else s["items"]:
            f = fl(it)
            if f != last and it["id"] not in pos:
                if x:
                    x, y, row = 0, y + row + 110, h
                if f:
                    fid = f"label:{s['title']}:{f}"
                    labels.append(pos.get(fid) or {"id": fid, "text": texts.get(fid, FLOOR_NAME[f]), "x": x0 - 1100, "y": y})
                last = f
            ih = ROW_H * 4 if it["kind"] != "stack" and match(it["id"], BIG) else h
            w = ih * it.get("ar", 1.0)  # square unless the item knows its shape
            it["section"] = s["title"]
            if it["id"] in pos:
                p = pos[it["id"]]
                it |= {"x": p["x"], "y": p["y"], "w": p["w"], "moved": True}
            else:
                if x and x + w > MAX_W:
                    x, y, row = 0, y + row + 110, h
                it |= {"x": x0 + x, "y": y, "w": round(w)}
                x += w + GAP
                row = max(row, ih)
            items.append(it)
        return y + row + 380

    by = {s["title"]: s for s in sections}
    cols = (0, MAX_W + 4000)  # the wide gap parts Grundlagen (left) from Entwurf (right)
    y = 0
    for row in GRID:
        y = max([flow(by[t], x, y) for x, t in zip(cols, row) if t in by] or [y])
    for s in sections:  # anything not in GRID (e.g. "Neu / unsortiert") goes below the left column
        if s["title"] not in (LEFT, KT_SEC) and not any(s["title"] in row for row in GRID):
            y = flow(s, 0, y)
    s = by.get(LEFT)
    if s:  # its single card ends 1000 before the first column, top level with the first row
        x0 = -round(ROW_H * 26 * s["items"][0]["ar"] + 1000)
        flow(s, x0, 0)
        k = by.get(KT_SEC)
        if k:  # the office page sits left of the Zeitplan
            flow(k, x0 - round(ROW_H * 4 * k["items"][0]["ar"]) - 1000, 0)
    # files dropped onto the board online (uploads/) and sheets hung on the Hängeplan wall (hp) stay where they lie
    ids = {i["id"] for i in items}
    items += [i for i in old.get("items", []) if (i.get("upload") or i.get("hp")) and i["id"] not in ids]
    board.write_text(json.dumps({"walls": old.get("walls", []), "labels": labels, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")


def relayout():
    """Re-sort the existing board.json into SECTIONS order; touches no files and no Seafile."""
    old = json.loads((REPO / "board.json").read_text(encoding="utf-8"))
    labs = sorted(old["labels"], key=lambda l: l["y"])
    groups = {l["text"]: [] for l in labs}
    names = {l["text"]: l["id"][len("label:"):] for l in labs}
    for it in sorted((i for i in old["items"] if not (i.get("upload") or i.get("hp"))), key=lambda i: (i["y"], i["x"])):  # layout() keeps uploads + wall sheets
        # boards written before the "section" field: plain vertical bands under each label
        sec = it.get("section") or names[[l for l in labs if l["y"] <= it["y"]][-1]["text"]]
        groups.setdefault(sec, []).append(it)
    groups = {names.get(k, k): v for k, v in groups.items()}
    order = [t for t, _ in SECTIONS] + ["Referenzen"]
    order += [t for t in groups if t not in order]
    layout([{"title": t, "items": groups[t]} for t in order if groups.get(t)])


if __name__ == "__main__":
    relayout() if "--layout" in sys.argv else main()
