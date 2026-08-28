#!/usr/bin/env python3
"""Build brand assets for the video pipeline:
  - rasterize the P/V shield mark in cream / green / gold (into .build/)
  - instantiate four Space Grotesk weights with unique family names and
    install them so both cairosvg and PIL can select them precisely.
Run once via setup.sh (idempotent)."""
import os, re, subprocess
import cairosvg
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, ".build")
os.makedirs(BUILD, exist_ok=True)

# ---- logo rasters ----
mark = open(os.path.join(HERE, "assets", "brand-mark.svg")).read()
def recolor(svg, hexv):
    svg = re.sub(r'fill="#[0-9A-Fa-f]{6}"', f'fill="{hexv}"', svg)
    return re.sub(r'fill:\s*#[0-9A-Fa-f]{6}', f'fill:{hexv}', svg)
for name, hexv in [("cream", "#f9f6f1"), ("green", "#296037"), ("gold", "#ce9e27")]:
    cairosvg.svg2png(bytestring=recolor(mark, hexv).encode(),
                     write_to=os.path.join(BUILD, f"mark_{name}.png"), output_width=500)
print("logo rasters ->", BUILD)

# ---- weighted fonts with unique family names ----
FONTDIR = "/usr/share/fonts/truetype/pvsg"
os.makedirs(FONTDIR, exist_ok=True)
vf = os.path.join(BUILD, "SpaceGrotesk-VF.ttf")
for wght, fam in [(400, "PVSG Regular"), (500, "PVSG Medium"), (600, "PVSG SemiBold"), (700, "PVSG Bold")]:
    f = TTFont(vf)
    instantiateVariableFont(f, {"wght": wght}, inplace=True)
    nm = f["name"]
    for nid in (1, 16): nm.setName(fam, nid, 3, 1, 0x409)
    for nid in (2, 17): nm.setName("Regular", nid, 3, 1, 0x409)
    nm.setName(fam, 4, 3, 1, 0x409)
    nm.setName(fam.replace(" ", "") + "-Regular", 6, 3, 1, 0x409)
    out = os.path.join(FONTDIR, fam.replace(" ", "") + ".ttf")
    f.save(out)
    # also drop a copy in .build so PIL can load by path without fontconfig
    f.save(os.path.join(BUILD, fam.replace(" ", "") + ".ttf"))
subprocess.run(["fc-cache", "-f"], check=False)
print("fonts installed ->", FONTDIR)
