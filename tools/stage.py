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
    "06_Fotos/Besichtigung_2026-10-20": [f"{FO}/2026-10-20_Besichtigung/*.JPG"],
    "06_Fotos/Perspektiven_2026-10-21": [f"{FO}/2026-10-21_Perspektive-Fotos/*.JPG"],
    "06_Fotos/Pressefotos": [f"{FO}/Pressefotos/*"],
    "06_Fotos/Online": [f"{FO}/Online/*"],
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
