#!/usr/bin/env python3
""""The $11,500 Word doc" talking head, recut (Sammy's notes, Nov 12 2026).

  python3 word_doc_bid.py --seamless seamless.mp4 --words ads/word-doc-bid/words.json --out-dir out [--formats 9x16,4x5]

What changed from the Clipper cut (brandkit.py):
  - Opens and closes on the same frame: the title above his head, his picture dimmed under a gold play button.
    The end frame adds "DM me PROPOSAL" in the caption band, so a loop runs end frame -> start frame cleanly
    and the start frame works as the grid cover.
  - Captions sit in a band under the camera window, never on his face. Short chunks (two lines max).
  - Founder photo law: the take is a 1920x1080 webcam frame and his shirt stays inside source x 592-1360 for the
    whole cut (measured at 4 fps), so the camera window is source x 476-1476: about 125 px clear past each shoulder
    on the canvas. The window's bottom edge is the only crop, and the caption band sits under it.
  - No green intro card and no "Follow along" outro: the hook starts at 0.6 s.

--seamless is the Clipper's jump-cut (cuts/word-doc-bid-recording-2026-11-11_11-04-26-take1/seamless.mp4 in the
2026-11-11 Studio takes folder). --words is captions.asr_words() output for that file: [start, end, word].
Captions follow what he said on the take (he ad-libbed a few lines off the script), with the spelling fixed.
"""
import argparse, json, os, re, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, ".build")
F = {k: os.path.join(B, f"PVSG{k}.ttf") for k in ("Bold", "SemiBold", "Medium", "Regular")}
DEEP = (25, 67, 36); GREEN = (41, 96, 55); GOLD = (206, 158, 39); CREAM = (249, 246, 241)
SAGE = (155, 191, 161); INK = (18, 33, 26)
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "1", "-movflags", "+faststart"]

SRC_X, SRC_W = 476, 1000            # camera window in source px (shirt measured at x 592-1360)
LAYOUT = {
    # Meta/TikTok UI covers ~250 px top and ~480 px bottom of a 9:16 frame, plus the right action rail (190 px).
    "9x16": dict(W=1080, H=1920, crop_y=360, crop_h=680, win_y=532, band=(1266, 1440), cap_w=700,
                 kicker_y=262, title=[("The $11,500", GOLD, 96), ("Word doc.", CREAM, 96)], title_y=300),
    "4x5":  dict(W=1080, H=1350, crop_y=370, crop_h=680, win_y=212, band=(964, 1240), cap_w=820,
                 kicker_y=64, title=[("The $11,500 Word doc.", CREAM, 76)], title_y=98),
}
HOLD_IN, HOLD_OUT = 0.6, 2.6
WEAK = {"the", "a", "an", "and", "of", "to", "in", "for", "with", "on", "my", "your", "their", "i", "is"}        # still start frame, still end frame (s)

# spelling fixes on what Whisper heard (the script's wording where the audio says the same thing)
TITLE_FIX = {"word": "Word", "Scopes": "scopes", "wire.": "wiring.", "proposal": "proposals", "proposal.": "PROPOSAL."}
REPLACE = [("11 ,500 dollars.", "$11,500."), ("11,500 dollars.", "$11,500."),
           ("sign on the phone", "sign on their phone"), ("Job's done.", "Job's done?")]


def font(k, s):
    return ImageFont.truetype(F[k], max(8, round(s)))


def run(*a):
    subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a])


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode().strip())


# ---------------------------------------------------------------- captions
def chunks(words):
    """Short caption chunks from word timings: break on sentence ends, on commas once a chunk has some length,
    at ~34 characters or 2.0 s."""
    toks = []
    for s, e, w in words:
        w = w.strip()
        if w.startswith(",") and toks:          # "11 ,500" -> one token
            toks[-1][2] += w; toks[-1][1] = e; continue
        toks.append([s, e, w])
    out, cur = [], []
    def flush():
        if cur:
            out.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(t[2] for t in cur)})
    for i, t in enumerate(toks):
        nxt = toks[i + 1][2] if i + 1 < len(toks) else ""
        text = " ".join(x[2] for x in cur + [t])
        if cur and (len(text) > 36 or t[1] - cur[0][0] > 2.0):
            carry = []                          # never end a line on "the", "a", "and"...: carry them over
            if re.search(r"[.?!]$", t[2]) and len(cur) > 2:
                carry.insert(0, cur.pop())      # and never leave the sentence's last word alone on a line
            while len(cur) > 1 and cur[-1][2].lower() in WEAK:
                carry.insert(0, cur.pop())
            flush(); cur = carry
        cur.append(t)
        text = " ".join(x[2] for x in cur)
        if re.search(r"[.?!]$", t[2]) or (t[2].endswith(",") and len(text) >= 14):
            if not (t[2] == "11" or nxt.startswith(",")):
                flush(); cur = []
    flush()
    for c in out:
        txt = " ".join(TITLE_FIX.get(w, re.sub(r"^word\b", "Word", w)) for w in c["text"].split())
        for a, b in REPLACE:
            txt = txt.replace(a, b)
        c["text"] = txt
    for a, b in zip(out, out[1:]):              # hold each line until the next one starts (no flicker)
        a["end"] = b["start"] - 0.02 if b["start"] - a["end"] < 0.6 else a["end"] + 0.25
    out[-1]["end"] += 0.3
    return out


def wrap(d, text, f, maxw):
    """Greedy wrap, then rebalance a two-line caption so neither line is a lone word."""
    lines = _greedy(d, text, f, maxw)
    if len(lines) == 2:
        ws = text.split(); best = None
        for i in range(1, len(ws)):
            a, b = " ".join(ws[:i]), " ".join(ws[i:])
            wa, wb = d.textlength(a, font=f), d.textlength(b, font=f)
            if max(wa, wb) > maxw: continue
            score = max(wa, wb) + (400 if ws[i - 1].lower() in WEAK else 0)
            if best is None or score < best[0]: best = (score, [a, b])
        if best: lines = best[1]
    return lines


def _greedy(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def caption_png(text, lay, path):
    W, H = lay["W"], lay["H"]; f = font("Bold", 56)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    padx, pady, lh = 34, 18, 64
    lines = wrap(d, text, f, lay["cap_w"] - 2 * padx)
    tw = max(d.textlength(l, font=f) for l in lines)
    y0 = lay["band"][0] + 10; y1 = y0 + lh * len(lines) + 2 * pady
    d.rounded_rectangle([W / 2 - tw / 2 - padx, y0, W / 2 + tw / 2 + padx, y1], radius=20, fill=DEEP + (236,))
    d.rounded_rectangle([W / 2 - 30, y1 - 12, W / 2 + 30, y1 - 8], radius=2, fill=GOLD + (255,))
    y = y0 + pady - 4
    for l in lines:
        d.text(((W - d.textlength(l, font=f)) / 2, y), l, font=f, fill=CREAM + (255,)); y += lh
    img.save(path)


# ---------------------------------------------------------------- frames
def background(lay, path):
    """Brand ground (deep green, faint dot texture), the kicker and the title above his head."""
    W, H = lay["W"], lay["H"]
    img = Image.new("RGB", (W, H), DEEP); d = ImageDraw.Draw(img)
    for y in range(H):                                       # green glow at the top, ink at the bottom
        t = y / H
        c = tuple(int(GREEN[i] * (1 - t) * 0.5 + DEEP[i] * (0.5 + t * 0.5) * (1 - 0.35 * t) + INK[i] * 0.35 * t * t)
                  for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(dots)
    for y in range(8, H, 22):
        for x in range(8 + (11 if (y // 22) % 2 else 0), W, 22):
            dd.ellipse([x - 1.3, y - 1.3, x + 1.3, y + 1.3], fill=CREAM + (16,))
    img = Image.alpha_composite(img.convert("RGBA"), dots); d = ImageDraw.Draw(img)
    k = font("SemiBold", 28 if lay["H"] > 1500 else 24)
    kick = "SAMMY P  ·  PANICCI VENTURES"
    sp = 5
    tw = sum(d.textlength(ch, font=k) for ch in kick) + sp * (len(kick) - 1)
    x = (W - tw) / 2
    for ch in kick:
        d.text((x, lay["kicker_y"]), ch, font=k, fill=GOLD); x += d.textlength(ch, font=k) + sp
    y = lay["title_y"]
    for text, col, size in lay["title"]:
        f = font("Bold", size)
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=col); y += int(size * 1.0)
    img.convert("RGB").save(path)


def play_button(d, img, cx, cy, r):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - r, cy - r + 10, cx + r, cy + r + 10], fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD + (255,), outline=CREAM + (235,), width=6)
    t = r * 0.42                                              # triangle, nudged right so it looks centred
    d.polygon([(cx - t * 0.78, cy - t), (cx - t * 0.78, cy + t), (cx + t * 1.12, cy)], fill=INK + (255,))


def cover_png(lay, path, cta=False):
    """Start/end frame overlay: dim the camera window, gold play button on his chest; the end frame adds the CTA."""
    W, H = lay["W"], lay["H"]; wh = round(lay["crop_h"] * W / SRC_W)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle([0, lay["win_y"], W, lay["win_y"] + wh], fill=INK + (92,))
    chest = lay["win_y"] + round((905 - lay["crop_y"]) * W / SRC_W)    # source y ~905: below the beard
    play_button(d, img, W // 2, min(chest, lay["win_y"] + wh - 110), 96)
    if cta:
        d = ImageDraw.Draw(img)
        f1, f2 = font("Bold", 64), font("Medium", 32)
        a, b = "DM me ", "PROPOSAL"
        w1 = d.textlength(a, font=f1) + d.textlength(b, font=f1)
        sub = "I'll show you yours rebuilt."
        bw = max(w1, d.textlength(sub, font=f2)) + 2 * 40
        y0 = lay["band"][0] + 10; y1 = y0 + 160
        d.rounded_rectangle([W / 2 - bw / 2, y0, W / 2 + bw / 2, y1], radius=22, fill=DEEP + (245,),
                            outline=GOLD + (255,), width=3)
        x = (W - w1) / 2
        d.text((x, y0 + 20), a, font=f1, fill=CREAM); d.text((x + d.textlength(a, font=f1), y0 + 20), b, font=f1, fill=GOLD)
        d.text(((W - d.textlength(sub, font=f2)) / 2, y0 + 104), sub, font=f2, fill=SAGE)
    img.save(path)


# ---------------------------------------------------------------- render
def render(seamless, caps, ratio, out, tmp):
    lay = LAYOUT[ratio]; W, H = lay["W"], lay["H"]; wh = round(lay["crop_h"] * W / SRC_W); wh -= wh % 2
    os.makedirs(tmp, exist_ok=True)
    background(lay, f"{tmp}/bg.png"); cover_png(lay, f"{tmp}/start.png"); cover_png(lay, f"{tmp}/end.png", cta=True)
    D = dur(seamless); T = HOLD_IN + D + HOLD_OUT
    capf = []
    for i, c in enumerate(caps):
        p = f"{tmp}/cap{i:02d}.png"; caption_png(c["text"], lay, p); capf.append((p, c["start"] + HOLD_IN, c["end"] + HOLD_IN))
    inp = ["-i", seamless, "-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", f"{tmp}/bg.png",
           "-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", f"{tmp}/start.png",
           "-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", f"{tmp}/end.png"]
    for p, _, _ in capf:
        inp += ["-i", p]
    fc = [f"[0:v]fps=30,crop={SRC_W}:{lay['crop_h']}:{SRC_X}:{lay['crop_y']},scale={W}:{wh},setsar=1,"
          f"tpad=start_duration={HOLD_IN}:start_mode=clone:stop_duration={HOLD_OUT + 0.2}:stop_mode=clone[cam];",
          f"[1:v]format=rgba[bg];[bg][cam]overlay=0:{lay['win_y']}:shortest=1[v0];"]
    cur = "v0"
    for i, (p, s, e) in enumerate(capf):
        fc.append(f"[{4 + i}:v]format=rgba[c{i}];[{cur}][c{i}]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{i + 1}];")
        cur = f"v{i + 1}"
    fc.append(f"[2:v]format=rgba,fade=t=out:st={HOLD_IN:.3f}:d=0.22:alpha=1[st];[{cur}][st]overlay=0:0[vs];")
    fc.append(f"[3:v]format=rgba,fade=t=in:st={HOLD_IN + D:.3f}:d=0.3:alpha=1[en];[vs][en]overlay=0:0,"
              f"trim=duration={T:.3f},format=yuv420p[vout];")
    fc.append(f"[0:a]adelay={int(HOLD_IN * 1000)}:all=1,apad=whole_dur={T:.3f}[aout]")
    run(*inp, "-filter_complex", "".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{T:.3f}", *ENC, out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seamless", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--formats", default="9x16,4x5")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    caps = chunks(json.load(open(a.words)))
    json.dump(caps, open(os.path.join(a.out_dir, "captions.json"), "w"), indent=1)
    for r in a.formats.split(","):
        o = os.path.join(a.out_dir, f"word-doc-bid_{r}.mp4")
        render(a.seamless, caps, r, o, os.path.join(a.out_dir, f".tmp_{r}"))
        print("wrote", o, f"{dur(o):.1f}s")


if __name__ == "__main__":
    main()
