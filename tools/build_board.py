"""Build board.json + thumbnails from the local 'Übersicht Main Datein' tree (already synced to Seafile).

- SECTIONS below decides what lies open on the board and what goes into stacks.
- Positions/sizes you changed on the board (edit mode, saved into board.json) are kept; everything else is re-flowed.
- PDFs and 3D files get one Seafile share link each: only /seafhttp/f/<token>/ allows the page to fetch them (CORS).
Run: uv run --no-project --python 3.12 --with mcp==1.27.2 --with pymupdf --with pillow python build_board.py
Add --layout to only re-sort board.json after changing GRID (no Seafile, no new files; new SECTIONS need a full run).
The board is also edited online (?edit saves board.json + uploads/ to GitHub): the run pulls first and keeps
those uploads, so commit + push board.json right after it.
"""
import fnmatch, hashlib, json, re, shutil, subprocess, sys
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

# The board follows the folder 1:1: chapter folder "N_…" -> sections "N … · <subfolder>", same order, same names.
# Older versions live in each folder's "Ältere Versionen" subfolder (D:/UNI/_ordnung/plan_2026-10-31.csv), so no
# version guessing here: what lies in a folder is open, the subfolder is one stack.
# (title, [entries]); entry = ("open", globs) | ("latest", globs) | ("pick", globs) | ("stack", title, globs) | ("box", title, [entries])
# "pick": like "latest", but older versions stay free for a later entry.
# "latest": newest version open (name_v3 / name_2 beats name), older ones go into one "Ältere Versionen" stack.
U, E, F, D, M, P, O = ("1_Bestand_von-der-Uni", "2_Bestand_eigene-Pläne", "3_Bestand_Fotos", "4_Entwurf", "5_3D-Modelle",
                       "6_3D-Druck", "Ältere Versionen")
PLATES = sorted(p.name for p in (LOCAL / P / "Entwurf_Platten").iterdir() if p.is_dir())
SECTIONS = [
    ("0 Aufgabe", [("open", ["0_Aufgabe/*.pdf"])]),
    *[(f"1 Uni · {t}", [("open", [f"{U}/{t}/*.pdf"]), ("stack", "CAD", [f"{U}/{t}/*"])])
      for t in ("Grundrisse", "Schnitte", "Ansichten", "Lageplan")],
    ("1 Uni · Archiv + Nachbarn", [
        ("open", [f"{U}/Archiv_1960-2013/1961_*Moeblierung*"]),  # the original 1961 furniture plan
        ("stack", "Archiv 1960–2013", [f"{U}/Archiv_1960-2013/*"]),
        ("stack", "Wettbewerb 1982/83", [f"{U}/Wettbewerb_1982-83/*"]),
        ("stack", "Nachbargebäude · Marstall 1103", [f"{U}/Nachbargebäude_Marstall-1103/*"]),
        ("stack", "Nachbargebäude · Garage 1114", [f"{U}/Nachbargebäude_Garage-1114/*"]),
        ("stack", "Raumliste", [f"{U}/Raumliste/*"]),
        ("stack", "Buchscans", [f"{U}/Buchscans/*"]),
    ]),
    ("2 Eigene Pläne · Grundrisse", [
        ("open", [f"{E}/Grundrisse/*_M1-200.pdf"]),
        ("stack", "A3 · M 1:250", [f"{E}/Grundrisse/*_A3.pdf"]),
        ("stack", "CAD", [f"{E}/Grundrisse/*"]),
    ]),
    ("2 Eigene Pläne · Schnitte", [
        ("open", [f"{E}/Schnitte/*_Schnitt_Skizze*.pdf", f"{E}/Schnitte/TIB_*.pdf"]),  # same look as the Lageplan
        ("stack", "Weitere Stile", [f"{E}/Schnitte/*.pdf"]),
        ("stack", O, [f"{E}/Schnitte/{O}/*"]),
        ("stack", "CAD", [f"{E}/Schnitte/*"]),
    ]),
    ("2 Eigene Pläne · Ansichten", [("open", [f"{E}/Ansichten/*"])]),
    ("2 Eigene Pläne · Lageplan", [
        ("open", [f"{E}/Lageplan/*_Lageplan_Skizze*.pdf"]),  # the chosen style
        ("stack", "Weitere Stile", [f"{E}/Lageplan/*_Lageplan_*.pdf"]),
        ("stack", "Alle Pläne (Sammel-PDF)", [f"{E}/Lageplan/*alle_Plaene*"]),
        ("stack", O, [f"{E}/Lageplan/{O}/*"]),
        ("stack", "CAD", [f"{E}/Lageplan/*"]),
    ]),
    ("2 Eigene Pläne · Details", [
        ("open", [f"{E}/Detail_*/*.pdf", f"{E}/Detail_Treppe-Kern335/*.html"]),
        ("stack", "Treppe Kern 335 · Fotos", [f"{E}/Detail_Treppe-Kern335/WhatsApp*"]),
        ("stack", "Grafiken + CAD", [f"{E}/Detail_*/*"]),
        ("stack", O, [f"{E}/Detail_*/{O}/*"]),
    ]),
    ("2 Eigene Pläne · Möblierung + Nutzung", [
        ("open", [f"{E}/Möblierung+Nutzung/*.pdf"]),
        ("stack", "CAD", [f"{E}/Möblierung+Nutzung/*"]),
    ]),
    ("2 Eigene Pläne · Raumprogramm", [
        ("open", [f"{E}/Raumprogramm/*.pdf", f"{E}/Raumprogramm/*.html"]),
        ("stack", "Grafiken, Excel, CAD", [f"{E}/Raumprogramm/*"]),
        ("stack", O, [f"{E}/Raumprogramm/{O}/*"]),
    ]),
    ("3 Fotos", [("stack", t.replace("_2026-10-20", " 20.10."), [f"{F}/{t}/*"]) for t in
                 ("Fassade", "Innen", "Innenhöfe", "Details", "Historisch", "Luftbilder", "Modellfotos_2026-10-20")]),
    ("4 Entwurf · Volumenstudien", [
        ("open", [f"{D}/Vergleiche/*"]),
        ("stack", "Varianten Andis", [f"{D}/Varianten_Andis/*"]),
        ("stack", "Varianten Luca", [f"{D}/Varianten_Luca/*"]),
        ("stack", "Optionen 1–15", [f"{D}/Optionen_1-15/*"]),
        ("stack", "Lagepläne Varianten", [f"{D}/Lagepläne_Varianten/*"]),
        ("stack", "Flächenbedarf (Rhino)", [f"{D}/Flächenbedarf/*"]),
        ("stack", O, [f"{D}/Vergleiche/{O}/*", f"{D}/Lagepläne_Varianten/{O}/*"]),
    ]),
    # empty until the design has plans: the rows line up with the Bestand rows of the same name
    *[(f"4 Entwurf · {t}", [("open", [f"{D}/{t}/*"]), ("stack", O, [f"{D}/{t}/{O}/*"])])
      for t in ("Grundrisse", "Schnitte", "Ansichten", "Lageplan", "Details")],
    ("5 3D-Modelle", [
        ("open", [f"{M}/Modell-Ansichten_Web/index.html", f"{M}/Bestandsmodell/*.png"]),
        ("stack", "Modell Uni · Ansichten", [f"{M}/Bestandsmodell_Uni/*.png"]),
        ("stack", "Rhino, IFC + Bericht", [f"{M}/*/*"]),
        ("stack", O, [f"{M}/Bestandsmodell/{O}/*"]),
    ]),
    # existing building and design variants are separate prints, never one row
    ("6 3D-Druck · Bestand", [("open", [f"{P}/Bestand_M1-500/*"])]),
    ("6 3D-Druck · Entwurf", [
        ("open", [f"{P}/Entwurf_M1-500/*"]),  # complete variants, assembly sheet, LIESMICH
        # one stack per print plate instead of one 70-part pile ("A1_Platte-2" -> "A1 · Platte 2")
        *[("stack", p.replace("_", " · ").replace("-", " "), [f"{P}/Entwurf_Platten/{p}/*"]) for p in PLATES],
        ("stack", O, [f"{P}/Entwurf_M1-500/{O}/*"]),
    ]),
]

REFS = {"id": "html/referenzen/index.html", "kind": "html", "title": "Referenzen · Bibliotheken", "ext": "html",
        "size": 0, "dl": "html/referenzen/index.html", "raw": "html/referenzen/index.html",
        "url": "html/referenzen/index.html"}
# dates from the brief, a repo-only page shown live in its card ("live"): one big column left of everything (LEFT)
ZEITPLAN = {"id": "html/zeitplan.html", "kind": "html", "title": "Zeitplan · Termine", "ext": "html", "size": 0,
            "dl": "html/zeitplan.html", "raw": "html/zeitplan.html", "url": "html/zeitplan.html", "live": True, "ar": 0.3015}
LEFT = "Zeitplan"

# rows of (Grundlagen | eigene Pläne | Entwurf); a row starts below the tallest cell of the row above, so the
# Entwurf plans sit level with the Bestand plans of the same name
GRID = [
    ("0 Aufgabe", None, "4 Entwurf · Volumenstudien"),
    *[(f"1 Uni · {t}", f"2 Eigene Pläne · {t}", f"4 Entwurf · {t}") for t in ("Grundrisse", "Schnitte", "Ansichten", "Lageplan")],
    (None, "2 Eigene Pläne · Details", "4 Entwurf · Details"),
    ("1 Uni · Archiv + Nachbarn", "2 Eigene Pläne · Möblierung + Nutzung", "6 3D-Druck · Entwurf"),
    ("3 Fotos", "2 Eigene Pläne · Raumprogramm", "Referenzen"),
    ("5 3D-Modelle", "6 3D-Druck · Bestand", None),
]

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
                    old["items"] += [item(r) for r in older]
            cards += [item(r) for r in rels]
        return cards + stacks

    sections = [{"title": t, "items": build(t, es)} for t, es in SECTIONS]

    # reference page lives only in the repo (built by build_refs.py), not in the Seafile tree
    preview = next(THUMBS.glob("referenzen-*.webp"))  # name carries a content hash, written by build_refs.py
    w, h = Image.open(preview).size
    sections.append({"title": "Referenzen", "items": [REFS | {"thumb": preview.relative_to(REPO).as_posix(), "ar": round(w / h, 4)}]})
    sections.append({"title": LEFT, "items": [dict(ZEITPLAN)]})

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
        h = {"3 Fotos": ROW_H * 2, "Referenzen": ROW_H * 4, LEFT: ROW_H * 26}.get(s["title"], ROW_H)
        x = 0
        for it in s["items"]:
            w = h * it.get("ar", 1.0)  # square unless the item knows its shape
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

    by = {s["title"]: s for s in sections}
    cols = (0, MAX_W + 1200, 2 * MAX_W + 1200 + 4000)  # the wider gap parts Grundlagen (left) from Entwurf (right)
    y = 0
    for row in GRID:
        y = max([flow(by[t], x, y) for x, t in zip(cols, row) if t in by] or [y])
    for s in sections:  # anything not in GRID (e.g. "Neu / unsortiert") goes below the left column
        if s["title"] != LEFT and not any(s["title"] in row for row in GRID):
            y = flow(s, 0, y)
    s = by.get(LEFT)
    if s:  # its single card ends 1000 before the first column, top level with the first row
        flow(s, -round(ROW_H * 26 * s["items"][0]["ar"] + 1000), 0)
    # files dropped onto the board online live in the repo (uploads/), not in the Seafile tree: keep them where they lie
    ids = {i["id"] for i in items}
    items += [i for i in old.get("items", []) if i.get("upload") and i["id"] not in ids]
    board.write_text(json.dumps({"labels": labels, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")


def relayout():
    """Re-sort the existing board.json into SECTIONS order; touches no files and no Seafile."""
    old = json.loads((REPO / "board.json").read_text(encoding="utf-8"))
    labs = sorted(old["labels"], key=lambda l: l["y"])
    groups = {l["text"]: [] for l in labs}
    names = {l["text"]: l["id"][len("label:"):] for l in labs}
    for it in sorted((i for i in old["items"] if not i.get("upload")), key=lambda i: (i["y"], i["x"])):  # layout() keeps uploads
        # boards written before the "section" field: plain vertical bands under each label
        sec = it.get("section") or names[[l for l in labs if l["y"] <= it["y"]][-1]["text"]]
        groups.setdefault(sec, []).append(it)
    groups = {names.get(k, k): v for k, v in groups.items()}
    order = [t for t, _ in SECTIONS] + ["Referenzen"]
    order += [t for t in groups if t not in order]
    layout([{"title": t, "items": groups[t]} for t in order if groups.get(t)])


if __name__ == "__main__":
    relayout() if "--layout" in sys.argv else main()
