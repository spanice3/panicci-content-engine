#!/usr/bin/env python3
"""Panicci branded talking-head renderer, safe-zone aware.
CLI:  python3 brandkit.py <seamless.mp4> <captions.json> <9x16|1x1|16x9> <out.mp4>
Also importable:  brandkit.render(src, caps_json, ratio, out)

One ffmpeg pass: face-centred crop (face.py), PV bug + lower third, captions placed so they never sit on Sammy's
face, then the animated open and close cards (opener.py) laid over the footage. The open card's first frame is
also saved as <out>_cover.png for the Reels/Shorts cover."""
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

def _probe(f):
    w, h = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", f]).decode().strip().split(",")[:2]
    return int(w), int(h)


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _area(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def render(SRC, CAPS, RATIO, OUT, intro=True, outro=True, texts=None, cover=None):
    """intro/outro=False for paid ads (adbuild.py): an ad has to open on the hook.
    texts: opener.texts_from(...) for the open/close cards (derived from the captions when None).
    cover: where to save the cover still (default <OUT>_cover.png; only written when intro is on)."""
    W, H = DIMS[RATIO]; S = SAFE[RATIO]; k = W / 1080.0
    mark = "data:image/png;base64," + base64.b64encode(open(os.path.join(BUILD, "mark_cream.png"), "rb").read()).decode()
    fontb = os.path.join(BUILD, "PVSGBold.ttf")
    tmp = os.path.join(os.path.dirname(os.path.abspath(OUT)) or ".", f".kit_{RATIO}")
    os.makedirs(tmp, exist_ok=True)

    def svgpng(svg, path, w, h):
        cairosvg.svg2png(bytestring=svg.encode(), write_to=path, output_width=w, output_height=h)
    def T(x, y, s, size, fam, fill, ls=0, anchor="middle"):
        sp = f' letter-spacing="{ls}"' if ls else ''
        return f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{sp}>{s}</text>'
    # lower third (top-left, inside safe inset): drawn on its own small canvas, shadow included
    lx, ly = S["left"], S["top"]; lw = int(min(W-S["left"]-S["right"], 720*k)); lh = int(150*k); ms2 = int(90*k)
    pad = int(40 * k); ltw, lth = lw + 2 * pad, lh + 2 * pad
    svgpng(f'<svg xmlns="http://www.w3.org/2000/svg" width="{ltw}" height="{lth}">'
        f'<defs><filter id="ds"><feDropShadow dx="0" dy="{6*k}" stdDeviation="{12*k}" flood-color="#000" flood-opacity="0.45"/></filter></defs>'
        f'<g filter="url(#ds)"><rect x="{pad}" y="{pad}" width="{lw}" height="{lh}" rx="{16*k}" fill="{DEEP}" fill-opacity="0.92"/>'
        f'<rect x="{pad}" y="{pad}" width="{10*k}" height="{lh}" fill="{GOLD}"/></g>'
        f'<image href="{mark}" x="{pad+30*k}" y="{pad+30*k}" width="{ms2}" height="{ms2}"/>'
        f'{T(pad+140*k,pad+66*k,"Sammy P",int(44*k),FAM["b"],CREAM,anchor="start")}'
        f'{T(pad+140*k,pad+108*k,"Panicci Ventures · SEO · AEO · GEO",int(23*k),FAM["m"],SAGE,anchor="start")}</svg>',
        f"{tmp}/lt.png", ltw, lth)
    # logo bug (the PV mark, top-left after the lower third leaves)
    bs = int(84 * k)
    if RATIO == "16x9": bx, by = W-bs-int(54*k), H-bs-int(54*k)
    else: bx, by = S["left"], S["top"]
    svgpng(f'<svg xmlns="http://www.w3.org/2000/svg" width="{bs}" height="{bs}"><image href="{mark}" x="0" y="0" width="{bs}" height="{bs}" opacity="0.9"/></svg>',
           f"{tmp}/bug.png", bs, bs)
    LT = (lx, ly, lx + lw, ly + lh); BUG = (bx, by, bx + bs, by + bs)
    OBST = [(LT, 0.4, 6.1), (BUG, 6.3 if RATIO != "16x9" else 0.0, 1e9)]

    # face-centred crop: the frame follows where Sammy sits, captions keep off his face
    sW, sH = _probe(SRC)
    try:
        import face as facemod
        ft = facemod.track(SRC)
    except Exception as e:                       # no detector: old centred crop, old caption spot
        print(f"   face check skipped: {e}")
        ft = {"samples": []}
    smp = ft["samples"]
    ar = W / H
    cW = min(sW, round(sH * ar)); cH = min(sH, round(sW / ar)); cW -= cW % 2; cH -= cH % 2
    if smp:
        fcx = sorted((b[0] + b[2]) / 2 for _, b in smp)[len(smp) // 2]
        fcy = sorted((b[1] + b[3]) / 2 for _, b in smp)[len(smp) // 2]
    else:
        fcx, fcy = sW / 2, sH / 2
    cx0 = int(min(max(fcx - cW / 2, 0), sW - cW)); cy0 = int(min(max(fcy - cH * 0.42, 0), sH - cH))
    cx0 -= cx0 % 2; cy0 -= cy0 % 2
    sx, sy = W / cW, H / cH
    zones = [(t, tuple(v for v in ((z[0] - cx0) * sx, (z[1] - cy0) * sy, (z[2] - cx0) * sx, (z[3] - cy0) * sy)))
             for t, z in ((t, facemod.zone(b)) for t, b in smp)] if smp else []

    def face_at(a, b):
        near = [z for t, z in zones if a - 0.6 <= t <= b + 0.6]
        if not near and zones:
            near = [min(zones, key=lambda tz: abs(tz[0] - (a + b) / 2))[1]]
        if not near:
            return None
        return (min(z[0] for z in near), min(z[1] for z in near), max(z[2] for z in near), max(z[3] for z in near))

    # captions: same look, but each line goes where it covers neither the face nor the lower third / bug
    caps = json.load(open(CAPS))
    box_l, box_r = S["left"], W - S["right"]; cxc = (box_l + box_r) // 2; maxw = box_r - box_l
    bottom_edge = H - S["bottom"] - int(10 * k); gap = int(14 * k)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    def wrap(text, font, padx):
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if d0.textlength(t, font=font) <= maxw - 2*padx: cur = t
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines
    def spots(pw, ph, fz):
        x0 = cxc - pw // 2; yield (x0, bottom_edge - ph, x0 + pw, bottom_edge)           # the usual spot
        if fz:
            y0 = int(fz[3]) + gap
            if y0 + ph <= bottom_edge: yield (x0, y0, x0 + pw, y0 + ph)
            y1 = int(fz[1]) - gap
            if y1 - ph >= S["top"]: yield (x0, y1 - ph, x0 + pw, y1)                      # above the head
            yield (x0, S["top"] + gap, x0 + pw, S["top"] + gap + ph)
            lim = H - int(S["bottom"] * 0.55)                                               # last resort: low
            if y0 + ph <= lim: yield (x0, y0, x0 + pw, y0 + ph)
    base_size = 58 if RATIO == "9x16" else int(54 * k)
    capmeta, moved = [], 0
    for i, c in enumerate(caps):
        fz = face_at(c["start"], c["end"])
        obst = [r for r, a, b in OBST if a < c["end"] and b > c["start"]]
        best = None
        for scale in (1.0, 0.86, 0.74):
            fsize = int(base_size * scale); font = ImageFont.truetype(fontb, fsize)
            padx = int(40*k*scale); pady = int(22*k*scale); lh_ = int(fsize*1.18)
            lines = wrap(c["text"], font, padx); tw = max(d0.textlength(ln, font=font) for ln in lines)
            pw = int(tw) + 2*padx; ph = lh_*len(lines) + 2*pady
            for r in spots(pw, ph, fz):
                cost = (_area(r, fz) if fz else 0) * 1000 + sum(_area(r, o) for o in obst)
                if best is None or cost < best[0]:
                    best = (cost, r, font, lines, padx, pady, lh_, scale)
                if cost == 0: break
            if best[0] == 0: break
        cost, (x0, y0, x1, y1), font, lines, padx, pady, lh_, scale = best
        if (x0, y1) != (cxc - (x1 - x0) // 2, bottom_edge) or scale < 1: moved += 1
        if cost >= 1000: print(f"   warning: caption {i} still touches the face ({c['text'][:30]})")
        img = Image.new("RGBA", (x1 - x0, y1 - y0), (0,0,0,0)); d = ImageDraw.Draw(img); w_, h_ = img.size
        d.rounded_rectangle([0, 0, w_ - 1, h_ - 1], radius=int(20*k*scale), fill=(25,67,36,222))
        d.rounded_rectangle([w_//2-int(30*k),h_-int(12*k),w_//2+int(30*k),h_-int(8*k)], radius=2, fill=(206,158,39,255))
        yy = pady
        for ln in lines:
            tl = d.textlength(ln, font=font); d.text((w_/2 - tl/2, yy), ln, font=font, fill=(249,246,241,255)); yy += lh_
        pth = f"{tmp}/cap{i}.png"; img.save(pth)
        capmeta.append({"file": pth, "start": c["start"], "end": c["end"], "x": x0, "y": y0})
    print(f"   captions: {len(caps)} lines, {moved} moved off the face" if smp else f"   captions: {len(caps)} lines (no face found, usual spot)")

    # open + close cards: smiling still, big hook, play button (opener.py)
    cards = None
    if intro or outro:
        import opener
        if texts is None:
            texts = opener.texts_from(captions=caps)
        cover = cover if cover else os.path.splitext(OUT)[0] + "_cover.png"
        cards = opener.build(RATIO, W, H, texts, os.path.join(tmp, "cards"), cover_png=cover if intro else None)
    OH = cards["open_hold"] if (cards and intro) else 0.0
    CL = cards["close_len"] if (cards and outro) else 0.0

    vf = f"crop={cW}:{cH}:{cx0}:{cy0},scale={W}:{H},setsar=1,fps=30"
    dmain = _dur(SRC); total = OH + dmain + CL
    inp = ["-i", SRC, "-i", f"{tmp}/lt.png", "-i", f"{tmp}/bug.png"] + sum([["-i", c["file"]] for c in capmeta], [])
    fc = [f"[0:v]{vf}[base];",
          f"[2:v]format=rgba[bug];[base][bug]overlay={bx}:{by}:enable='{'gte(t,6.3)' if RATIO != '16x9' else 'gte(t,0)'}'[v0];",
          f"[1:v]format=rgba[lt];[v0][lt]overlay={lx - pad}:{ly - pad}:enable='between(t,0.4,6.1)'[vb];"]
    cur = "vb"
    for i, c in enumerate(capmeta):
        fc.append(f"[{3+i}:v]format=rgba[p{i}];[{cur}][p{i}]overlay={c['x']}:{c['y']}:enable='between(t,{c['start']},{c['end']})'[vc{i}];"); cur = f"vc{i}"
    nxt = 3 + len(capmeta)
    tail = []
    if not intro: tail.append("fade=t=in:st=0:d=0.15")
    if not outro: tail.append(f"fade=t=out:st={dmain-0.30:.2f}:d=0.30")
    if OH or CL: tail.append(f"tpad=start_duration={OH:.3f}:start_mode=clone:stop_duration={CL:.3f}:stop_mode=clone")
    fc.append(f"[{cur}]{','.join(tail) or 'null'}[vm];"); cur = "vm"
    amix = [f"[0:a]aresample=48000{f',adelay={int(OH*1000)}:all=1' if OH else ''},apad=whole_dur={total:.3f}[am];"]; ain = ["[am]"]
    if cards and intro:
        inp += ["-i", cards["open"]]
        fc.append(f"[{nxt}:v]format=rgba[op];[{cur}][op]overlay=0:0:eof_action=pass[vo];"); cur = "vo"; nxt += 1
        amix.append(f"aevalsrc=exprs='0.16*sin(2*PI*1700*t)*exp(-90*t)+0.10*sin(2*PI*820*t)*exp(-45*t)':s=48000:d=0.14,"
                    f"adelay={int(cards['tap_at']*1000)}:all=1[tap];"); ain.append("[tap]")
    if cards and outro:
        inp += ["-i", cards["close"]]
        fc.append(f"[{nxt}:v]format=rgba,setpts=PTS+{OH + dmain:.3f}/TB[cl];[{cur}][cl]overlay=0:0:eof_action=repeat[vx];")
        cur = "vx"; nxt += 1
        amix.append(f"aevalsrc=exprs='0.14*sin(2*PI*(420+1300*t)*t)*exp(-26*t)':s=48000:d=0.22,"
                    f"adelay={int((OH + dmain + cards['pop_at'])*1000)}:all=1[pop];"); ain.append("[pop]")
    fc.append(f"[{cur}]format=yuv420p[vout];")
    fc += amix
    fc.append(f"{''.join(ain)}amix=inputs={len(ain)}:normalize=0:duration=first[aout]" if len(ain) > 1 else "[am]anull[aout]")
    subprocess.check_call(["ffmpeg","-hide_banner","-loglevel","error","-y",*inp,"-filter_complex","".join(fc),
                           "-map","[vout]","-map","[aout]","-t",f"{total:.3f}",*ENC,OUT])
    return OUT


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print("wrote", sys.argv[4])
