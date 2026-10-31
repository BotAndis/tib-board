"""Build board.json + thumbnails from the local 'Übersicht Main Datein' tree (already synced to Seafile).

- SECTIONS below decides what lies open on the board and what goes into stacks.
- Positions/sizes you changed on the board (edit mode, saved into board.json) are kept; everything else is re-flowed.
- PDFs and 3D files get one Seafile share link each: only /seafhttp/f/<token>/ allows the page to fetch them (CORS).
Run: uv run --no-project --python 3.12 --with mcp==1.27.2 --with pymupdf --with pillow python build_board.py
Add --layout to only re-sort board.json after changing SECTIONS / SIDE (no Seafile, no new files).
"""
import fnmatch, hashlib, json, re, shutil, sys
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
        ".stl": "model", ".glb": "model", ".3mf": "model", ".html": "html"}
# HTML previews are served from the repo itself (Seafile forbids framing): local path -> repo path
HTML = {"05_3D-Modelle/Modell-Ansichten_HTML/index.html": "html/modell-ansichten/index.html",
        "02_Plaene/Details/Kern335/Treppe_Kern335_Detailmappe_2.html": "html/kern335-detailmappe.html",
        "03_Analyse/Raumprogramm/TIB_1102_D_Flaechen-Editor_10.html": "html/flaechen-editor.html"}

# (title, [entries]); entry = ("open", globs) | ("latest", globs) | ("stack", title, globs)
# "latest": newest version open (name_v3 / name_2 beats name), older ones go into one "Ältere Versionen" stack.
SECTIONS = [
    ("Aufgabenstellung", [("open", ["00_Aufgabe/*.pdf"])]),
    ("Grundrisse", [
        ("open", ["02_Plaene/Grundrisse/*_M1-200.pdf"]),
        ("stack", "Grundrisse A3 · M 1:250", ["02_Plaene/Grundrisse/*_A3.pdf"]),
        ("stack", "CAD (DXF)", ["02_Plaene/Grundrisse/*.dxf"]),
    ]),
    ("Schnitte", [
        ("open", ["02_Plaene/Schnitte/TIB_*.pdf", "02_Plaene/Schnitte/hannover-*.pdf"]),
        ("stack", "Städtebaulicher Schnitt · Stile", ["02_Plaene/Schnitte/LP_*.pdf"]),
        ("stack", "CAD (DXF)", ["02_Plaene/Schnitte/*"]),
    ]),
    # the reworked elevation sheet; listed before Bestand so Bestand does not claim it
    ("Ansichten", [("open", ["01_Bestand_Uni/Ansichten/*berarbeitet*.pdf", "02_Plaene/Ansichten/*.pdf"])]),
    ("Lageplan", [
        ("latest", ["02_Plaene/Lageplan/*_Lageplan_*.pdf"]),
        ("stack", "Alle Pläne (Sammel-PDF)", ["02_Plaene/Lageplan/*alle_Plaene*"]),
        ("stack", "CAD (DXF)", ["02_Plaene/Lageplan/*"]),
    ]),
    ("Details", [
        ("latest", ["02_Plaene/Details/*.pdf", "02_Plaene/Details/Kern335/*.pdf"]),
        ("latest", ["02_Plaene/Details/Kern335/*.html"]),
        ("stack", "Kern 335 · Fotos", ["02_Plaene/Details/Kern335/Fotos/*", "02_Plaene/Details/Kern335/WhatsApp*"]),
        ("stack", "Kern 335 · Grafiken + CAD", ["02_Plaene/Details/**"]),
    ]),
    ("3D-Modelle", [
        ("open", ["05_3D-Modelle/Modell-Ansichten_HTML/index.html", "05_3D-Modelle/Web-Vorschau/*.glb"]),
        ("latest", ["05_3D-Modelle/Bestandsmodell/*.png"]),
        ("stack", "Modell Uni · Ansichten", ["05_3D-Modelle/Bestandsmodell_Uni/*.png"]),
        ("stack", "Rhino-Dateien + Bericht", ["05_3D-Modelle/*/*.3dm", "05_3D-Modelle/*/*.ifc", "05_3D-Modelle/*/*.md"]),
    ]),
    ("3D-Druck", [
        ("open", ["06_3D-Druck/Bestand_M1-500/*.stl", "06_3D-Druck/Varianten_M1-500/*.stl", "06_3D-Druck/Varianten_M1-500/*.png"]),
        ("stack", "Druckteile geteilt", ["06_3D-Druck/Varianten_M1-500/geteilt_ohne-Stuetzen/**"]),
        ("stack", "Bambu 3MF + Liesmich", ["06_3D-Druck/**"]),
    ]),
    ("Analyse · Möblierung + Nutzung", [
        ("open", ["03_Analyse/Moeblierung_Nutzung/*.pdf"]),
        ("stack", "CAD (DXF)", ["03_Analyse/Moeblierung_Nutzung/*.dxf"]),
    ]),
    ("Analyse · Raumprogramm", [
        ("latest", ["03_Analyse/Raumprogramm/*.pdf"]),
        ("open", ["03_Analyse/Raumprogramm/*.html"]),
        ("stack", "Grafiken, Excel, DXF", ["03_Analyse/Raumprogramm/*"]),
    ]),
    # side columns (see SIDE): volume studies so far, and the university's own plans
    ("Entwurf · Volumenstudien", [
        ("latest", ["04_Entwurf/Renderings/TIB_Vergleich_*"]),
        ("stack", "Varianten Andis", ["04_Entwurf/Renderings/Andis*"]),
        ("stack", "Varianten Luca", ["04_Entwurf/Renderings/Luca*"]),
        ("stack", "Optionen 1–15", ["04_Entwurf/Renderings/Option*"]),
        ("stack", "Lagepläne Varianten", ["04_Entwurf/Lageplaene_Varianten/*"]),
        ("stack", "Flächenbedarf (Rhino)", ["04_Entwurf/Flaechenbedarf/*"]),
    ]),
    ("Bestand · Pläne Uni", [
        ("open", ["01_Bestand_Uni/Grundrisse/*.pdf", "01_Bestand_Uni/Schnitte/*.pdf", "01_Bestand_Uni/Ansichten/*.pdf"]),
        ("latest", ["01_Bestand_Uni/Lageplan/*.pdf"]),
        ("open", ["01_Bestand_Uni/Historisch/*.pdf"]),  # 1961 original furniture plan
        ("stack", "Wettbewerb 1982/83", ["01_Bestand_Uni/Historisch/Archiv_1960-2013/1982-83_Wettbewerb/*"]),
        ("stack", "Historische Pläne 1960–2013", ["01_Bestand_Uni/Historisch/Archiv_1960-2013/*"]),
        ("stack", "Nachbargebäude", ["01_Bestand_Uni/Nachbargebaeude/**"]),
        ("stack", "Buchscans", ["01_Bestand_Uni/Buchscans/*"]),
        ("stack", "CAD + Raumliste", ["01_Bestand_Uni/*/*"]),
    ]),
    ("Fotos", [
        ("stack", "Fassade", ["07_Fotos/Fassade/*"]),
        ("stack", "Innen", ["07_Fotos/Innen/*"]),
        ("stack", "Innenhöfe", ["07_Fotos/Innenhoefe/*"]),
        ("stack", "Details + Material", ["07_Fotos/Details/*"]),
        ("stack", "Historisch", ["07_Fotos/Historisch/*"]),
        ("stack", "Luftbilder", ["07_Fotos/Luftbilder/*"]),
        ("stack", "Modellfotos 20.10.", ["07_Fotos/Modellfotos_2026-10-20/*"]),
    ]),
]

REFS = {"id": "html/referenzen/index.html", "kind": "html", "title": "Referenzen · Bibliotheken", "ext": "html",
        "size": 0, "dl": "html/referenzen/index.html", "raw": "html/referenzen/index.html",
        "url": "html/referenzen/index.html"}

# side columns right of the main one, in this order, each starting level with the named main section
SIDE = {"Entwurf · Volumenstudien": "Aufgabenstellung", "Bestand · Pläne Uni": "Grundrisse"}

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
                   and "Modell-Ansichten_HTML/" not in p.relative_to(LOCAL).as_posix()
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

    used, sections = set(), []
    for title, entries in SECTIONS:
        cards, stacks = [], []
        for e in entries:
            if e[0] == "stack":
                rels = [r for r in files if r not in used and match(r, e[2])]
                if rels:
                    used.update(rels)
                    stacks.append({"id": f"stack:{title}:{e[1]}", "kind": "stack", "title": e[1],
                                   "items": [item(r) for r in rels]})
                continue
            rels = [r for r in files if r not in used and match(r, e[1])]
            used.update(rels)
            if e[0] == "latest":
                best = {}
                for r in rels:
                    k, v = version(r)
                    if k not in best or (v, (LOCAL / r).stat().st_mtime) > best[k][0]:
                        best[k] = ((v, (LOCAL / r).stat().st_mtime), r)
                newest = {r for _, r in best.values()}
                older = [r for r in rels if r not in newest]
                rels = [r for r in rels if r in newest]
                if older:
                    stacks.append({"id": f"stack:{title}:old:{len(stacks)}", "kind": "stack",
                                   "title": "Ältere Versionen", "items": [item(r) for r in older]})
            cards += [item(r) for r in rels]
        sections.append({"title": title, "items": cards + stacks})

    # reference page lives only in the repo (built by build_refs.py), not in the Seafile tree
    thumb = next(THUMBS.glob("referenzen-*.webp"))  # name carries a content hash, written by build_refs.py
    w, h = Image.open(thumb).size
    sections.append({"title": "Referenzen", "items": [REFS | {"thumb": thumb.relative_to(REPO).as_posix(), "ar": round(w / h, 4)}]})

    left = [r for r in files if r not in used]
    if left:
        sections.append({"title": "Neu / unsortiert", "items": [item(r) for r in left]})

    for rel, dst in HTML.items():
        src, out = LOCAL / rel, REPO / dst
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith("Modell-Ansichten_HTML/index.html"):
            shutil.copytree(src.parent, out.parent, dirs_exist_ok=True)
        else:
            shutil.copy2(src, out)

    layout(sections)
    print(sum(len(s["items"]) for s in sections), "board items in", len(sections), "sections")


def layout(sections):
    """Keep what was moved in edit mode (and renamed labels); flow everything else in justified rows per section."""
    board = REPO / "board.json"
    old = json.loads(board.read_text(encoding="utf-8")) if board.exists() else {}
    pos = {i["id"]: i for i in old.get("items", []) + old.get("labels", []) if i.get("moved")}
    texts = {l["id"]: l["text"] for l in old.get("labels", [])}
    items, labels, tops = [], [], {}
    ROW_H, MAX_W, GAP = 300, 5200, 40

    def flow(s, x0, y):
        lid = "label:" + s["title"]
        labels.append(pos.get(lid) or {"id": lid, "text": texts.get(lid, s["title"]), "x": x0, "y": y})
        tops[s["title"]] = y
        y += 250  # room for the 180px section title
        # photo stacks are the content there, so show them bigger; the references tile is a page preview
        h = {"Fotos": ROW_H * 2, "Referenzen": ROW_H * 4}.get(s["title"], ROW_H)
        x = 0
        for it in s["items"]:
            w = h * it.get("ar", 1.0) if it["kind"] in ("pdf", "image") or it["id"] == REFS["id"] else h
            it["section"] = s["title"]
            if it["id"] in pos:
                p = pos[it["id"]]
                it |= {"x": p["x"], "y": p["y"], "w": p["w"], "moved": True}
            else:
                if x and x + w > MAX_W:
                    x, y = 0, y + h + 110
                it |= {"x": x0 + x, "y": y, "w": round(w)}
                x += w + GAP
            items.append(it)
        return y + h + 380

    y = 0
    for s in sections:
        if s["title"] not in SIDE:
            y = flow(s, 0, y)
    for title in SIDE:
        s = next((s for s in sections if s["title"] == title), None)
        if s:  # next column starts 1000 right of everything so far (labels ~100 px per character at 180 px)
            right = max([i["x"] + i["w"] for i in items] + [l["x"] + 100 * len(l["text"]) for l in labels])
            flow(s, right + 1000, tops.get(SIDE[title], 0))
    board.write_text(json.dumps({"labels": labels, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")


def relayout():
    """Re-sort the existing board.json into SECTIONS order; touches no files and no Seafile."""
    old = json.loads((REPO / "board.json").read_text(encoding="utf-8"))
    labs = sorted(old["labels"], key=lambda l: l["y"])
    groups = {l["text"]: [] for l in labs}
    names = {l["text"]: l["id"][len("label:"):] for l in labs}
    for it in sorted(old["items"], key=lambda i: (i["y"], i["x"])):
        # boards written before the "section" field: plain vertical bands under each label
        sec = it.get("section") or names[[l for l in labs if l["y"] <= it["y"]][-1]["text"]]
        groups.setdefault(sec, []).append(it)
    groups = {names.get(k, k): v for k, v in groups.items()}
    order = [t for t, _ in SECTIONS] + ["Referenzen"]
    order += [t for t in groups if t not in order]
    layout([{"title": t, "items": groups[t]} for t in order if groups.get(t)])


if __name__ == "__main__":
    relayout() if "--layout" in sys.argv else main()
