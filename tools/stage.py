"""Copy the current TIB thesis files into the local 'Übersicht Main Datein' tree (mirrored 1:1 to Seafile).

Existing files are skipped, so re-running only adds new ones. Then upload the tree to Seafile.
Usage: python stage.py [out_dir]
"""
import os, sys, glob, shutil

B = "D:/UNI/Bachelor"
PU = f"{B}/02_Bestand/Pläne uni"
AN = f"{B}/02_Bestand/Analyse"
VAR = f"{B}/03_Entwurf/Varianten/2026-10-26_Claude-Optionen"
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
    "02_Analyse/Grundrisse": [f"{AN}/Grundrisse/TIB_1102_Grundriss_{g}_M1-*" for g in ("??", "???", "Dach")],
    "02_Analyse/Grundrisse_Moeblierung": [f"{AN}/Grundrisse/*Moeblierung*"],
    "02_Analyse/Schnitte": [f"{AN}/Schnitte/*"],
    "02_Analyse/Lageplan": [f"{AN}/Lageplan/*"],
    "02_Analyse/Raumprogramm": [f"{AN}/Raumprogramm/*.pdf", f"{AN}/Raumprogramm/*.png", f"{AN}/Raumprogramm/*.xlsx",
                                f"{AN}/Raumprogramm/*.dxf", f"{AN}/Raumprogramm/TIB_1102_D_Flaechen-Editor_10.html"],
    "02_Analyse/Details": [f"{AN}/Details/*.pdf", f"{AN}/Details/*.svg"],
    "02_Analyse/Details/Kern335": [f"{AN}/Details/Kern335/*.pdf", f"{AN}/Details/Kern335/*.png", f"{AN}/Details/Kern335/*.dxf",
                                   f"{AN}/Details/Kern335/*.html",
                                   f"{AN}/Details/Kern335/*.3dm", f"{AN}/Details/Kern335/Fotos/*"],
    "03_Entwurf/Lageplaene_Varianten": [f"{VAR}/Lageplaene/*.pdf"],
    "03_Entwurf/Renderings": [f"{VAR}/*.jpg"],
    "03_Entwurf/Flaechenbedarf": [f"{B}/03_Entwurf/Varianten/*.3dm"],
    # shortcut: the Rhino model itself is left out while it is still being edited; add its final .3dm here when done
    "04_3D-Modelle/Bestandsmodell": [f"{B}/04_Modelle/Bestandsmodell/*.png", f"{B}/04_Modelle/Bestandsmodell/*Pruefbericht_v3.md"],
    "04_3D-Modelle/Bestandsmodell_Uni": [f"{PU}/Modell/TIB_011_detail_final.3dm", f"{PU}/Modell/_shots/*.png"],
    "04_3D-Modelle/Modell-Ansichten_HTML": ["D:/Claude_Workspaces/CX-NEA/Rhino-Arch-AI/work/review/tib/publish/**/*"],
    "04_3D-Modelle/Volumenmodell":[f"{PU}/Tib_Volument.3dm"],
    "04_3D-Modelle/Umgebungsmodell": ["D:/Claude_Workspaces/CX-NEA/Map-Maker/downloads/hannover-tib/TIB_Umgebung_500m_LoD2.*"],
    "04_3D-Modelle/Web-Vorschau": [f"{B}/04_Modelle/Web-Vorschau/*.glb"],
    "05_3D-Druck/Bestand_M1-500": [f"{PU}/Modell/TIB_Druck_1zu500_mm.stl", f"{DR}/druck bestand tib getrennt.stl", f"{DR}/Bambulab/*.3mf"],
    "05_3D-Druck/Varianten_M1-500": [f"{DRV}/*.png", f"{DRV}/*.txt", f"{DRV}/komplett_mit-Stuetzen/*.stl"],
    "05_3D-Druck/Varianten_M1-500/geteilt_ohne-Stuetzen": [f"{DRV}/geteilt_ohne-Stuetzen/**/*.stl"],
    # photos sorted by topic (incl. the references the 3D model was built from); new photos: add them to a topic
    "06_Fotos/Modellfotos_2026-10-20": [f"{FO}/2026-10-20_Besichtigung/*.JPG"],
    "06_Fotos/Fassade": [f"{FO}/Online/*", *pf("TIB_Aussenansicht1_RGB.JPG", "TIB_Aussenansicht_Standort_*", "Technische_*",
                                                 "csm_technat-aussen*", "images.jpg"),
                         f"{RF}/ph/cat_00.jpg", f"{RF}/ph/cat_01.jpg", f"{RF}/ph/welf_*.jpg", f"{RF}/web/w1_00.jpg",
                         f"{RF}/web/w7_11.jpg", f"{RF}/user/review3/eg_[st]*", f"{RF}/user/review3/annex_east_*", f"{RF}/sv/*.png"],
    "06_Fotos/Innen": [*dsc((2497, 2500), (2510, 2547), (2552, 2557), (2560, 2561), (2569, 2572)),
                       *pf("*Galerie*", "*Lesesaal*", "hannover_tib_ub_*"), f"{RF}/ph/cat_0[2-6].jpg",
                       f"{RF}/user/interior_*.webp", f"{RF}/web/w3_13.jpg"],
    "06_Fotos/Innenhoefe": dsc((2501, 2509), (2562, 2568)),
    "06_Fotos/Details": dsc((2548, 2551), (2558, 2559)),
    "06_Fotos/Historisch": [*pf("Screenshot_*", "TIB_Außenansicht*", "TIB_im_Bau_*"), f"{RF}/user/review3/eg_historic_bw.png"],
    "06_Fotos/Luftbilder": [*pf("gottfried-*"), f"{RF}/web/wc_02.jpg", f"{RF}/cesium/tib_ortho_google.png",
                            f"{RF}/cesium/corners.png", f"{RF}/user/review3/annex_roof_google3d.webp"],
}


def stage(out):
    n = 0
    for dest, globs in PLAN.items():
        for g in globs:
            root = g.split("**")[0] if "**" in g else None
            for src in glob.glob(g, recursive=True):
                if not os.path.isfile(src):
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
