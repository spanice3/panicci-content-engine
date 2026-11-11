#!/usr/bin/env python3
"""Jiu-jitsu gym owner video ads (GJJW proof), Nov 3 2026. One studio take in, Meta video ads out.

  python3 bjj_gjjw_ads.py --take take4_clean.mp4 --words take4.words.json --broll <dir with crop-*.png> --out-dir out

The take is Sammy's studio read of panicciventures social/ads-oct26/bjj-visible/video-script.md: the main cut, then
the 20-second cut. `--words` is captions.asr_words() output for that take: [start, end, word].

Normalize the raw take first (the studio's MP4 is VFR):
  ffmpeg -i take4.mp4 -vf fps=30,format=yuv420p -c:v libx264 -crf 15 -g 15 -c:a aac -b:a 192k take4_clean.mp4

The Nov 3 takes only carry ~12.5 s of video (the studio recorder dropped the video track; the audio runs the full
length), so the build is "hook on camera, then Sammy's voice over full-screen proof". `--video-end` (default: the
take's video stream length) is where the camera stops; everything after it is a designed scene. When a take has full
video, the same blocks stay on camera and the proof shows as top cards instead.

Every number is real and dated (sources: panicciventures social/ads-oct26/README.md, BJJ section). The AI montage is
Sammy's own screen recording (ChatGPT, Perplexity, DeepSeek, Nov 3 2026), cropped to the answer column so no chat
history shows. Cuts follow Whisper word timings and trim pauses over 0.45 s.
"""
import argparse, json, os, re, subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, ".build")
F = {k: os.path.join(B, f"PVSG{k}.ttf") for k in ("Bold", "SemiBold", "Medium", "Regular")}
INK = (13, 18, 16); CREAM = (246, 241, 232); GOLD = (242, 193, 78); DEEP = (25, 67, 36); WHITE = (255, 255, 255)
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "1", "-movflags", "+faststart"]
LAYOUT = {  # Meta Reels/Stories UI covers roughly the top 250 px and bottom 480 px of a 9:16 frame
    "9x16": dict(W=1080, H=1920, top=250, bottom=480, side=72, src_y=None),
    "4x5":  dict(W=1080, H=1350, top=60, bottom=96, side=64, src_y=300),
}
FINE = ("Guarantee: 30% more qualified traffic (non-branded Google clicks + AI-assistant visits) in 90 days "
        "vs. the 90 days before, on retainers, or we keep working free. Terms apply.")

# ---- the edit: word-index ranges in take 4 (inclusive), one block per script beat ----
MAIN = [("hook", 0, 11), ("problem", 12, 38), ("map", 39, 71), ("reviews", 73, 89),
        ("growth", 90, 118), ("offer", 119, 146), ("cta", 147, 155)]
# 20 s: the on-camera hook from the main read, then the short read as voice-over
SHORT = [("hook", 0, 11), ("map", 168, 188), ("reviews", 189, 197), ("offer", 198, 207), ("cta", 208, 210)]
FIX = {"hour,": "their"}  # ASR heard "130 to their 116" as "to hour"
FIX_IDX = {194: "gym"}     # "than the gym they're up against" (ASR put a comma after gym)


def run(*a):
    subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a])


def font(k, s):
    return ImageFont.truetype(F[k], max(8, round(s)))


def video_len(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                          "stream=duration", "-of", "csv=p=0", path]).decode().strip())


# ---------------------------------------------------------------- cutting
def plan(words, blocks, vend, gap=0.45, pre=0.07, post=0.12):
    """(src_start, src_end, block_index, on_camera) split at pauses > gap and at the end of the video."""
    segs = []
    for bi, (_, a, b) in enumerate(blocks):
        run_a = a
        for i in range(a, b + 1):
            last = i == b
            if last or words[i + 1][0] - words[i][1] > gap:
                s, e = max(0, words[run_a][0] - pre), words[i][1] + post
                if not last:
                    e = min(e, words[i + 1][0] - 0.02)
                if segs and s < segs[-1][1] and segs[-1][2] == bi:
                    s = segs[-1][1]
                if s < vend < e:
                    segs += [(s, vend, bi, True), (vend, e, bi, False)]
                else:
                    segs.append((s, e, bi, e <= vend + 1e-3))
                run_a = i + 1
    return segs


def cut(take, segs, lay, ratio, tmp):
    """One ffmpeg pass: trim camera segments (punch in 12% on every other block), ink frames where the camera is
    gone, audio from the take throughout, concat in the graph."""
    W, H = lay["W"], lay["H"]
    n, cams = len(segs), [k for k, s in enumerate(segs) if s[3]]
    fc = ["[0:a]asplit=" + str(n) + "".join(f"[sa{k}]" for k in range(n))]
    if cams:
        fc.append(f"[0:v]split={len(cams)}" + "".join(f"[sv{k}]" for k in cams))
    labels = ""
    for k, (s, e, bi, cam) in enumerate(segs):
        d = e - s
        if cam:
            z = 1.12 if bi % 2 else 1.0
            cw, ch = round(1080 / z) // 2 * 2, round(1920 / z) // 2 * 2
            cx, cy = min(1080 - cw, max(0, 740 - cw // 2)), (1920 - ch) // 2   # face sits right of center
            vf = f"crop={cw}:{ch}:{cx}:{cy},scale=1080:1920"
            if ratio == "4x5":
                vf += f",crop=1080:1350:0:{lay['src_y']}"
            fc.append(f"[sv{k}]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS,{vf},setsar=1,format=yuv420p[v{k}]")
        else:
            fc.append(f"color=c=0x0d1210:s={W}x{H}:r=30:d={d:.3f},setsar=1,format=yuv420p[v{k}]")
        fc.append(f"[sa{k}]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.012,afade=t=out:st={max(0, d - 0.02):.3f}:d=0.02[a{k}]")
        labels += f"[v{k}][a{k}]"
    fc.append(f"{labels}concat=n={n}:v=1:a=1[v][a]")
    out = f"{tmp}/cut.mp4"
    run("-i", take, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", *ENC, out)
    return out


def timeline(segs):
    """Map a source time to the output timeline (a time inside a trimmed gap snaps to the next kept frame)."""
    def O(t):
        acc = 0.0
        for s, e, _, _ in segs:
            if t < s:
                return round(acc, 3)
            if t <= e:
                return round(acc + t - s, 3)
            acc += e - s
        return round(acc, 3)
    return O, sum(e - s for s, e, _, _ in segs)


# ---------------------------------------------------------------- captions
def caption_chunks(words, segs, O):
    toks = []
    for i, (s, e, w) in enumerate(words):
        if not any(a - 1e-3 <= s and e <= b + 1e-3 for a, b, _, _ in segs):
            continue
        s, e, w = O(s), O(e), FIX_IDX.get(i, FIX.get(w, w))
        if toks and (w.startswith("-") or w == "%"):        # Jiu -Jitsu, self -defense, 46 %
            toks[-1] = (toks[-1][0], e, toks[-1][2] + w); continue
        w = {"Kids": "kids", "Gym": "gym", "Owners,": "owners,"}.get(w, w)
        toks.append((s, e, w))
    caps, cur = [], []
    for t in toks:
        cur.append(t)
        if t[2].endswith((".", ",", "?", "!")) or len(cur) >= 4:
            caps.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(x[2] for x in cur)}); cur = []
    if cur:
        caps.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(x[2] for x in cur)})
    for i in range(len(caps) - 1):
        caps[i]["end"] = min(caps[i]["end"] + 0.25, caps[i + 1]["start"] - 0.02)
    return caps


def caption_png(text, lay, path):
    W, H = lay["W"], lay["H"]
    f = font("Bold", 58)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    lines = wrap(d, text, f, W - 2 * lay["side"] - 120)
    lh, padx, pady = 68, 36, 20
    tw = max(d.textlength(l, font=f) for l in lines)
    y1 = H - lay["bottom"] - 10; y0 = y1 - lh * len(lines) - 2 * pady
    d.rounded_rectangle([(W - tw) / 2 - padx, y0, (W + tw) / 2 + padx, y1], radius=20, fill=DEEP + (232,))
    d.rounded_rectangle([W / 2 - 30, y1 - 12, W / 2 + 30, y1 - 8], radius=2, fill=GOLD + (255,))
    y = y0 + pady - 4
    for l in lines:
        d.text(((W - d.textlength(l, font=f)) / 2, y), l, font=f, fill=CREAM + (255,)); y += lh
    img.save(path)


# ---------------------------------------------------------------- scenes
def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


class Scene:
    """Full-frame proof scene: ink ground, faint dot texture (Panicci signature), brand line, then stacked type."""
    def __init__(self, lay):
        self.lay = lay; W, H = lay["W"], lay["H"]
        self.k = 1.0 if H > 1500 else 0.82
        self.img = Image.new("RGBA", (W, H), INK + (255,))
        dots = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(dots)
        for y in range(11, H, 22):
            for x in range(11, W, 22):
                g.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=(246, 241, 232, 16))
        self.img.alpha_composite(dots)    # blend, so the ground stays opaque
        g = ImageDraw.Draw(self.img)
        self.c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.c)
        self.x = lay["side"]; self.maxw = W - 2 * lay["side"]
        top = lay["top"] + 34 * self.k
        mark = Image.open(os.path.join(B, "mark_cream.png")).convert("RGBA").resize((round(46 * self.k),) * 2)
        self.img.alpha_composite(mark, (self.x, round(top)))
        g.text((self.x + 62 * self.k, top + 9 * self.k), "P A N I C C I   V E N T U R E S",
               font=font("SemiBold", 22 * self.k), fill=CREAM + (220,))
        self.y0 = self.y = top + 120 * self.k
        self.y1 = H - lay["bottom"] - 190 * self.k      # caption zone starts here

    def text(self, s, kind="Bold", size=60, fill=WHITE, gap=0, lh=1.08, alpha=255):
        f = font(kind, size * self.k)
        for l in wrap(self.d, s, f, self.maxw):
            self.d.text((self.x, self.y), l, font=f, fill=fill + (alpha,)); self.y += size * self.k * lh
        self.y += gap * self.k
        return self

    def kicker(self, s, gap=18):
        return self.text(s.upper(), "Bold", 28, GOLD, gap=gap)

    def rule(self, gap=28):
        self.d.rectangle((self.x, self.y, self.x + 120 * self.k, self.y + 5 * self.k), fill=GOLD + (255,))
        self.y += (5 + gap) * self.k
        return self

    def space(self, px):
        self.y += px * self.k; return self

    def save(self, path):
        off = max(0, round((self.y1 - self.y0 - (self.y - self.y0)) / 2))
        self.img.alpha_composite(self.c, (0, off)); self.img.save(path); return path


def hook_callout(lay, path):
    W, H = lay["W"], lay["H"]; img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f = font("Bold", 46); text = "JIU-JITSU GYM OWNERS"; tw = d.textlength(text, font=f)
    x0, y0 = lay["side"], lay["top"] + 16
    d.rounded_rectangle((x0, y0, x0 + tw + 56, y0 + 84), radius=12, fill=GOLD + (255,))
    d.text((x0 + 28, y0 + 14), text, font=f, fill=INK + (255,))
    img.save(path)


def end_scene(lay, path):
    S = Scene(lay)
    S.text("Get your gym", size=104, lh=1.0).text("to the top", size=104, lh=1.0).text("of Google.", size=104, gap=46)
    k = S.k; x, y = S.x, S.y; fb = font("Bold", 58 * k); bt = "APPLY BELOW"
    bw = S.d.textlength(bt, font=fb) + 140 * k
    S.d.rounded_rectangle((x, y, x + bw, y + 112 * k), radius=16, fill=GOLD + (255,))
    S.d.text((x + 40 * k, y + 24 * k), bt, font=fb, fill=INK + (255,))
    ax, ay = x + bw - 70 * k, y + 56 * k          # down arrow, pointing at Meta's button
    for seg in ((ax, ay - 24 * k, ax, ay + 22 * k), (ax - 18 * k, ay + 4 * k, ax, ay + 24 * k), (ax + 18 * k, ay + 4 * k, ax, ay + 24 * k)):
        S.d.line(seg, fill=INK + (255,), width=round(8 * k))
    S.y = y + 112 * k + 34 * k
    S.text("See if your gym qualifies for 30% more Google traffic in 90 days, guaranteed.", "SemiBold", 40, CREAM, gap=26, lh=1.25)
    S.text(FINE, "Regular", 22, CREAM, lh=1.35, alpha=150)
    return S.save(path)


# Where Gracie Jiu-Jitsu Warwick sits in each crop (crop pixels): boxed in gold so the eye lands on it.
# The ChatGPT crop is trimmed to the query and the #1 pick so the text stays big enough to read on a phone.
AI_MARK = {"crop-chatgpt.png": dict(keep=(0, 0, 1306, 720), boxes=[(30, 598, 418, 648)]),
           "crop-perplexity.png": dict(keep=None, boxes=[(196, 154, 510, 196)]),
           "crop-deepseek.png": dict(keep=None, boxes=[(12, 80, 580, 118)])}


def ai_panel(lay, path, crop, tool):
    """Sammy's real recording, cropped to the answer column, GJJW boxed in gold (a highlight, nothing altered)."""
    S = Scene(lay)
    S.kicker("Ask the AI tools", gap=4).text(tool, size=84, gap=6)
    S.text("“best child self-defense programs near Warwick RI”", "Medium", 32, CREAM, gap=30, alpha=210)
    shot = Image.open(crop).convert("RGB")
    spec = AI_MARK.get(os.path.basename(crop), dict(keep=None, boxes=[]))
    if spec["keep"]:
        shot = shot.crop(spec["keep"])
    hd = ImageDraw.Draw(shot)
    for bx in spec["boxes"]:
        hd.rounded_rectangle(bx, radius=10, outline=GOLD, width=5)
    maxh = S.y1 - S.y - 60 * S.k
    s = min(S.maxw / shot.width, maxh / shot.height)
    shot = shot.resize((round(shot.width * s), round(shot.height * s)), Image.LANCZOS)
    m = Image.new("L", shot.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, *shot.size), radius=22, fill=255)
    sy = round(S.y)
    S.c.paste(shot, (S.x, sy), m)
    S.d.rounded_rectangle((S.x - 2, sy - 2, S.x + shot.width + 2, sy + shot.height + 2), radius=24, outline=(246, 241, 232, 70), width=2)
    S.y = sy + shot.height + 18
    S.text("Screen recording, Nov 3, 2026", "Regular", 22, CREAM, alpha=140)
    return S.save(path)


def scenes(lay, tmp, broll):
    P = lambda n: f"{tmp}/{n}.png"
    sc = {}
    sc["street"] = (Scene(lay).kicker("When a parent searches “kids jiu‑jitsu”")
                    .text("They pick from the top 3 gyms on the map.", size=92, gap=36)
                    .text("Not there? They sign up down the street.", size=92, fill=GOLD).save(P("s_street")))
    sc["map_a"] = (Scene(lay).kicker("My client").text("Gracie Jiu‑Jitsu Warwick", size=112, lh=1.02, gap=14)
                   .text("Warwick, Rhode Island", "Medium", 44, CREAM).save(P("s_map_a")))
    def map_b():
        S = Scene(lay).kicker("Gracie Jiu‑Jitsu Warwick · Warwick, RI", gap=0)
        S.text("#1", size=330, fill=GOLD, lh=0.98)
        S.text("on Google Maps for", "SemiBold", 56, WHITE, lh=1.1).text("“kids jiu‑jitsu”", size=84, gap=30)
        S.rule().text("All 39 of 39 map pins, 5 miles around the gym.", "SemiBold", 46, CREAM, gap=22, lh=1.2)
        return S.text("Search Atlas map scan, Oct 26, 2026", "Regular", 24, CREAM, alpha=150).save(P("s_map_b"))
    sc["map_b"] = map_b()
    def reviews(still):
        S = Scene(lay).kicker("Same map. More reviews.", gap=26)
        for n, who, a in (("130", "reviews · a rival gym", 120), ("116", "reviews · my client", 255)):
            y = S.y; S.text(n, size=210, fill=CREAM if a < 255 else WHITE, lh=0.95, alpha=a)
            S.d.text((S.x + S.d.textlength(n, font=font("Bold", 210 * S.k)) + 30 * S.k, y + 120 * S.k), who,
                     font=font("SemiBold", 42 * S.k), fill=CREAM + (a,))
            S.space(10)
        if still:
            S.space(24).text("Still #1.", size=150, fill=GOLD, gap=10)
        S.text("Search Atlas map scan, Oct 26, 2026", "Regular", 24, CREAM, alpha=150)
        return S.save(P("s_reviews_b" if still else "s_reviews_a"))
    sc["reviews_a"], sc["reviews_b"] = reviews(False), reviews(True)
    sc["growth"] = (Scene(lay).kicker("Since August").text("+46%", size=300, fill=GOLD, lh=0.98)
                    .text("more Google searches showing their gym", "SemiBold", 64, WHITE, gap=30, lh=1.12).rule()
                    .text("Google Business Profile: 1,444 → 2,106 searches, 60 days to Aug 18 vs. 60 days to Nov 2",
                          "Regular", 24, CREAM, alpha=150, lh=1.35).save(P("s_growth")))
    def offer(more):
        S = Scene(lay).kicker("For your gym").text("30% more Google traffic in 90 days.", size=104, lh=1.02, gap=10)
        S.text("Guaranteed.", size=120, fill=GOLD, gap=34)
        if more:
            S.text("If I don't hit it, I keep working free until you get there.", "SemiBold", 48, CREAM, gap=30, lh=1.2)
        S.text(FINE, "Regular", 22, CREAM, lh=1.35, alpha=150)
        return S.save(P("s_offer_b" if more else "s_offer_a"))
    sc["offer_a"], sc["offer_b"] = offer(False), offer(True)
    sc["end"] = end_scene(lay, P("s_end"))
    sc["ai"] = [ai_panel(lay, P(f"s_ai{k}"), os.path.join(broll, f), tool)
                for k, (tool, f) in enumerate([("ChatGPT", "crop-chatgpt.png"), ("Perplexity", "crop-perplexity.png"),
                                               ("DeepSeek", "crop-deepseek.png")])]
    return sc


# ---------------------------------------------------------------- compose
def compose(base, dur, overlays, out, tail=None):
    """overlays: (png, start, end), stacked in list order (captions last). Flattened into one PNG per interval and
    fed as a single ffconcat track, so the render is one overlay however many captions and scenes there are."""
    fps = 30
    q = lambda t: round(round(t * fps) / fps, 4)
    ev = [(png, q(max(0, s)), q(min(dur, e))) for png, s, e in overlays if e > s]
    cuts = sorted({0.0, q(dur), *[s for _, s, _ in ev], *[e for _, _, e in ev]})
    W, H = Image.open(ev[0][0]).size
    odir = out + ".ov"; os.makedirs(odir, exist_ok=True)
    lines, cache = ["ffconcat version 1.0"], {}
    for k in range(len(cuts) - 1):
        a, b = cuts[k], cuts[k + 1]
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
    body = out + ".body.mp4"
    run("-i", base, "-f", "concat", "-safe", "0", "-i", lst,
        "-filter_complex", f"[1:v]fps={fps},format=rgba[o];[0:v][o]overlay=0:0:eof_action=pass:format=auto[v]",
        "-map", "[v]", "-map", "0:a", "-t", f"{dur:.3f}", *ENC, body)
    png, t = tail
    still = out + ".tail.mp4"
    run("-loop", "1", "-t", str(t), "-i", png, "-f", "lavfi", "-t", str(t), "-i", "anullsrc=r=48000:cl=mono",
        "-vf", "fps=30,format=yuv420p", "-map", "0:v", "-map", "1:a", *ENC, still)
    lst2 = out + ".txt"; open(lst2, "w").write(f"file '{body}'\nfile '{still}'\n")
    run("-f", "concat", "-safe", "0", "-i", lst2, "-c", "copy", out)
    for f in (body, still, lst2): os.remove(f)


def build(name, blocks, words, take, broll, ratio, outdir, vend):
    lay = LAYOUT[ratio]; tmp = os.path.join(outdir, f".tmp_{name}_{ratio}"); os.makedirs(tmp, exist_ok=True)
    segs = plan(words, blocks, vend)
    O, dur = timeline(segs)
    base = cut(take, segs, lay, ratio, tmp)
    sc = scenes(lay, tmp, broll)
    blk = {n: (a, b) for n, a, b in blocks}
    st = lambda i: O(words[i][0]); en = lambda i: O(words[i][1])
    first = lambda a, b, w: next(i for i in range(a, b + 1) if words[i][2].startswith(w))
    cam_end = O(vend)
    ov = []

    a, b = blk["hook"]
    callout = f"{tmp}/callout.png"; hook_callout(lay, callout); ov.append((callout, 0, en(b) + 0.3))
    if "problem" in blk:
        a, b = blk["problem"]
        if cam_end < en(b):
            ov.append((sc["street"], cam_end, st(blk["map"][0])))
    a, b = blk["map"]; i = first(a, b, "We") if any(words[j][2] == "We" for j in range(a, b + 1)) else first(a, b, "number")
    ov += [(sc["map_a"], st(a) if "problem" in blk else en(blk["hook"][1]), st(i)), (sc["map_b"], st(i), st(blk["reviews"][0]))]
    a, b = blk["reviews"]
    nxt = st(blk["growth"][0]) if "growth" in blk else st(blk["offer"][0])
    if "growth" in blk:
        i = first(a, b, "Still")
        ov += [(sc["reviews_a"], st(a), st(i)), (sc["reviews_b"], st(i), nxt)]
    else:
        ov.append((sc["reviews_b"], st(a), nxt))
    if "growth" in blk:
        a, b = blk["growth"]; i = first(a, b, "And")
        ov.append((sc["growth"], st(a), st(i)))
        s0, s1 = st(i), st(blk["offer"][0]); step = (s1 - s0) / 3
        ov += [(p, s0 + k * step, s0 + (k + 1) * step) for k, p in enumerate(sc["ai"])]
    a, b = blk["offer"]
    if "If" in [words[j][2] for j in range(a, b + 1)]:
        i = first(a, b, "If")
        ov += [(sc["offer_a"], st(a), st(i)), (sc["offer_b"], st(i), st(blk["cta"][0]))]
    else:
        ov.append((sc["offer_a"], st(a), st(blk["cta"][0])))
    ov.append((sc["end"], st(blk["cta"][0]), dur))
    for k, c in enumerate(caption_chunks(words, segs, O)):
        p = f"{tmp}/cap{k:02d}.png"; caption_png(c["text"], lay, p); ov.append((p, c["start"], c["end"]))
    out = os.path.join(outdir, f"panicci-bjj-gjjw_{name}_{ratio}.mp4")
    compose(base, dur, ov, out, tail=(sc["end"], 2.0))
    print(f"{out}: {dur + 2.0:.1f}s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", required=True); ap.add_argument("--words", required=True)
    ap.add_argument("--broll", required=True); ap.add_argument("--out-dir", default="out")
    ap.add_argument("--ratios", default="9x16,4x5"); ap.add_argument("--cuts", default="main,20s")
    ap.add_argument("--video-end", type=float, default=None, help="seconds of usable camera video (default: probe)")
    a = ap.parse_args(); os.makedirs(a.out_dir, exist_ok=True)
    words = [tuple(w) for w in json.load(open(a.words))]
    vend = a.video_end if a.video_end is not None else video_len(a.take) - 0.08
    for cutname in a.cuts.split(","):
        for r in a.ratios.split(","):
            build(cutname, MAIN if cutname == "main" else SHORT, words, a.take, a.broll, r, a.out_dir, vend)
