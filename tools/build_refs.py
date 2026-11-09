"""Build html/referenzen/data.json + webp images from collected raw folders (<raw>/<slug>/meta.json + role images).
Run: uv run --no-project --python 3.12 --with pillow python build_refs.py <raw dir>
Re-running replaces a project's images; projects not in <raw> stay as they are in data.json.
"""
import json, sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "html" / "referenzen"
PLANS = {"eg", "og", "og2", "schnitt"}
ROLES = ["eg", "og", "og2", "schnitt", "aussen", "innen1", "innen2"]
# Bestand weitergebaut: the most relevant group for the TIB task
UMBAU = {"fribourg-bcu", "kopenhagen-black-diamond", "leipzig-dnb", "peking-nationalbibliothek", "malmoe-stadtbibliothek",
         "zuerich-rechtswiss", "freiburg-ub", "tilburg-lochal", "luzern-ub", "berlin-staatsbibliothek",
         "washington-mlk-umbau", "paris-richelieu", "oxford-weston", "bern-vonroll", "stuttgart-wlb",
         "toronto-story-arts", "budapest-bbu"}
PREVIEW = ["washington-mlk", "washington-mlk-umbau", "berlin-grimm-zentrum", "freiburg-ub"]  # rows on the board tile
# Editorial TIB selection: own competition plus related library types and transformations.
KT = {"fribourg-bcu", "washington-mlk", "washington-mlk-umbau", "eindhoven-metaforum",
      "stockholm-asplund", "paris-richelieu", "yale-beinecke", "exeter-kahn", "berlin-grimm-zentrum", "latem-office"}
# one line: how the building is organised (Magazin / Freihand / Lesen / Erschließung)
NOTES = {
    "fribourg-bcu": "Wettbewerbsentwurf 2010, 3. Preis, nicht realisiert: Altbau restaurieren, unterirdisch erweitern; ovaler Lesesaal mit großem Oberlicht unter dem Garten.",
    "kopenhagen-black-diamond": "Erweiterung am Altbau: zwei Blöcke, dazwischen ein Atrium-Spalt; Brücken über die Straße zum Bestand.",
    "peking-nationalbibliothek": "Erweiterung: Schatzmagazin im Sockel, darüber offene Lese-Terrassen unter einem schwebenden Dach.",
    "leipzig-dnb": "Anbau an den Altbau: Magazingeschosse im Raster, ein öffentlicher Weg verbindet Alt und Neu.",
    "berlin-staatsbibliothek": "Umbau im Bestand: neuer Lesesaal-Kubus im kriegszerstörten Kern, Magazine ringsum im Altbau.",
    "phoenix-burton-barr": "Großer Block: Erschließung über das Atrium „Crystal Canyon“, oben ein stützenfreier Lesesaal unter abgehängtem Dach.",
    "norwich-millennium": "Bibliothek als ein Flügel eines Hufeisens um ein großes gläsernes Atrium (The Forum).",
    "amsterdam-oba": "Gestapelte Geschosse um eine zentrale Rolltreppenhalle; Bereiche nach Themen pro Ebene.",
    "stuttgart-stadtbibliothek": "Würfel: innen das „Herz“ (Leerraum über mehrere Ebenen), darüber der trichterförmige Galeriesaal.",
    "birmingham-library": "Gestapelte Boxen; Rotunden als Lichthöfe verbinden die Ebenen, Bücherrotunde im 3. OG.",
    "oslo-deichman": "Drei Lichtschächte durchstoßen alle Geschosse; offene Raumfolge statt abgetrennter Abteilungen.",
    "aarhus-dokk1": "Ein großer offener Bibliotheksboden auf einem Sockel; Kerne gliedern die Fläche.",
    "stockholm-asplund": "Rotunde als zentraler Ausleihsaal mit Bücherwänden; U-förmige Flügel mit Lesesälen.",
    "tilburg-lochal": "Umbau einer Lokhalle: Halle bleibt offen, Bibliothek auf eingestellten Plattformen und Sitzstufen.",
    "washington-mlk": "Mies 1972: Stahl-Glas-Box im Stützenraster, offene Geschosse um Kerne, zurückgesetztes Erdgeschoss.",
    "washington-mlk-umbau": "Modernisierung 2020: Raster bleibt; neue Treppen durch die Kerne, neues Dachgeschoss mit Terrasse.",
    "london-peckham": "Umgedrehtes L: die Bibliothek als Box auf Stützen über dem Platz, Pods im Lesesaal.",
    "london-whitechapel": "Gestapelte Geschosse an einer Rolltreppen-Fassade zur Straße; oben Café und Terrasse.",
    "scottsdale-arabian": "Eingeschossig: ein Raum unter einem gefalteten Dach, Licht über eine Schlucht im Inneren.",
    "viana-siza": "Quadratischer Ring über dem Platz, Lesesäle umlaufen einen offenen Hof.",
    "vennesla": "Ein langer Raum; Holzrippen tragen das Dach und bilden zugleich Regale und Nischen.",
    "ceuta": "Bibliothek über einer archäologischen Grabung: Lesesäle auf Plattformen über den Funden.",
    "viipuri-aalto": "Zwei versetzte Riegel: Lesesaal mit Oberlichtern auf mehreren Ebenen, Ausleihe in der Mitte.",
    "heidenheim-dudler": "Kompakter Block mit einer zentralen Treppenhalle durch alle Geschosse.",
    "delft-tu": "Bibliothek unter einem begrünten Dachkeil: eine große Halle mit Bücherwand, der Kegel bringt Licht.",
    "berlin-philologische": "Einbau in einen Innenhof der „Rostlaube“: geschwungene Geschosse unter einer Kuppelhülle.",
    "berlin-grimm-zentrum": "Langer Block, Regale im Raster; mittiger Lesesaal mit Terrassen, die nach oben zurückspringen.",
    "katowice-ciniba": "Kompakter Würfel mit Atrium in der Mitte, Lesebereiche ringsum; Kompaktmagazin im UG.",
    "freiburg-ub": "Umbau einer 1970er-Bibliothek: Tragwerk bleibt, neue Hülle; offenes Erdgeschoss, Lesesäle darüber.",
    "utrecht-ub": "Schwarzer Block: Magazine als geschlossene Boxen in der Halle, Leseplätze dazwischen.",
    "luzern-ub": "Umbau des Baus von 1951: Bestand saniert, Struktur und Lesesaal bleiben.",
    "darmstadt-ulb": "Großer Block mit zentralem Atrium; Leseplätze an der Fassade, Freihand in der Gebäudetiefe.",
    "exeter-kahn": "Drei Schichten: außen Leseplätze am Fenster, in der Mitte Regale, innen ein großer Lichthof.",
    "toronto-story-arts": "Gläserner Anbau an einen Mies-artigen Bau von 1954: Leseband an der Glasfassade, Regale und Räume dahinter.",
    "budapest-bbu": "Neubau am 1970er-Campus: unten Cafeteria + Hörsaal, oben die Bibliothek um einen Kern; Galerie verbindet die Altbauten.",
    "stuttgart-wlb": "Erweiterungsbau neben dem Altbau von 1970; beide Häuser sind verbunden und werden gemeinsam genutzt.",
    "kanazawa-umimirai": "Ein großer quadratischer Raum über zwei Geschosse; die Lochfassade bringt gleichmäßiges Licht.",
    "paris-richelieu": "Umbau des historischen Bibliotheksblocks: Säle und Magazine saniert, neue Erschließung und Glasgalerie am Ehrenhof.",
    "latem-office":"Runder Grundriss: Regale entlang der Rundwand, rechteckiger Kern mit Glashof in der Mitte.",
}


def main(raw):
    data_file = OUT / "data.json"
    data = {p["slug"]: p for p in json.loads(data_file.read_text(encoding="utf-8"))} if data_file.exists() else {}
    for meta_file in sorted(Path(raw).glob("*/meta.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        slug, src_dir = meta["slug"], meta_file.parent
        if not any((src_dir / i["file"]).exists() for r, i in meta.get("images", {}).items() if r in {"eg", "og", "og2"}):
            print("skipped, no floor plan:", slug)  # a row without a floor plan can't be compared
            data.pop(slug, None)
            continue
        dst = OUT / "img" / slug
        dst.mkdir(parents=True, exist_ok=True)
        images = {}
        for role in ROLES:
            info = meta.get("images", {}).get(role)
            if not info or not (src_dir / info["file"]).exists():
                continue
            im = Image.open(src_dir / info["file"])
            if im.mode in ("RGBA", "LA", "P"):  # transparent plans -> white paper, not black
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, "white")
                bg.paste(im, mask=im.split()[3])
                im = bg
            im = im.convert("RGB")
            im.thumbnail((2200, 2200) if role in PLANS else (1600, 1600))
            im.save(dst / f"{role}.webp", "WEBP", quality=85 if role in PLANS else 80)
            images[role] = {"label": info.get("label", ""), "src": info.get("src", ""),
                            "ar": round(im.width / im.height, 3)}
        keep = {k: meta.get(k) for k in ("slug", "title", "city", "country", "architect", "year", "category", "book_page")}
        old = data.get(slug, {})
        data[slug] = keep | {"kt": slug in KT, "umbau": slug in UMBAU or bool(meta.get("umbau")), "note": NOTES.get(slug) or meta.get("note", ""),
                             "link": meta.get("link") or old.get("link"), "relevance": meta.get("relevance") or old.get("relevance"),
                             "images": images}
    # Also flag existing references, even when this run has no raw folder for them.
    for slug, project in data.items():
        project["kt"] = slug in KT
    ordered = sorted(data.values(), key=lambda p: (p["category"], p.get("book_page") or 999, p["slug"]))  # slug keeps MLK original before its Umbau
    data_file.write_text(json.dumps(ordered, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(ordered), "projects;", sum(len(p["images"]) for p in ordered), "images")
    preview({p["slug"]: p for p in ordered})


def preview(data):
    """Board tile: a miniature of the page itself (header, column labels, a few full rows)."""
    from PIL import ImageDraw, ImageFont
    def font(size, bold=False):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/segoeui{'b' if bold else ''}.ttf", size)
        except OSError:
            return ImageFont.truetype(f"DejaVuSans{'-Bold' if bold else ''}.ttf", size)
    W, M, G = 2000, 60, 16
    cw = (W - 2 * M - 5 * G) // 6
    ch = cw * 3 // 4
    rows = [data[s] for s in PREVIEW if s in data]
    im = Image.new("RGB", (W, 260 + len(rows) * (ch + 130)), "white")
    dr = ImageDraw.Draw(im)
    dr.text((M, 46), "Referenzen · Bibliotheken", font=font(56, True), fill="#1a1a1a")
    for i, t in enumerate(["ERDGESCHOSS", "REGELGESCHOSS", "SCHNITT", "AUSSEN", "INNEN", "INNEN"]):
        dr.text((M + i * (cw + G), 140), t, font=font(22), fill="#8a8a8a")
    y = 190
    for p in rows:
        dr.line((M, y, W - M, y), fill="#e7e7e7", width=2)
        dr.text((M, y + 26), p["title"], font=font(34, True), fill="#1a1a1a")
        dr.text((M, y + 72), f"{p['city']}, {p['country']} · {p['architect']} · {p['year']}", font=font(26), fill="#8a8a8a")
        top = y + 118
        for i, role in enumerate(["eg", "og", "schnitt", "aussen", "innen1", "innen2"]):
            x, f = M + i * (cw + G), OUT / "img" / p["slug"] / f"{role}.webp"
            if not f.exists():
                continue
            src = Image.open(f).convert("RGB")
            if role in PLANS:  # plans fit inside the cell, photos fill it
                src.thumbnail((cw - 16, ch - 16))
                im.paste(src, (x + (cw - src.width) // 2, top + (ch - src.height) // 2))
            else:
                s = min(src.width / cw, src.height / ch)
                bw, bh = int(cw * s), int(ch * s)
                src = src.crop(((src.width - bw) // 2, (src.height - bh) // 2, (src.width + bw) // 2, (src.height + bh) // 2)).resize((cw, ch))
                im.paste(src, (x, top))
            dr.rectangle((x, top, x + cw - 1, top + ch - 1), outline="#e7e7e7", width=2)
        y = top + ch + 12
    im = im.crop((0, 0, W, y + 30))
    # content hash in the name: browsers cache thumbs hard, a new preview must get a new URL
    import hashlib, io
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=86)
    thumbs = OUT.parent.parent / "thumbs"
    for old in thumbs.glob("referenzen*.webp"):
        old.unlink()
    (thumbs / f"referenzen-{hashlib.sha1(buf.getvalue()).hexdigest()[:8]}.webp").write_bytes(buf.getvalue())
    print("preview", im.size, "ar", round(im.width / im.height, 4))


if __name__ == "__main__":
    main(sys.argv[1])
