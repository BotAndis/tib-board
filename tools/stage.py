"""Copy the current TIB thesis files into the local 'Übersicht Main Datein' tree (mirrored 1:1 to Seafile).

Existing files are skipped, so re-running only adds new ones. Then upload the tree to Seafile.
Usage: python stage.py [out_dir]
"""
import os, sys, glob, shutil

B = "D:/UNI/Bachelor"
PU = f"{B}/02_Bestand/Pläne uni"
AN = f"{B}/02_Bestand/Analyse"
VAR = f"{B}/04_Entwurf/Varianten/2026-10-26_Claude-Optionen"
DR = f"{B}/04_Modelle/3D-Druck"
DRV = f"{DR}/2026-10-27_Varianten-M1-500"
FO = f"{B}/02_Bestand/Fotos"
RF = "D:/Claude_Workspaces/CX-NEA/Rhino-Arch-AI/work/refs/tib"


def pf(*names):  # press photos by name pattern
    return [f"{FO}/Pressefotos/{n}" for n in names]


def dsc(*ranges):  # site-visit photos 21.10. by number range
    return [f"{FO}/2026-10-21_Perspektive-Fotos/DSC_{n}.JPG" for a, b in ranges for n in range(a, b + 1)]


# destination folder -> source globs (recursive ** keeps the subfolders below the glob root)
PLAN = {
    "00_Aufgabe": [f"{B}/00_Aufgabe/*.pdf"],
    "01_Bestand_Uni/Grundrisse": [f"{PU}/GR/*.pdf", f"{PU}/GR/*.dwg"],
    "01_Bestand_Uni/Schnitte": [f"{PU}/SC/*.pdf", f"{PU}/SC/*.dwg"],
    "01_Bestand_Uni/Ansichten": [f"{PU}/Ansichten/*.pdf", f"{PU}/Ansichten/*.dwg", f"{PU}/Ansichten/*.pln"],
    "01_Bestand_Uni/Lageplan": [f"{PU}/LP/*.pdf", f"{PU}/LP/*.dwg"],
    "01_Bestand_Uni/Nachbargebaeude": [f"{PU}/Nachbargebäude/**/*.pdf", f"{PU}/Nachbargebäude/**/*.dwg"],
    "01_Bestand_Uni/Raumliste": [f"{B}/02_Bestand/Raumliste/*.xlsx"],
    "01_Bestand_Uni/Buchscans": [f"{B}/02_Bestand/Buchscans/*.jpg"],
    "02_Plaene/Grundrisse": [f"{AN}/Grundrisse/TIB_1102_Grundriss_{g}_M1-*" for g in ("??", "???", "Dach")],
    "03_Analyse/Moeblierung_Nutzung": [f"{AN}/Grundrisse/*Moeblierung*"],
    "02_Plaene/Schnitte": [f"{AN}/Schnitte/*"],
    "02_Plaene/Lageplan": [f"{AN}/Lageplan/*"],
    "03_Analyse/Raumprogramm": [f"{AN}/Raumprogramm/*.pdf", f"{AN}/Raumprogramm/*.png", f"{AN}/Raumprogramm/*.xlsx",
                                f"{AN}/Raumprogramm/*.dxf", f"{AN}/Raumprogramm/TIB_1102_D_Flaechen-Editor_10.html"],
    "02_Plaene/Details": [f"{AN}/Details/*.pdf", f"{AN}/Details/*.svg"],
    "02_Plaene/Details/Kern335": [f"{AN}/Details/Kern335/*.pdf", f"{AN}/Details/Kern335/*.png", f"{AN}/Details/Kern335/*.dxf",
                                   f"{AN}/Details/Kern335/*.html",
                                   f"{AN}/Details/Kern335/*.3dm", f"{AN}/Details/Kern335/Fotos/*"],
    "04_Entwurf/Lageplaene_Varianten": [f"{VAR}/Lageplaene/*.pdf"],
    "04_Entwurf/Renderings": [f"{VAR}/*.jpg"],
    "04_Entwurf/Flaechenbedarf": [f"{B}/04_Entwurf/Varianten/*.3dm"],
    # shortcut: the Rhino model itself is left out while it is still being edited; add its final .3dm here when done
    "05_3D-Modelle/Bestandsmodell": [f"{B}/04_Modelle/Bestandsmodell/*.png", f"{B}/04_Modelle/Bestandsmodell/*Pruefbericht_v3.md"],
    "05_3D-Modelle/Bestandsmodell_Uni": [f"{PU}/Modell/TIB_011_detail_final.3dm", f"{PU}/Modell/_shots/*.png"],
    "05_3D-Modelle/Modell-Ansichten_HTML": ["D:/Claude_Workspaces/CX-NEA/Rhino-Arch-AI/work/review/tib/publish/**/*"],
    "05_3D-Modelle/Volumenmodell":[f"{PU}/Tib_Volument.3dm"],
    "05_3D-Modelle/Umgebungsmodell": ["D:/Claude_Workspaces/CX-NEA/Map-Maker/downloads/hannover-tib/TIB_Umgebung_500m_LoD2.*"],
    "05_3D-Modelle/Web-Vorschau": [f"{B}/04_Modelle/Web-Vorschau/*.glb"],
    "06_3D-Druck/Bestand_M1-500": [f"{PU}/Modell/TIB_Druck_1zu500_mm.stl", f"{DR}/druck bestand tib getrennt.stl", f"{DR}/Bambulab/*.3mf"],
    "06_3D-Druck/Varianten_M1-500": [f"{DRV}/*.png", f"{DRV}/*.txt", f"{DRV}/komplett_mit-Stuetzen/*.stl"],
    "06_3D-Druck/Varianten_M1-500/geteilt_ohne-Stuetzen": [f"{DRV}/geteilt_ohne-Stuetzen/**/*.stl"],
    # photos sorted by topic (incl. the references the 3D model was built from); new photos: add them to a topic
    "07_Fotos/Modellfotos_2026-10-20": [f"{FO}/2026-10-20_Besichtigung/*.JPG"],
    "07_Fotos/Fassade": [f"{FO}/Online/*", *pf("TIB_Aussenansicht1_RGB.JPG", "TIB_Aussenansicht_Standort_*", "Technische_*",
                                                 "csm_technat-aussen*", "images.jpg"),
                         f"{RF}/ph/cat_00.jpg", f"{RF}/ph/cat_01.jpg", f"{RF}/ph/welf_*.jpg", f"{RF}/web/w1_00.jpg",
                         f"{RF}/web/w7_11.jpg", f"{RF}/user/review3/eg_[st]*", f"{RF}/user/review3/annex_east_*", f"{RF}/sv/*.png"],
    "07_Fotos/Innen": [*dsc((2497, 2500), (2510, 2547), (2552, 2557), (2560, 2561), (2569, 2572)),
                       *pf("*Galerie*", "*Lesesaal*", "hannover_tib_ub_*"), f"{RF}/ph/cat_0[2-6].jpg",
                       f"{RF}/user/interior_*.webp", f"{RF}/web/w3_13.jpg"],
    "07_Fotos/Innenhoefe": dsc((2501, 2509), (2562, 2568)),
    "07_Fotos/Details": dsc((2548, 2551), (2558, 2559)),
    "07_Fotos/Historisch": [*pf("Screenshot_*", "TIB_Außenansicht*", "TIB_im_Bau_*"), f"{RF}/user/review3/eg_historic_bw.png"],
    "07_Fotos/Luftbilder": [*pf("gottfried-*"), f"{RF}/web/wc_02.jpg", f"{RF}/cesium/tib_ortho_google.png",
                            f"{RF}/cesium/corners.png", f"{RF}/user/review3/annex_roof_google3d.webp"],
}


# photos left out on purpose: same perspective as a kept one (one day + one night view per viewpoint is enough)
SKIP_FOTOS = {f"DSC_{n}.JPG" for n in (
    2460, 2461, 2462, 2464, 2465, 2466, 2468, 2469, 2471, 2472, 2473, 2474, 2475, 2477, 2478, 2498, 2503, 2504, 2506,
    2508, 2509, 2512, 2514, 2518, 2521, 2524, 2526, 2529, 2530, 2532, 2533, 2535, 2536, 2538, 2539, 2541, 2543, 2546,
    2548, 2552, 2554, 2555, 2559, 2560, 2563, 2565, 2571)} | {
    "cat_01.jpg", "cat_02.jpg", "commons_0dcff9.jpg", "commons_551fbe.jpg", "commons_5b2aae.jpg", "commons_95bc1d.jpg",
    "corners.png", "csm_technat-aussen-2_d59ba30e01.jpg", "eg_sw_day_tinted.webp", "eg_sw_dusk_all_around.webp",
    "images.jpg", "interior_1_lesesaal.webp", "interior_2_gallery.webp", "n_nw_00.png", "s_east_00.png", "w3_13.jpg",
    "welf_01.jpg", "welf_06.jpg"}


def stage(out):
    n = 0
    for dest, globs in PLAN.items():
        for g in globs:
            root = g.split("**")[0] if "**" in g else None
            for src in glob.glob(g, recursive=True):
                if not os.path.isfile(src) or dest.startswith("07_Fotos") and os.path.basename(src) in SKIP_FOTOS:
                    continue
                rel = os.path.relpath(src, root) if root else os.path.basename(src)
                dst = os.path.join(out, dest, rel)
                if os.path.exists(dst):
                    continue
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                n += 1
    return n


if __name__ == "__main__":
    print(stage(sys.argv[1] if len(sys.argv) > 1 else f"{B}/Übersicht Main Datein"), "files copied")
