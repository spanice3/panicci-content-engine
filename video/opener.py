#!/usr/bin/env python3
"""Animated open + close cards and the cover still for talking-head cuts.

Every card is the same three things: a clean smiling shot of Sammy (assets/sammy-smile.jpg, both shoulders whole,
only the bottom cropped), a big hook, and a play button so it reads as a video in a grid or a paused feed.

  open  (1.2 s): frame 0 is the finished cover (that's the thumbnail). The gold word catches a sheen, the play
                 button pulses, gets pressed (soft tap), and the card irises open from the button into the footage.
  close (2.4 s): the footage collapses back into the play button, the button pops in, the closing line rises in
                 word by word, the swoosh draws under the key word, and the button keeps pulsing to the last frame.

Cards stream straight into ffmpeg as lossless video with alpha (FFV1), which brandkit.py lays over the footage in
its single pass.
Text comes from the take's script (first line = hook, last line = the call to action) or an explicit
`cover` object in the Script data: {"kicker", "hook", "emphasis", "closeKicker", "close", "closeEmphasis"}.

  python3 opener.py <script.txt> <out_dir> [9x16,1x1]     # writes the covers + a contact sheet for a look
"""
import math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, ".build")
PHOTO = os.path.join(HERE, "assets", "sammy-smile.jpg")
# Sammy in that photo: cap top to the photo's bottom edge, outer edge of each shoulder/arm (source px).
PERSON = (236, 330, 1116, 960)
PHOTO_FACE = (608, 438, 811, 694)                   # YuNet on the photo (face.detect_image)
BAND_Y = 868                                        # below this row his arms run wide: keep it under a band/edge
INK, CREAM, GOLD, WHITE, SAGE = (13, 18, 16), (246, 241, 232), (242, 193, 78), (255, 255, 255), (155, 191, 161)
FPS = 30
OPEN_HOLD, OPEN_IRIS, CLOSE = 0.9, 0.3, 2.4         # seconds
TAP_AT, POP_AT = 0.72, 0.32                         # sound cues (open-relative, close-relative)
BRAND = "SAMMY P · PANICCI VENTURES"


def F(weight, size):
    return ImageFont.truetype(os.path.join(BUILD, f"PVSG{weight}.ttf"), max(8, round(size)))


def ease_out(u):
    u = min(max(u, 0.0), 1.0); return 1 - (1 - u) ** 3


def ease_in(u):
    u = min(max(u, 0.0), 1.0); return u ** 2.2


# ---------------------------------------------------------------- words

def _tidy(t):
    t = re.sub(r"\bnumber (\d+)", r"#\1", t, flags=re.I)
    t = re.sub(r"(\(\d{3}\)) (\d{3}-\d{4})", "\\1\u00a0\\2", t)
    t = re.sub(r'"(?=\w)', "\u201c", t).replace('"', "\u201d").replace("'", "\u2019")
    return re.sub(r"[ \t\r\n]+", " ", t).strip()


def words(t):
    return [x for x in t.split(" ") if x]          # plain spaces only: a no-break space keeps "(702) 467-0784" whole


def emphasis(text):
    """(i, j, own_line): the word span to paint gold. A short answer after a question gets its own big line."""
    w = words(text)
    if not w:
        return 0, 0, False
    q = text.rfind("?")
    if 0 < q < len(text) - 1:
        after = words(text[q + 1:])
        if 0 < len(after) <= 3:
            return len(w) - len(after), len(w), True
    for i, x in enumerate(w):                                       # an all-caps keyword: "Text MAPS"
        core = re.sub(r"[^A-Za-z]", "", x)
        if len(core) >= 2 and core.isupper() and core not in ("AI", "SEO", "AEO", "GEO", "GBP", "SMS"):
            return i, i + 1, False
    ph = re.search(r"\(?\d{3}\)?[ \u00a0.-]?\d{3}-\d{4}", text)
    if ph:
        a = len(words(text[:ph.start()])); b = len(words(text[:ph.end()]))
        return a, b, False
    for i, x in enumerate(w):                                       # "30% more"
        if "%" in x:
            return i, min(len(w), i + 2), False
    for i in range(len(w) - 1, -1, -1):                             # the last number: "to 62.", "#21"
        if re.search(r"\d", w[i]):
            return i, i + 1, False
    return len(w) - 1, len(w), False


def texts_from(script=None, cover=None, captions=None):
    """The words on the cards. Explicit `cover` fields win; then the script; then the captions."""
    cover = cover or {}
    lines = [l.strip() for l in (script or "").splitlines() if l.strip() and l.strip() != "|"]
    if not lines and captions:
        lines = [c["text"] for c in captions]
    hook = lines[0] if lines else "Watch this."
    if len(lines) > 1 and len(words(hook)) <= 6 and len(words(hook + " " + lines[1])) <= 13:
        hook += " " + lines[1]
    kicker = BRAND
    m = re.match(r"^([^:?.!]{3,40}):\s+(.+)$", hook)
    if m and len(words(m.group(1))) <= 4:
        kicker, hook = m.group(1), m.group(2)[0].upper() + m.group(2)[1:]
    close, ck = (lines[-1] if len(lines) > 1 else "Follow along."), "FOLLOW ALONG"
    if len(lines) > 2 and lines[-2].endswith("?"):
        ck = lines[-2]
    if len(words(close)) > 13:                                     # keep the close to one sentence
        close = re.split(r"(?<=[.!?])\s+", close)[0]
    t = dict(kicker=cover.get("kicker") or kicker, hook=_tidy(cover.get("hook") or hook),
             close_kicker=cover.get("closeKicker") or ck, close=_tidy(cover.get("close") or close))
    t["emph"] = _span(t["hook"], cover.get("emphasis"))
    t["close_emph"] = _span(t["close"], cover.get("closeEmphasis"))
    return t


def _span(text, want):
    if want and want in text:
        a = len(words(text[:text.index(want)])); return a, a + len(words(want)), False
    return emphasis(text)


# ---------------------------------------------------------------- layout

def layout(ratio, W, H):
    """Where the photo, the words and the play button go. Photo scale keeps both shoulders inside the frame."""
    k = W / 1080.0
    if ratio == "9x16":
        s = 1.15; py = 640; px = W / 2 - (PERSON[0] + PERSON[2]) / 2 * s
        text = (72, 250, W - 110, None); band = py + BAND_Y * s        # band hides where the arms reach the sides
        return dict(k=k, s=s, px=px, py=py, fade=("top", 190), text=text, band=band, r=round(92 * k), play="gap",
                    tsize=(128, 72), kick=40, maxl=4)
    if ratio == "1x1":
        s = 0.9; py = H - 960 * s; px = W / 2 - (PERSON[0] + PERSON[2]) / 2 * s - 40
        return dict(k=k, s=s, px=px, py=py, fade=("top", 330), text=(54, 64, W - 54, 470), band=None,
                    r=round(78 * k), play="side", tsize=(96, 56), kick=32, maxl=3)
    s = 1.05; py = H - 960 * s; px = W - 24 * W / 1920.0 - 24 - PERSON[2] * s    # 16x9: photo right, words left
    return dict(k=W / 1920.0, s=s, px=px, py=py, fade=("left", 200), text=(90, 150, 860, 760), band=None,
                r=round(84 * W / 1920.0), play="below", tsize=(100, 60), kick=34, maxl=4)


def background(L, W, H):
    """Ink, Panicci dots, the photo melting out of the ink, a plain band under the photo's bottom edge."""
    img = Image.new("RGBA", (W, H), INK + (255,))
    d = ImageDraw.Draw(img)
    for y in range(11, H, 22):
        for x in range(11, W, 22):
            d.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=CREAM + (18,))
    ph = Image.open(PHOTO).convert("RGB")
    pw, phh = round(ph.width * L["s"]), round(ph.height * L["s"])
    ph = ph.resize((pw, phh), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", ph.size, 255); md = ImageDraw.Draw(m)
    side, n = L["fade"]
    for i in range(n):
        a = round(255 * (i / n) ** 1.8)
        if side == "top":
            md.line((0, i, pw, i), fill=a)
        else:
            md.line((i, 0, i, phh), fill=a)
    img.paste(ph, (round(L["px"]), round(L["py"])), m)
    return img


def face_zone(L):
    x0, y0, x1, y1 = PHOTO_FACE; w, h = x1 - x0, y1 - y0
    z = (x0 - w * 0.32, y0 - h * 0.45, x1 + w * 0.32, y1 + h * 0.30)       # cap, headphones, beard
    return tuple(v * L["s"] + (L["px"] if i % 2 == 0 else L["py"]) for i, v in enumerate(z))


def words_layer(W, H, L, kicker, text, emph, top=None):
    """Kicker + hook, auto-sized. Returns (layer, word sprites [(img, x, y)], emph box, swoosh points, bottom y)."""
    k = L["k"]; x0, y0, x1, ymax = L["text"]; y0 = top if top is not None else y0
    ymax = ymax or (face_zone(L)[1] - 2 * L["r"] - 70 * k)
    maxw = x1 - x0; d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    ws = words(text); i0, i1, own = emph
    body = ws[:i0] if own else ws
    fk = F("Bold", L["kick"] * k)
    for size in range(L["tsize"][0], L["tsize"][1] - 1, -4):
        fs = F("Bold", size * k); fe = F("Bold", size * k * (1.25 if own else 1.0))
        sp = d0.textlength(" ", font=fs); lines, cur, cw = [], [], 0
        for wi, wd in enumerate(body):
            ww = d0.textlength(wd, font=fs)
            if cur and cw + sp + ww > maxw:
                lines.append(cur); cur, cw = [], 0
            cur.append(wi); cw += (sp if len(cur) > 1 else 0) + ww
        if cur:
            lines.append(cur)
        lh = size * k * 1.02; eh = size * k * 1.25 * 1.05 if own else 0
        tall = 66 * k + lh * len(lines) + eh
        wide = max([d0.textlength(" ".join(ws[i] for i in ln), font=fs) for ln in lines] or [0])
        if own:
            wide = max(wide, d0.textlength(" ".join(ws[i0:i1]), font=fe))
        if len(lines) + (1 if own else 0) <= L["maxl"] + (1 if own else 0) and y0 + tall <= ymax and wide <= maxw:
            break
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    sprites = []

    def put(s, x, y, font, fill):
        bb = d0.textbbox((0, 0), s, font=font); pad = round(8 * k)
        sp_ = Image.new("RGBA", (bb[2] + 2 * pad, bb[3] + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(sp_).text((pad, pad), s, font=font, fill=fill + (255,))
        sprites.append((sp_, round(x - pad), round(y - pad)))
        layer.alpha_composite(sp_, (round(x - pad), round(y - pad)))
        return d0.textlength(s, font=font)

    put(kicker.upper(), x0, y0, fk, GOLD)
    y = y0 + 66 * k; ebox = None
    for ln in lines:
        x = x0
        for wi in ln:
            gold = (not own) and i0 <= wi < i1
            wl = put(ws[wi], x, y, fs, GOLD if gold else WHITE)
            if gold:
                b = (x, y, x + wl, y + size * k)
                ebox = b if ebox is None or b[1] != ebox[1] else (ebox[0], ebox[1], b[2], b[3])
            x += wl + sp
        y += lh
    if own:
        wl = put(" ".join(ws[i0:i1]), x0, y - 6 * k, fe, GOLD)
        ebox = (x0, y - 6 * k, x0 + wl, y - 6 * k + size * k * 1.25); y += eh
    swoosh = []
    if ebox:
        wv = ebox[2] - ebox[0]; uy = ebox[3] + (14 if own else 12) * k
        swoosh = [(ebox[0] + 6 * k + (wv - 24 * k) * t, uy - 16 * k * (1 - (2 * t - 1) ** 2) + 6 * k * t)
                  for t in [i / 40 for i in range(41)]]
    return layer, sprites, ebox, swoosh, y


def play_sprite(r, k, scale=1.0):
    r2 = max(4, round(r * scale)); pad = round(30 * k); S = 2 * (r2 + pad)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); c = S // 2
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((c - r2, c - r2 + 8 * k, c + r2, c + r2 + 8 * k), fill=(0, 0, 0, 120))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14 * k)))
    d = ImageDraw.Draw(im)
    d.ellipse((c - r2, c - r2, c + r2, c + r2), fill=INK + (170,), outline=CREAM + (240,), width=max(2, round(6 * k * scale)))
    t = r2 * 0.42
    d.polygon([(c - t * 0.75, c - t), (c - t * 0.75, c + t), (c + t * 1.05, c)], fill=CREAM + (255,))
    return im


def ring(img, c, rad, alpha, width):
    if alpha <= 0 or rad <= 0:
        return
    R = math.ceil(rad + width); lay = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse((R - rad, R - rad, R + rad, R + rad), outline=GOLD + (round(255 * alpha),),
                                width=max(1, round(width)))
    x, y = round(c[0] - R), round(c[1] - R)
    if x >= 0 and y >= 0 and x + 2 * R <= img.width and y + 2 * R <= img.height:
        img.alpha_composite(lay, (x, y))
    else:                                               # near an edge: clip through a full-size layer
        full = Image.new("RGBA", img.size, (0, 0, 0, 0)); full.paste(lay, (x, y)); img.alpha_composite(full)


def play_center(L, W, H, text_bottom):
    z = face_zone(L); k = L["k"]; r = L["r"]
    if L["play"] == "gap":
        return (W // 2, round((text_bottom + z[1]) / 2))
    if L["play"] == "side":
        return (round((z[2] + W - 54 * k) / 2), round((z[1] + z[3]) / 2))
    return (round(L["text"][0] + r + 6 * k), round(text_bottom + r + 40 * k))


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ---------------------------------------------------------------- frames

class Card:
    def __init__(self, ratio, W, H, kicker, text, emph, footer=None):
        self.W, self.H = W, H; self.L = L = layout(ratio, W, H); k = L["k"]
        self.bg = background(L, W, H)
        self.text, self.sprites, self.ebox, self.swoosh, tb = words_layer(W, H, L, kicker, text, emph)
        self.c = play_center(L, W, H, tb)
        r = L["r"]; pb = (self.c[0] - r, self.c[1] - r, self.c[0] + r, self.c[1] + r)
        if _overlaps(pb, face_zone(L)):                         # never on his face
            raise RuntimeError(f"play button would cover the face on {ratio}")
        self.band = None
        if L["band"] and L["band"] < H:
            self.band = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(self.band)
            y = round(L["band"]); bd.rectangle((0, y, W, H), fill=INK + (255,))
            for yy in range(y + 11, H, 22):
                for xx in range(11, W, 22):
                    bd.ellipse((xx - 1.4, yy - 1.4, xx + 1.4, yy + 1.4), fill=CREAM + (18,))
            bd.rectangle((0, y, W, y + round(3 * k)), fill=GOLD + (255,))
            mk = Image.open(os.path.join(BUILD, "mark_cream.png")).convert("RGBA")
            ms = round(46 * k); mk = mk.resize((ms, ms), Image.LANCZOS)
            fy = y + round(40 * k); self.band.alpha_composite(mk, (L["text"][0], fy))
            bd.text((L["text"][0] + ms + 18 * k, fy + 8 * k), footer or BRAND, font=F("SemiBold", 26 * k), fill=CREAM + (230,))
        elif footer:                                            # no band: footer sits under the words
            ImageDraw.Draw(self.text).text((L["text"][0], tb + 6 * k), footer, font=F("SemiBold", 30 * k), fill=CREAM + (220,))
        self.k = k; self.r = r
        self.btn = {}

    def button(self, scale):
        key = round(scale, 3)
        if key not in self.btn:
            self.btn[key] = play_sprite(self.r, self.k, scale)
        return self.btn[key]

    def base(self, zoom=1.0):
        if abs(zoom - 1.0) < 2e-3:
            return self.bg.copy()
        W, H = self.W, self.H; fz = face_zone(self.L); ax, ay = (fz[0] + fz[2]) / 2, (fz[1] + fz[3]) / 2
        big = self.bg.resize((round(W * zoom), round(H * zoom)), Image.BILINEAR)
        ox, oy = round(ax * zoom - ax), round(ay * zoom - ay)
        return big.crop((ox, oy, ox + W, oy + H))

    def compose(self, zoom=1.0, btn=1.0, rings=(), text_alpha=None, swoosh=1.0, sheen=None):
        img = self.base(zoom)
        if self.band:
            img.alpha_composite(self.band)
        if text_alpha is None:
            img.alpha_composite(self.text)
        else:                                                   # words rising in, one after another
            for (sp, x, y), a in zip(self.sprites, text_alpha):
                if a <= 0:
                    continue
                s2 = sp if a >= 1 else _fade(sp, a)
                img.alpha_composite(s2, (x, y + round(34 * self.k * (1 - a))))
        if self.swoosh and swoosh > 0:
            n = max(2, round(len(self.swoosh) * min(1, swoosh)))
            ImageDraw.Draw(img).line(self.swoosh[:n], fill=GOLD + (255,), width=round(9 * self.k), joint="curve")
        if sheen is not None and self.ebox:
            _sheen(img, self.ebox, sheen, self.k)
        for rad, a in rings:
            ring(img, self.c, rad, a, 5 * self.k)
        if btn > 0.01:
            b = self.button(btn); img.alpha_composite(b, (self.c[0] - b.width // 2, self.c[1] - b.height // 2))
        return img

    def far(self):
        return max(math.hypot(self.c[0] - x, self.c[1] - y) for x in (0, self.W) for y in (0, self.H))


def _fade(sp, a):
    s2 = sp.copy(); s2.putalpha(sp.getchannel("A").point(lambda v: round(v * a))); return s2


def _sheen(img, box, u, k):
    """A light band sweeping across the gold word (u: 0..1 across)."""
    x0, y0, x1, y1 = [round(v) for v in box]; x0 -= 4; y0 -= round(10 * k); y1 += round(16 * k)
    region = img.crop((x0, y0, x1, y1)); w, h = region.size
    if w < 4 or h < 4:
        return
    a = np.asarray(region)
    gold = Image.fromarray(((a[..., 0] > 200) & (a[..., 1] > 150) & (a[..., 1] < 225) & (a[..., 2] < 140)).astype(np.uint8) * 255)
    band = Image.new("L", (w, h), 0); bd = ImageDraw.Draw(band)
    cx = -0.3 * w + u * 1.6 * w; bw = 0.18 * w
    bd.polygon([(cx - bw, h), (cx, h), (cx + bw + 0.3 * h, 0), (cx + 0.3 * h, 0)], fill=150)
    band = band.filter(ImageFilter.GaussianBlur(6 * k))
    from PIL import ImageChops
    m = ImageChops.multiply(band, gold)
    white = Image.new("RGBA", (w, h), (255, 248, 225, 255)); region.paste(white, (0, 0), m)
    img.paste(region, (x0, y0))


def iris(card_img, c, rad, k, edge=True):
    """Punch a growing/shrinking hole in the card so the footage shows through."""
    m = Image.new("L", card_img.size, 255)
    ImageDraw.Draw(m).ellipse((c[0] - rad, c[1] - rad, c[0] + rad, c[1] + rad), fill=0)
    card_img.putalpha(m)
    if edge and rad > 2:
        ImageDraw.Draw(card_img).ellipse((c[0] - rad, c[1] - rad, c[0] + rad, c[1] + rad), outline=GOLD + (255,),
                                         width=max(2, round(6 * k)))
    return card_img


class AlphaVideo:
    """RGBA frames piped into ffmpeg as lossless FFV1 with alpha: no PNG round trip per frame."""
    def __init__(self, path, W, H):
        self.p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                                   "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "ffv1", "-level", "3", "-slices", "4",
                                   "-threads", "4", "-pix_fmt", "yuva444p", path], stdin=subprocess.PIPE)
        self.n = 0

    def save(self, img, *_a, **_k):
        self.p.stdin.write(img.tobytes()); self.n += 1

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            raise RuntimeError("ffmpeg could not write the card")
        return self.n


def render_open(card, path):
    """OPEN_HOLD + OPEN_IRIS seconds of RGBA frames. Frame 0 is the cover."""
    out = AlphaVideo(path, card.W, card.H)
    n_hold, n_iris = round(OPEN_HOLD * FPS), round(OPEN_IRIS * FPS); r = card.r; far = card.far()
    for f in range(n_hold + n_iris):
        t = f / FPS
        zoom = 1.0 + 0.025 * ease_out(t / (OPEN_HOLD + OPEN_IRIS))
        p = (t % 0.6) / 0.6 if t < 0.6 else None                      # one breath of the ring before the tap
        rings = [(r * (1 + 0.55 * ease_out(p)), 0.75 * (1 - p))] if p is not None and t > 0.05 else []
        btn = 1.0 + 0.05 * math.sin(math.pi * min(t / 0.6, 1))
        if 0.62 <= t < 0.9:                                           # the tap
            u = (t - 0.62) / 0.28
            btn = 1 - 0.14 * math.sin(math.pi * min(u * 1.6, 1))
            rings = [(r * (1 + 1.4 * ease_out(u)), 0.95 * (1 - u))]
        sheen = (t - 0.08) / 0.5 if 0.08 <= t <= 0.58 else None
        img = card.compose(zoom=zoom, btn=btn if t < OPEN_HOLD else 1.0, rings=rings, sheen=sheen)
        if t >= OPEN_HOLD:                                            # iris opens out of the play button
            u = (t - OPEN_HOLD + 1 / FPS) / OPEN_IRIS
            img = iris(img, card.c, r * 0.9 + (far - r * 0.9) * ease_in(u), card.k)
        out.save(img)
    return out.close()


def render_close(card, path):
    out = AlphaVideo(path, card.W, card.H)
    n = round(CLOSE * FPS); r = card.r; far = card.far(); nw = len(card.sprites)
    for f in range(n):
        t = f / FPS
        zoom = 1.04 - 0.04 * ease_out(t / CLOSE)
        ta = [ease_out((t - 0.40 - 0.05 * i) / 0.28) for i in range(nw)]
        sw = (t - 0.95) / 0.3
        if t < POP_AT:
            btn = 0.0
        else:
            u = (t - POP_AT) / 0.25
            btn = 1.0 if u >= 1 else ease_out(u) * (1 + 0.15 * math.sin(math.pi * u))
        rings = []
        if t > 1.2:
            for ph in (0.0, 0.5):
                p = ((t - 1.2 + ph) % 1.0) / 1.0
                rings.append((r * (1 + 0.6 * ease_out(p)), 0.7 * (1 - p)))
        img = card.compose(zoom=zoom, btn=btn, rings=rings, text_alpha=ta, swoosh=sw if sw > 0 else 0)
        if t < 0.36:                                                  # footage collapses into the button
            u = t / 0.36
            img = iris(img, card.c, far * (1 - ease_out(u)) + r * 0.8 * ease_out(u), card.k)
        out.save(img)
    return out.close()


def build(ratio, W, H, texts, out_dir, cover_png=None):
    """Writes out_dir/open.mkv and out_dir/close.mkv (alpha); saves the cover still. Returns timing for brandkit."""
    os.makedirs(out_dir, exist_ok=True)
    op = Card(ratio, W, H, texts["kicker"], texts["hook"], texts["emph"])
    if cover_png:
        op.compose().convert("RGB").save(cover_png)
    no = render_open(op, os.path.join(out_dir, "open.mkv"))
    cl = Card(ratio, W, H, texts["close_kicker"], texts["close"], texts["close_emph"], footer="panicciventures.com")
    nc = render_close(cl, os.path.join(out_dir, "close.mkv"))
    return dict(open=os.path.join(out_dir, "open.mkv"), close=os.path.join(out_dir, "close.mkv"),
                open_hold=OPEN_HOLD, open_len=no / FPS, close_len=nc / FPS, tap_at=TAP_AT, pop_at=POP_AT)


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]; ratios = (sys.argv[3] if len(sys.argv) > 3 else "9x16,1x1").split(",")
    os.makedirs(out, exist_ok=True)
    tx = texts_from(open(src).read())
    print(tx)
    dims = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
    for r_ in ratios:
        W, H = dims[r_]
        Card(r_, W, H, tx["kicker"], tx["hook"], tx["emph"]).compose().convert("RGB").save(os.path.join(out, f"cover_{r_}.png"))
        c2 = Card(r_, W, H, tx["close_kicker"], tx["close"], tx["close_emph"], footer="panicciventures.com")
        c2.compose().convert("RGB").save(os.path.join(out, f"close_{r_}.png"))
    print("wrote", out)
