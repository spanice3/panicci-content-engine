#!/usr/bin/env python3
"""Jiu-jitsu gym owner video ads, v2 (Brian's review, Nov 6 2026). Face on camera the whole time.

  python3 bjj_gjjw_v2.py --cut main --take clean_take3.mp4 --words take3.words.json --assets <dir> --out-dir out
  python3 bjj_gjjw_v2.py --cut 20s  --take clean_take1.mp4 --words take1.words.json --assets <dir> --out-dir out

What changed from v1 (bjj_gjjw_ads.py), per Brian:
  - Sammy's face stays on screen start to finish. No full-screen slides and no end card.
  - One title sits above his head for the whole video: "Jiu-jitsu gym owners: get to the top of Google."
  - Proof pops up as small cards just above his head, on the line it backs up: the real Google Maps result,
    the 39-spot scan, the reviews, +42% searches, then Sammy's own ChatGPT / Perplexity / DeepSeek recordings.
  - "Five miles around the gym" is cut out of the read. "Visibility" is never clipped.

The Nov 6 retakes are 16:9 webcam frames with little headroom, so the 9:16 build is a brand-ink header (title)
over a 4:5 window of the camera, and the cards sit across the seam, right above the cap.

Sources for every number: the bjj-visibility entry in presets/talking-heads.json (refreshed Nov 11 2026) and
panicciventures social/ads-oct26/bjj-visible/video-script.md. Every card footnote names its tool and date. --assets holds
crop-chatgpt.png, crop-perplexity.png, crop-deepseek.png (video/ads/bjj-gjjw/) and gjjw-map-pack.webp
(panicciventures repo root: unedited Google Maps screenshot, "kids jiu-jitsu", Warwick RI, Oct 12 2026).

Normalize a raw studio take first (its MP4 is VFR):
  ffmpeg -i take.mp4 -vf fps=30,format=yuv420p -c:v libx264 -crf 15 -g 15 -c:a aac -b:a 192k clean.mp4
"""
import argparse, json, os, subprocess
import numpy as np
from PIL import Image, ImageDraw

import bjj_gjjw_ads as v1
from bjj_gjjw_ads import run, font, wrap, plan, timeline, caption_png, INK, CREAM, GOLD, WHITE, ENC

# canvas, Meta's UI zones, the camera window (box) and where proof cards go (zone, above the head)
LAYOUT = {
    "9x16": dict(W=1080, H=1920, top=250, bottom=480, side=72, box=(0, 570, 1080, 1350), zone=(430, 830)),
    "4x5":  dict(W=1080, H=1350, top=56, bottom=110, side=64, box=(0, 250, 1080, 1100), zone=(236, 520)),
}

# Per take: the 4:5-ish camera crop centred on Sammy's face (source px), for each canvas.
CROP = {
    "main": {"9x16": (563, 0, 864, 1080), "4x5": (450, 0, 1090, 1080)},   # 12:11 take 3: framed tight
    "20s":  {"9x16": (650, 216, 691, 864), "4x5": (560, 216, 870, 864)},  # 12:17 take 1: framed wider, zoom in
}

# word-index ranges (inclusive) per beat; a gap between ranges is cut out of the read
CUTS = {
    "main": dict(blocks=[("hook", 0, 11), ("problem", 12, 38), ("map", 39, 53), ("scan", 59, 71),
                         ("reviews", 72, 88), ("growth", 89, 99), ("ai", 100, 117), ("offer", 118, 145),
                         ("cta", 146, 154)],
                 fix={53: "map.", 73: "a rival"}),       # drop "five miles around their gym." (54-58)
    "20s": dict(blocks=[("hook", 154, 165), ("map", 166, 181), ("scan", 182, 186), ("reviews", 187, 195),
                        ("offer", 196, 205), ("cta", 206, 208)],
                fix={}),
}
ZOOM = {"hook", "problem", "offer", "cta"}   # punch in on the talking beats, wide when a card is up


def let_words_land(take, segs, words, floor=0.012, cap=0.6):
    """Whisper ends a word early (it heard "visibility" stop ~0.2 s before the sound did, which is the clip Brian
    caught). Push every cut that ends on a pause out until the audio actually goes quiet, never into the next word."""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", take, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.float32); hop = 160                     # 10 ms frames
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))[::hop]
    starts = sorted(w[0] for w in words)
    out = []
    for i, (s, e, bi, cam) in enumerate(segs):
        nxt_seg = segs[i + 1][0] if i + 1 < len(segs) else None
        if nxt_seg is not None and nxt_seg - e < 0.05:                   # joined to the next stretch: leave it
            out.append((s, e, bi, cam)); continue
        nxt_word = next((t for t in starts if t > e + 0.01), e + cap)
        limit = min(e + cap, nxt_word - 0.03, nxt_seg - 0.01 if nxt_seg is not None else e + cap)
        t = e
        while t < limit and int(t * 100) < len(rms) and rms[int(t * 100)] > floor:
            t += 0.01
        out.append((s, max(e, min(limit, t + 0.06)), bi, cam))
    return out


def card_img(kind, assets, k=1.0):
    """One proof card (RGBA), sized for the card zone. Ink ground, gold kicker, cream footnote."""
    pad, maxw = round(26 * k), round(936 * k)
    fk, fn = font("Bold", 30 * k), font("Regular", 20 * k)

    def frame(body, kicker, foot):
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        kl = wrap(tmp, kicker, fk, maxw - 2 * pad)
        w = max(body.width, max(tmp.textlength(l, font=fk) for l in kl), tmp.textlength(foot, font=fn)) + 2 * pad
        h = pad + len(kl) * round(38 * k) + round(12 * k) + body.height + round(14 * k) + round(26 * k) + pad
        img = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=round(24 * k), fill=INK + (242,),
                            outline=GOLD + (255,), width=max(2, round(3 * k)))
        y = pad
        for l in kl:
            d.text((pad, y), l, font=fk, fill=GOLD + (255,)); y += round(38 * k)
        y += round(12 * k)
        x = (img.width - body.width) // 2
        img.alpha_composite(body, (x, y)); y += body.height + round(14 * k)
        d.text((pad, y), foot, font=fn, fill=CREAM + (170,))
        return img

    def shot(path, keep=None, boxes=(), maxh=230):
        im = Image.open(path).convert("RGB")
        if keep: im = im.crop(keep)
        hd = ImageDraw.Draw(im)
        for bx in boxes:
            hd.rounded_rectangle(bx, radius=10, outline=GOLD, width=6)
        s = min((maxw - 2 * pad) / im.width, maxh * k / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS).convert("RGBA")
        m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, *im.size), radius=round(14 * k), fill=255)
        im.putalpha(m)
        return im

    def stat(big, label, bigsize=150):
        fb, fl = font("Bold", bigsize * k), font("SemiBold", 40 * k)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        bw = tmp.textlength(big, font=fb)
        ll = wrap(tmp, label, fl, maxw - 2 * pad - bw - 30 * k)
        w = round(bw + 30 * k + max(tmp.textlength(l, font=fl) for l in ll))
        h = round(max(bigsize * 0.86, len(ll) * 48) * k)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.text((0, -bigsize * 0.2 * k), big, font=fb, fill=GOLD + (255,))
        y = (h - len(ll) * 48 * k) / 2
        for l in ll:
            d.text((bw + 30 * k, y), l, font=fl, fill=WHITE + (255,)); y += 48 * k
        return im

    A = lambda f: os.path.join(assets, f)
    if kind == "map":
        return frame(shot(A("gjjw-map-pack.webp"), keep=(0, 0, 800, 372), boxes=[(22, 104, 778, 360)]),
                     "#1 on Google Maps · “kids jiu-jitsu”", "Unedited Google Maps screenshot · Warwick, RI · Oct 12, 2026")
    if kind == "scan":
        return frame(stat("39/39", "map spots ranking #1 for “kids jiu-jitsu”", 120), "Gracie Jiu-Jitsu Warwick",
                     "Search Atlas map scan · 39 spots, 5 mi · Nov 9, 2026")
    if kind == "reviews":
        return frame(stat("#1", "on 117 reviews vs. a rival’s 132"), "Fewer reviews. Still #1.",
                     "Google review counts · Search Atlas map scan · Nov 2, 2026")
    if kind == "growth":
        return frame(stat("+42%", "more Google searches showed their gym’s profile"), "Since August",
                     "Search Atlas GBP search appearances · 1,578 → 2,238 · 60 days to Aug 18 vs. Nov 7")
    tool, f, keep, boxes = {
        "ai0": ("ChatGPT", "crop-chatgpt.png", (20, 520, 760, 715), [(10, 78, 398, 128)]),
        "ai1": ("Perplexity", "crop-perplexity.png", None, [(196, 154, 510, 196)]),
        "ai2": ("DeepSeek", "crop-deepseek.png", None, [(12, 80, 580, 118)]),
    }[kind]
    return frame(shot(A(f), keep, boxes), f"Ask {tool}: best kids self-defense near Warwick, RI",
                 "Screen recording Nov 3 · #1 in Search Atlas AI tracking, 30 days to Nov 11")


def place(card, lay, path, scale=1.0, alpha=1.0):
    """Full-canvas PNG with the card centred in the zone (scaled/faded for the pop-in frames)."""
    W, H = lay["W"], lay["H"]; z0, z1 = lay["zone"]
    c = card
    if scale != 1.0:
        c = card.resize((max(1, round(card.width * scale)), max(1, round(card.height * scale))), Image.LANCZOS)
    if alpha < 1.0:
        a = c.getchannel("A").point(lambda v: round(v * alpha)); c = c.copy(); c.putalpha(a)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(c, ((W - c.width) // 2, max(z0, z1 - c.height - (card.height - c.height) // 2)))
    img.save(path); return path


def header(lay, path):
    """Ink band over the top of the frame, Panicci dot texture, the title, and a soft fade into the camera."""
    W, H = lay["W"], lay["H"]; bx, by, bw, bh = lay["box"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, by), fill=INK + (255,))
    for y in range(11, by, 22):
        for x in range(11, W, 22):
            d.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=(246, 241, 232, 18))
    fade = 140
    for i in range(fade):
        d.line((0, by + i, W, by + i), fill=INK + (round(235 * (1 - i / fade) ** 1.6),))
    k = 1.0 if H > 1500 else 0.8
    y = lay["top"] + 18 * k
    fk, ft = font("Bold", 34 * k), font("Bold", 74 * k)
    d.text((lay["side"], y), "JIU-JITSU GYM OWNERS", font=fk, fill=GOLD + (255,))
    y += 48 * k
    for l in wrap(d, "Get to the top of Google.", ft, W - 2 * lay["side"]):
        d.text((lay["side"], y), l, font=ft, fill=WHITE + (255,)); y += 80 * k
    img.save(path); return path


def cut(take, segs, blocks, lay, crop, tmp):
    """One ffmpeg pass: each kept stretch cropped to the face window (tighter on talking beats), scaled into the
    camera box on an ink canvas; audio from the take with tiny fades at every join."""
    W, H = lay["W"], lay["H"]; bx, by, bw, bh = lay["box"]
    n = len(segs)
    fc = [f"[0:a]asplit={n}" + "".join(f"[sa{i}]" for i in range(n)),
          f"[0:v]split={n}" + "".join(f"[sv{i}]" for i in range(n))]
    labels = ""
    for i, (s, e, bi, _) in enumerate(segs):
        x0, y0, cw, ch = crop
        if blocks[bi][0] in ZOOM:
            z = 1.1; nw, nh = round(cw / z / 2) * 2, round(ch / z / 2) * 2
            x0, y0, cw, ch = x0 + (cw - nw) // 2, y0 + round((ch - nh) * 0.35), nw, nh
        d = e - s
        fc.append(f"[sv{i}]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS,crop={cw}:{ch}:{x0}:{y0},"
                  f"scale={bw}:{bh}:flags=lanczos,pad={W}:{H}:{bx}:{by}:color=0x0d1210,setsar=1,format=yuv420p[v{i}]")
        fc.append(f"[sa{i}]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.012,afade=t=out:st={max(0, d - 0.02):.3f}:d=0.02[a{i}]")
        labels += f"[v{i}][a{i}]"
    fc.append(f"{labels}concat=n={n}:v=1:a=1[v][a]")
    out = f"{tmp}/cut.mp4"
    run("-i", take, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", *ENC, out)
    return out


def caption_chunks(words, segs, O, fix):
    """Captions from the kept words, in house style: jiu-jitsu lowercase unless it starts a line or names GJJW."""
    toks = []
    for i, (s, e, w) in enumerate(words):
        if not any(a - 1e-3 <= s and e <= b + 1e-3 for a, b, _, _ in segs):
            continue
        s, e, w = O(s), O(e), fix.get(i, w)
        if toks and (w.startswith("-") or w == "%" or w.startswith("%")):
            toks[-1] = (toks[-1][0], e, toks[-1][2] + w); continue
        toks.append((s, e, w))
    out = []
    for j, (s, e, w) in enumerate(toks):
        core, tail = w.rstrip(".,?!"), w[len(w.rstrip(".,?!")):]
        low = core.lower()
        if low == "jiu-jitsu":
            prev = out[-1][2] if out else ""
            core = "Jiu-Jitsu" if prev == "Gracie" else ("Jiu-jitsu" if not prev or prev.endswith((".", "?", "!")) else "jiu-jitsu")
        elif low in ("kids", "gym", "best", "self-defense", "program", "below"):
            core = low
        out.append((s, e, core + tail))
    caps, cur = [], []
    for t in out:
        cur.append(t)
        if t[2].endswith((".", ",", "?", "!")) or len(cur) >= 4:
            caps.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(x[2] for x in cur)}); cur = []
    if cur:
        caps.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(x[2] for x in cur)})
    for i in range(len(caps) - 1):
        caps[i]["end"] = min(caps[i]["end"] + 0.25, caps[i + 1]["start"] - 0.02)
    caps[-1]["end"] += 0.25
    return caps


def compose(base, dur, overlays, out):
    """Every overlay flattened per interval into one ffconcat PNG track (one overlay filter for the whole video)."""
    fps = 30
    q = lambda t: round(round(t * fps) / fps, 4)
    ev = [(png, q(max(0, s)), q(min(dur, e))) for png, s, e in overlays if e > s]
    cuts = sorted({0.0, q(dur), *[s for _, s, _ in ev], *[e for _, _, e in ev]})
    W, H = Image.open(ev[0][0]).size
    odir = out + ".ov"; os.makedirs(odir, exist_ok=True)
    lines, cache = ["ffconcat version 1.0"], {}
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        if b - a <= 0: continue
        active = tuple(png for png, s, e in ev if s <= a and e >= b)
        if active not in cache:
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for png in active:
                img.alpha_composite(Image.open(png).convert("RGBA"))
            cache[active] = f"{odir}/f{len(cache):03d}.png"; img.save(cache[active])
        lines += [f"file '{cache[active]}'", f"duration {b - a:.4f}"]
    lines.append(lines[-2])
    lst = f"{odir}/ov.ffconcat"; open(lst, "w").write("\n".join(lines) + "\n")
    run("-i", base, "-f", "concat", "-safe", "0", "-i", lst,
        "-filter_complex", f"[1:v]fps={fps},format=rgba[o];[0:v][o]overlay=0:0:eof_action=pass:format=auto[v]",
        "-map", "[v]", "-map", "0:a", "-t", f"{dur:.3f}", *ENC, out)


def build(name, take, words, assets, ratio, outdir):
    lay = LAYOUT[ratio]; spec = CUTS[name]; blocks = spec["blocks"]
    tmp = os.path.join(outdir, f".tmp_{name}_{ratio}"); os.makedirs(tmp, exist_ok=True)
    segs = let_words_land(take, plan(words, blocks, vend=10 ** 6), words)
    O, dur = timeline(segs)
    base = cut(take, segs, blocks, lay, CROP[name][ratio], tmp)
    blk = {n: (a, b) for n, a, b in blocks}
    st = lambda i: O(words[i][0])
    k = 1.0 if lay["H"] > 1500 else 0.74
    ov = [(header(lay, f"{tmp}/header.png"), 0, dur)]

    def pop(kind, t0, t1):
        card = card_img(kind, assets, k)
        f = 1 / 30
        ov.extend([(place(card, lay, f"{tmp}/{kind}_p1.png", 0.86, 0.35), t0, t0 + f),
                   (place(card, lay, f"{tmp}/{kind}_p2.png", 0.95, 0.8), t0 + f, t0 + 2 * f),
                   (place(card, lay, f"{tmp}/{kind}.png"), t0 + 2 * f, t1)])

    nxt = lambda name_: st(blocks[[b[0] for b in blocks].index(name_) + 1][1])
    for kind in ("map", "scan", "reviews", "growth"):
        if kind in blk:
            pop(kind, st(blk[kind][0]), nxt(kind) - 0.05)
    if "ai" in blk:
        a, b = blk["ai"]; s0, s1 = st(a), nxt("ai") - 0.05; step = (s1 - s0) / 3
        for i in range(3):
            pop(f"ai{i}", s0 + i * step, s0 + (i + 1) * step)
    for i, c in enumerate(caption_chunks(words, segs, O, spec["fix"])):
        p = f"{tmp}/cap{i:02d}.png"; caption_png(c["text"], lay, p); ov.append((p, c["start"], c["end"]))
    out = os.path.join(outdir, f"panicci-bjj-gjjw-v2_{name}_{ratio}.mp4")
    compose(base, dur, ov, out)
    print(f"{out}: {dur:.1f}s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", required=True, choices=list(CUTS)); ap.add_argument("--take", required=True)
    ap.add_argument("--words", required=True); ap.add_argument("--assets", required=True)
    ap.add_argument("--out-dir", default="out"); ap.add_argument("--ratios", default="9x16,4x5")
    a = ap.parse_args(); os.makedirs(a.out_dir, exist_ok=True)
    words = [tuple(w) for w in json.load(open(a.words))]
    for r in a.ratios.split(","):
        build(a.cut, a.take, words, a.assets, r, a.out_dir)
