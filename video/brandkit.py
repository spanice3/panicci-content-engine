#!/usr/bin/env python3
"""Panicci branded talking-head renderer, safe-zone aware.
CLI:  python3 brandkit.py <seamless.mp4> <captions.json> <9x16|1x1|16x9> <out.mp4>
Also importable:  brandkit.render(src, caps_json, ratio, out)"""
import sys, os, json, base64, subprocess
from PIL import Image, ImageDraw, ImageFont
import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, ".build")
FONTDIR = "/usr/share/fonts/truetype/pvsg"
DEEP="#194324"; GREEN="#296037"; SAGE="#9bbfa1"; GOLD="#ce9e27"; CREAM="#f9f6f1"; INK="#12211a"
DIMS = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
# Reserved platform-UI margins (px). 9:16 tuned to the strictest case (TikTok):
# right action rail, top tabs/status, bottom caption+music+nav.
SAFE = {"9x16": dict(top=250, bottom=480, left=64, right=190),
        "1x1":  dict(top=54,  bottom=120, left=54, right=54),
        "16x9": dict(top=60,  bottom=140, left=90, right=90)}
ENC = ["-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-r","30",
       "-c:a","aac","-b:a","144k","-ar","48000","-ac","1","-video_track_timescale","30000","-movflags","+faststart"]
FAM = {"b": "PVSG Bold", "m": "PVSG Medium", "s": "PVSG SemiBold"}

def _dur(f):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nk=1:nw=1",f]).decode())

def render(SRC, CAPS, RATIO, OUT):
    W, H = DIMS[RATIO]; S = SAFE[RATIO]; k = W / 1080.0
    mark = "data:image/png;base64," + base64.b64encode(open(os.path.join(BUILD, "mark_cream.png"), "rb").read()).decode()
    fontb = os.path.join(BUILD, "PVSGBold.ttf")
    tmp = os.path.join(os.path.dirname(os.path.abspath(OUT)) or ".", f".kit_{RATIO}")
    os.makedirs(tmp, exist_ok=True)

    def png(svg, path): cairosvg.svg2png(bytestring=svg.encode(), write_to=path, output_width=W, output_height=H)
    def T(x, y, s, size, fam, fill, ls=0, anchor="middle"):
        sp = f' letter-spacing="{ls}"' if ls else ''
        return f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{sp}>{s}</text>'
    def ground(wx, wy, wm):
        lines = "".join(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{CREAM}" stroke-opacity="0.028" stroke-width="1"/>' for y in range(0, H, 3))
        return (f'<rect width="{W}" height="{H}" fill="{DEEP}"/><rect width="{W}" height="{H}" fill="url(#g)"/>{lines}'
                f'<image href="{mark}" x="{wx}" y="{wy}" width="{wm}" height="{wm}" opacity="0.05"/>')
    DEFS = (f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{GREEN}" stop-opacity="0.35"/>'
            f'<stop offset="0.55" stop-color="{DEEP}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{INK}" stop-opacity="0.55"/></linearGradient></defs>')
    cy = H * 0.5
    ms = int(300 * k)
    png(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{DEFS}{ground(W*0.55,H*0.62,int(1100*k))}'
        f'<image href="{mark}" x="{W/2-ms/2}" y="{cy-ms-60*k}" width="{ms}" height="{ms}"/>'
        f'{T(W/2,cy+30*k,"PANICCI VENTURES",int(72*k),FAM["b"],CREAM,ls=6*k)}'
        f'<rect x="{W/2-70*k}" y="{cy+58*k}" width="{140*k}" height="{4*k}" fill="{GOLD}"/>'
        f'{T(W/2,cy+130*k,"Sammy P takes you from A to C",int(32*k),FAM["m"],SAGE)}'
        f'{T(W/2,cy+250*k,"SEO · AEO · GEO",int(30*k),FAM["s"],GOLD,ls=12*k)}</svg>', f"{tmp}/intro.png")
    mo = int(190 * k)
    png(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{DEFS}{ground(-W*0.2,H*0.55,int(1100*k))}'
        f'<image href="{mark}" x="{W/2-mo/2}" y="{cy-mo-90*k}" width="{mo}" height="{mo}"/>'
        f'{T(W/2,cy+10*k,"Follow along.",int(72*k),FAM["b"],CREAM)}'
        f'{T(W/2,cy+70*k,"New SEO · AEO · GEO plays every week.",int(30*k),FAM["m"],SAGE)}'
        f'<rect x="{W/2-70*k}" y="{cy+108*k}" width="{140*k}" height="{4*k}" fill="{GOLD}"/>'
        f'{T(W/2,cy+200*k,"panicciventures.com",int(42*k),FAM["s"],CREAM,ls=2)}'
        f'{T(W/2,cy+258*k,"Sammy P takes you from A to C",int(28*k),FAM["m"],GOLD)}</svg>', f"{tmp}/outro.png")
    # lower third (top-left, inside safe inset)
    lx, ly = S["left"], S["top"]; lw = int(min(W-S["left"]-S["right"], 720*k)); lh = int(150*k); ms2 = int(90*k)
    png(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">'
        f'<defs><filter id="ds"><feDropShadow dx="0" dy="{6*k}" stdDeviation="{12*k}" flood-color="#000" flood-opacity="0.45"/></filter></defs>'
        f'<g filter="url(#ds)"><rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="{16*k}" fill="{DEEP}" fill-opacity="0.92"/>'
        f'<rect x="{lx}" y="{ly}" width="{10*k}" height="{lh}" fill="{GOLD}"/></g>'
        f'<image href="{mark}" x="{lx+30*k}" y="{ly+30*k}" width="{ms2}" height="{ms2}"/>'
        f'{T(lx+140*k,ly+66*k,"Sammy P",int(44*k),FAM["b"],CREAM,anchor="start")}'
        f'{T(lx+140*k,ly+108*k,"Panicci Ventures · SEO · AEO · GEO",int(23*k),FAM["m"],SAGE,anchor="start")}</svg>', f"{tmp}/lt.png")
    # logo bug
    bs = int(84 * k)
    if RATIO == "16x9": bx, by = W-bs-int(54*k), H-bs-int(54*k)
    else: bx, by = S["left"], S["top"]
    png(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><image href="{mark}" x="{bx}" y="{by}" width="{bs}" height="{bs}" opacity="0.9"/></svg>', f"{tmp}/bug.png")
    # captions
    caps = json.load(open(CAPS))
    fsize = 58 if RATIO == "9x16" else int(54 * k)
    font = ImageFont.truetype(fontb, fsize)
    box_l, box_r = S["left"], W - S["right"]; cxc = (box_l + box_r) // 2; maxw = box_r - box_l
    bottom_edge = H - S["bottom"] - int(10 * k)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10))); padx = int(40*k); pady = int(22*k); lh_ = int(fsize*1.18)
    def wrap(text):
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if d0.textlength(t, font=font) <= maxw - 2*padx: cur = t
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines
    capmeta = []
    for i, c in enumerate(caps):
        lines = wrap(c["text"]); tw = max(d0.textlength(ln, font=font) for ln in lines)
        pw = int(tw)+2*padx; ph = lh_*len(lines)+2*pady
        img = Image.new("RGBA", (W, H), (0,0,0,0)); d = ImageDraw.Draw(img)
        y1 = bottom_edge; y0 = y1-ph; x0 = cxc-pw//2; x1 = cxc+pw//2
        d.rounded_rectangle([x0,y0,x1,y1], radius=int(20*k), fill=(25,67,36,222))
        d.rounded_rectangle([cxc-int(30*k),y1-int(12*k),cxc+int(30*k),y1-int(8*k)], radius=2, fill=(206,158,39,255))
        yy = y0+pady
        for ln in lines:
            w_ = d.textlength(ln, font=font); d.text((cxc-w_/2, yy), ln, font=font, fill=(249,246,241,255)); yy += lh_
        p = f"{tmp}/cap{i}.png"; img.save(p); capmeta.append({"file": p, "start": c["start"], "end": c["end"]})
    # crop/scale + composite
    ar = W/H; sW, sH = 1920, 1080
    cW = min(sW, round(sH*ar)); cH = min(sH, round(sW/ar)); cW -= cW % 2; cH -= cH % 2
    vf = f"crop={cW}:{cH}:(iw-{cW})/2:(ih-{cH})/2,scale={W}:{H},setsar=1,fps=30"
    dmain = _dur(SRC)
    bug_enable = "gte(t,6.3)" if RATIO != "16x9" else "gte(t,0)"
    inp = ["-i", SRC, "-i", f"{tmp}/lt.png", "-i", f"{tmp}/bug.png"] + sum([["-i", c["file"]] for c in capmeta], [])
    fc = [f"[0:v]{vf}[base];",
          f"[2:v]format=rgba[bug];[base][bug]overlay=0:0:enable='{bug_enable}'[v0];",
          "[1:v]format=rgba[lt];[v0][lt]overlay=0:0:enable='between(t,0.4,6.1)'[vb];"]
    cur = "vb"
    for i, c in enumerate(capmeta):
        fc.append(f"[{3+i}:v]format=rgba[p{i}];[{cur}][p{i}]overlay=0:0:enable='between(t,{c['start']},{c['end']})'[vc{i}];"); cur = f"vc{i}"
    fc.append(f"[{cur}]fade=t=in:st=0:d=0.15,fade=t=out:st={dmain-0.30:.2f}:d=0.30[vout]")
    subprocess.check_call(["ffmpeg","-hide_banner","-loglevel","error","-y",*inp,"-filter_complex","".join(fc),"-map","[vout]","-map","0:a",*ENC,f"{tmp}/main.mp4"])
    def card(png_, t, fi, fo, out):
        subprocess.check_call(["ffmpeg","-hide_banner","-loglevel","error","-y","-loop","1","-t",str(t),"-i",png_,
            "-f","lavfi","-t",str(t),"-i","anullsrc=r=48000:cl=mono",
            "-vf",f"fps=30,fade=t=in:st=0:d={fi},fade=t=out:st={t-fo:.2f}:d={fo},format=yuv420p","-map","0:v","-map","1:a",*ENC,out])
    card(f"{tmp}/intro.png", 2.5, 0.5, 0.4, f"{tmp}/intro.mp4")
    card(f"{tmp}/outro.png", 3.6, 0.4, 0.5, f"{tmp}/outro.mp4")
    open(f"{tmp}/cc.txt", "w").write("".join(f"file '{os.path.abspath(f)}'\n" for f in [f"{tmp}/intro.mp4", f"{tmp}/main.mp4", f"{tmp}/outro.mp4"]))
    subprocess.check_call(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",f"{tmp}/cc.txt","-c","copy","-movflags","+faststart",OUT])
    return OUT

if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print("wrote", sys.argv[4])
