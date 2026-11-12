#!/usr/bin/env python3
"""Electrician story, "The $11,500 Word doc" (Ready script word-doc-bid), proof-card cut. Opens on a clean title screen
(the title alone, held through the first spoken sentence, Sammy's rule), then face on camera the whole time, a title band up top, and the real bid (names blurred) popping up as cards above Sammy's head on the line it
backs up. Same engine and look as the BJJ v3 ad (bjj_gjjw_v2.py).

  python3 word_doc_bid.py --take seamless.mp4 --captions captions.json --assets <dir> --crop9 X,Y,W,H --crop45 X,Y,W,H
  python3 word_doc_bid.py --cut dont --take seamless.mp4 --captions captions.json --assets <dir> \\
      --crop9 260,0,1400,1080 --crop45 260,0,1400,1080          # electrician-dont take 7 (Nov 12)
  python3 word_doc_bid.py --cut friction ...same crops...       # electrician-friction take 1 (Nov 12)

--take / --captions: the Clipper's seamless.mp4 and captions.json for word-doc-bid take 1 (Nov 11 2026); the pauses
are already cut, so this pass only frames, captions and lays the cards over it.
--assets: proposal crops blurred from the bid .docx (crop-01-header-date.png, crop-02-lump-sum.png,
crop-04-gc-boilerplate.png, crop-05-sign-the-x.png), the blurred invoice page (invoice.png, from Inv 3721 .docx) and
the demo phone screens (p-link.png, p-options.png, p-signed.png, p-invoice.png, p-review.png), plus the bid's
Word page 1 (wordp1.png) and the same bid rebuilt by Sammy on one clean page (rebuilt.png, Sept 30, 2026), both blurred. The assets stay out of
this public repo: they are a real contractor's paperwork.
--crop9 / --crop45: the camera window in source px. Founder photo law: both shoulders whole, with clear space past
each one; check a few frames before rendering. Take 1 (1920x1080): the shirt runs x 590-1355 at the bottom row in every
frame checked, so --crop9 432,180,1080,900 --crop45 442,0,1060,1080 leave ~150 px clear past each shoulder (Nov 12 v1).
electrician-dont take 7 (black tee, no cap, framed closer, leans): the shirt reaches x ~390 left and ~1537 right at the
bottom row, so the window is 1400 px wide (x 260-1660), scaled to 1080: ~100 px clear past each shoulder.
electrician-friction take 1, same setup: the shirt runs x 426-1532 at the bottom row across the whole take (sampled
twice a second), so the same window leaves ~128 px left and ~99 px right after scaling.

Every number on a card comes from the paperwork: the bid (Sept 23, 2026: Base Bid $11,500.00, 296 devices across
its 19 line items, the GC-bid-form exclusion, the printed X signature line, 100% upon completion) and invoice #3721
(Oct 23, 2026: total $11,685.00, due on receipt, the "Reference Proposal:" line left blank, no pay link in the file).
The take says "Twelve grand and change", which the invoice doesn't back, so DROP cuts that sentence out of the audio.
The phone screens are a demo with a sample customer.
The friction cut's stat card is Oldroyd, McElheran & Elkington, "The Short Life of Online Sales Leads", Harvard
Business Review, March 2011: firms that tried to reach a lead within an hour were nearly seven times as likely to
qualify it (a meaningful conversation with a decision maker) as firms that waited even one more hour.
"""
import argparse, json, os, subprocess
import numpy as np
from PIL import Image, ImageDraw

from bjj_gjjw_ads import font, wrap, caption_png, INK, CREAM, GOLD, WHITE
from bjj_gjjw_v2 import cut, compose, place, timeline_any

LAYOUT = {
    "9x16": dict(W=1080, H=1920, top=250, bottom=480, side=72, box=(0, 640, 1080, 900), zone=(450, 860)),
    "4x5":  dict(W=1080, H=1350, top=56, bottom=110, side=64, box=(0, 250, 1080, 1100), zone=(236, 540)),
}
TITLE = ("ELECTRICIANS", "The $11,500 Word doc.")
# Sentences cut out of the read (first words of the caption chunk). The invoice total is $11,685, not "twelve grand".
DROP = ["Twelve grand"]

# (card, first words of the caption it opens on, first words of the caption it closes before). None = runs to the end.
BEATS = [
    ("doc", "Five days later", "Eleven thousand"),
    ("lump", "Eleven thousand", "Two hundred"),
    ("count", "Two hundred", "scopes not"),
    ("gc", "scopes not", "It's my house"),
    ("sign", "It's my house", "Then the invoice"),
    ("invoice", "Then the invoice", "Look"),
    ("rebuilt", "Here's the fix", "and before you leave"),
    ("link", "and before you leave", "Three options"),
    ("options", "Three options", "phone and pay"),
    ("signed", "phone and pay", "The invoice sends"),
    ("paybtn", "The invoice sends", "and asks for"),
    ("review", "and asks for", "If your proposals"),
    ("cta", "If your proposals", None),
]
CTA = ("Proposals still living in Word?", "DM me \u201cPROPOSAL\u201d", "I'll show you yours, rebuilt.")
TRIM_LEAD = False      # cut dead air before the first word
NAME = "word-doc-bid"

# Each cut: its title, cards, layout and close. --cut picks one; the functions below read these names at run time.
CUTS = {
    "word-doc": dict(name=NAME, title=TITLE, drop=DROP, beats=BEATS, layout=LAYOUT, cta=CTA, trim_lead=False),
    # Ready script electrician-dont (Brian's story rescript, Nov 12), take 7. Fewer cards than the word-doc cut, one per
    # idea, and none on "I still hired him. Most homeowners won't." so his face carries the turn. Sammy sits bigger in
    # this frame and leans, so the camera window is wider (scaled down) and lower; see the crop note in the docstring.
    "dont": dict(
        name="electrician-dont",
        title=("ELECTRICIANS", "Don't do what this guy did."),
        drop=[],
        beats=[("quote", "Swap every", "Five days"),
               ("doc", "Five days", "No photos"),
               ("lump", "No photos", "To say yes"),
               ("sign", "To say yes", "I still hired"),
               ("rebuilt", "Here's what easy", "Before you leave"),
               ("link", "Before you leave", "Your logo"),
               ("options", "Your logo", "They sign"),
               ("signed", "They sign", "When the job"),
               ("paybtn", "When the job", "If your quotes"),
               ("cta", "If your quotes", None)],
        layout={"9x16": dict(W=1080, H=1920, top=250, bottom=480, side=72, box=(0, 760, 1080, 833), zone=(430, 880)),
                "4x5": dict(W=1080, H=1350, top=56, bottom=110, side=64, box=(0, 517, 1080, 833), zone=(190, 655))},
        cta=("Quotes still going out as Word docs?", "DM me \u201cQUOTE\u201d", "I'll rebuild one of yours."),
        trim_lead=True),
    # Ready script electrician-friction (the direct version, Nov 12), take 1: the A/B partner to "dont". The hook runs
    # face-only, then one card per idea, held long: the print-and-sign Word doc, the HBR stat with its source on the
    # card, the real 5-day bid on "I just had an electrician take five days", then the fix and the close.
    "friction": dict(
        name="electrician-friction",
        title=("ELECTRICIANS", "It's not your price."),
        drop=[],
        beats=[("sign", "If it shows", "Harvard"),
               ("hbr", "Harvard", "I just had"),
               ("doc", "I just had", "Here's the fix"),
               ("link", "Here's the fix", "Your logo"),
               ("options", "Your logo", "They sign"),
               ("signed", "They sign", "If your quotes"),
               ("cta", "If your quotes", None)],
        layout={"9x16": dict(W=1080, H=1920, top=250, bottom=480, side=72, box=(0, 760, 1080, 833), zone=(430, 880)),
                "4x5": dict(W=1080, H=1350, top=56, bottom=110, side=64, box=(0, 517, 1080, 833), zone=(190, 655))},
        cta=("Quotes still going out as Word docs?", "DM me \u201cQUOTE\u201d", "I'll show you yours, rebuilt."),
        trim_lead=False),
}
REAL = "The real bid · Sept 23, 2026 · names blurred"
DEMO = "Demo of the fix · sample customer"


def card_img(kind, assets, k=1.0):
    """One proof card (RGBA): ink ground, gold rule, gold kicker, the proof, cream footnote. bjj_gjjw_v2's look."""
    pad, maxw = round(26 * k), round(936 * k)
    fk, fn = font("Bold", 32 * k), font("Regular", 21 * k)
    A = lambda f: os.path.join(assets, f)

    def frame(body, kicker, foot):
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        kl = wrap(tmp, kicker, fk, maxw - 2 * pad)
        w = max(body.width, max(tmp.textlength(l, font=fk) for l in kl), tmp.textlength(foot, font=fn) if foot else 0)
        w += 2 * pad
        h = pad + len(kl) * round(40 * k) + round(12 * k) + body.height + (round(40 * k) if foot else 0) + pad
        img = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=round(24 * k), fill=INK + (242,),
                            outline=GOLD + (255,), width=max(2, round(3 * k)))
        y = pad
        for l in kl:
            d.text((pad, y), l, font=fk, fill=GOLD + (255,)); y += round(40 * k)
        y += round(12 * k)
        img.alpha_composite(body, ((img.width - body.width) // 2, y)); y += body.height + round(14 * k)
        if foot:
            d.text((pad, y), foot, font=fn, fill=CREAM + (170,))
        return img

    def shot(path, keep=None, boxes=(), maxh=250, paper=False):
        im = Image.open(path).convert("RGBA")
        if keep: im = im.crop(keep)
        if paper:   # a scrap of the real document: white sheet, a little margin
            bg = Image.new("RGBA", (im.width + 40, im.height + 30), (255, 255, 255, 255)); bg.alpha_composite(im, (20, 15)); im = bg
            boxes = [(x0 + 20, y0 + 15, x1 + 20, y1 + 15) for x0, y0, x1, y1 in boxes]
        hd = ImageDraw.Draw(im)
        for bx in boxes:
            hd.rounded_rectangle(bx, radius=10, outline=GOLD, width=7)
        s = min((maxw - 2 * pad) / im.width, maxh * k / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, *im.size), radius=round(14 * k), fill=255)
        im.putalpha(Image.composite(im.getchannel("A"), m, m) if not paper else m)
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

    def phone(f, keep):   # the top of a demo phone screen, big enough to read
        return shot(A(f), keep=keep, maxh=310)

    if kind == "doc":
        return frame(shot(A("crop-01-header-date.png"), boxes=[(18, 338, 282, 402)], maxh=230, paper=True),
                     "5 days after the walk: a Word doc", REAL)
    if kind == "lump":
        return frame(shot(A("crop-02-lump-sum.png"), keep=(0, 0, 560, 82), boxes=[(16, 10, 300, 74)], maxh=120, paper=True),
                     "One price for the whole job. No options. No photos.", REAL)
    if kind == "quote":
        return frame(stat("$11,500", "to swap every outlet and switch in my house", 130), "The quote", REAL)
    if kind == "hbr":   # the stat Sammy reads, with its source on the card
        return frame(stat("7\u00d7", "more likely to reach the decision-maker when you reply within the hour, vs. an hour later", 150),
                     "Speed wins the conversation",
                     "Harvard Business Review, 2011 \u00b7 \u201cThe Short Life of Online Sales Leads\u201d")
    if kind == "count":
        return frame(stat("296", "outlets, switches and lights. One price."), "The scope",
                     "Counted from the bid's 19 line items")
    if kind == "gc":
        return frame(shot(A("crop-04-gc-boilerplate.png"), boxes=[(48, 150, 562, 206)], maxh=250, paper=True),
                     "“GC bid form.” There's no GC. It's a house.", REAL)
    if kind == "sign":
        return frame(shot(A("crop-05-sign-the-x.png"), boxes=[(10, 10, 606, 104), (212, 296, 532, 354)], maxh=250, paper=True),
                     "To say yes: print it, sign the X, send it back", "No e-sign. No deposit. 100% due on completion.")
    if kind == "invoice":
        page = shot(A("invoice.png"), boxes=[(966, 1486, 1288, 1542), (244, 798, 506, 846)], maxh=300, paper=True)
        fb, fl, fs = font("Bold", 96 * k), font("SemiBold", 34 * k), font("Regular", 26 * k)
        lines = [("$11,685", fb, GOLD, 104), ("Due on receipt.", fl, WHITE, 46), ("\u201cReference Proposal:\u201d", fl, WHITE, 42),
                 ("left blank.", fl, WHITE, 52), ("No pay link on it.", fs, CREAM, 34)]
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        tw = round(max(tmp.textlength(t, font=f) for t, f, _, _ in lines)); gap = round(32 * k)
        th = round(sum(h for *_, h in lines) * k)
        body = Image.new("RGBA", (page.width + gap + tw, max(page.height, th)), (0, 0, 0, 0))
        body.alpha_composite(page, (0, 0)); d = ImageDraw.Draw(body); y = (body.height - th) / 2 - 10 * k
        for t, f, c, h in lines:
            d.text((page.width + gap, y), t, font=f, fill=c + (255,)); y += h * k
        return frame(body, "Then the invoice: a generic Word template", "The real invoice #3721 \u00b7 Oct 23, 2026 \u00b7 names blurred")
    if kind == "rebuilt":   # the Word doc next to the same bid laid out on one page (rebuilt.png, Sept 30 2026)
        a = shot(A("wordp1.png"), keep=(0, 0, 1700, 1880), maxh=300, paper=True)
        b = shot(A("rebuilt.png"), keep=(0, 0, 1700, 1980), maxh=300, paper=True)
        fl = font("SemiBold", 24 * k); gap = round(70 * k); lh = round(34 * k)
        body = Image.new("RGBA", (a.width + gap + b.width, lh + max(a.height, b.height)), (0, 0, 0, 0))
        d = ImageDraw.Draw(body)
        d.text((0, 0), "Sent: Word doc, 2 pages", font=fl, fill=CREAM + (200,))
        d.text((a.width + gap, 0), "Same bid, rebuilt", font=fl, fill=GOLD + (255,))
        body.alpha_composite(a, (0, lh)); body.alpha_composite(b, (a.width + gap, lh))
        ax = a.width + gap // 2; ay = lh + max(a.height, b.height) // 2
        d.polygon([(ax - 16 * k, ay - 22 * k), (ax + 18 * k, ay), (ax - 16 * k, ay + 22 * k)], fill=GOLD + (255,))
        return frame(body, "Same bid. One clean page.", "Same $11,500 bid, rebuilt on one page by Sammy P \u00b7 names blurred")
    if kind == "link":
        return frame(phone("p-link.png", (40, 236, 616, 690)), "The fix: a link before you leave the driveway", DEMO)
    if kind == "options":
        return frame(phone("p-options.png", (24, 462, 656, 906)), "Three options, not one number", DEMO)
    if kind == "signed":
        return frame(phone("p-signed.png", (24, 256, 656, 500)), "They sign and pay the deposit on their phone", DEMO)
    if kind == "paybtn":
        return frame(phone("p-invoice.png", (24, 256, 656, 610)), "Job done: the invoice sends itself", DEMO)
    if kind == "review":
        return frame(phone("p-review.png", (24, 256, 656, 660)), "Paid. Then it asks for the review.", DEMO)
    if kind == "cta":
        fb, fs = font("Bold", 92 * k), font("SemiBold", 40 * k)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        kick, a, b = CTA
        w = round(max(tmp.textlength(a, font=fb), tmp.textlength(b, font=fs))); h = round(150 * k)
        body = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(body)
        d.text(((w - tmp.textlength(a, font=fb)) / 2, -6 * k), a, font=fb, fill=WHITE + (255,))
        d.text(((w - tmp.textlength(b, font=fs)) / 2, 100 * k), b, font=fs, fill=CREAM + (230,))
        return frame(body, kick, "Sammy P · panicciventures.com")
    raise KeyError(kind)


def header(lay, path):
    """Ink band, Panicci dot texture, the title, and a soft fade into the camera (bjj_gjjw_v2.header, new words)."""
    W, H = lay["W"], lay["H"]; by = lay["box"][1]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, by), fill=INK + (255,))
    for y in range(11, by, 22):
        for x in range(11, W, 22):
            d.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=(246, 241, 232, 18))
    for i in range(140):
        d.line((0, by + i, W, by + i), fill=INK + (round(235 * (1 - i / 140) ** 1.6),))
    k = 1.0 if H > 1500 else 0.8
    y = lay["top"] + 18 * k
    d.text((lay["side"], y), TITLE[0], font=font("Bold", 34 * k), fill=GOLD + (255,)); y += 48 * k
    size = 74 * k
    while d.textlength(TITLE[1], font=font("Bold", size)) > W - 2 * lay["side"] and size > 40 * k:
        size -= 2          # shrink to one line, so the cards below never meet a second title line
    d.text((lay["side"], y), TITLE[1], font=font("Bold", size), fill=WHITE + (255,))
    img.save(path); return path


def title_screen(lay, path):
    """The opening frame: a clean title screen, nothing else on it (no face, captions or cards). Ink ground, Panicci
    dot texture, the gold kicker and the title big and centred. The read's audio runs underneath it."""
    W, H, k = lay["W"], lay["H"], (1.0 if lay["H"] > 1500 else 0.8)
    img = Image.new("RGBA", (W, H), INK + (255,))
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(dots)
    for y in range(11, H, 22):
        for x in range(11, W, 22):
            dd.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=(246, 241, 232, 18))
    img.alpha_composite(dots); d = ImageDraw.Draw(img)   # blended, so the screen stays fully opaque
    fk, maxw = font("Bold", 46 * k), W - 2 * lay["side"] - 40
    size = 132 * k
    while True:          # two lines if it can stay big (no orphan word), else up to three
        ft = font("Bold", size); lines = wrap(d, TITLE[1], ft, maxw)
        if len(lines) <= 2 or (size < 96 * k and len(lines) <= 3) or size < 70 * k: break
        size -= 4
    lh, gap, rule = size * 1.08, 34 * k, 8 * k
    block = 46 * k + gap + rule + gap + len(lines) * lh
    y = (H - block) / 2 - 40 * k
    d.text(((W - d.textlength(TITLE[0], font=fk)) / 2, y), TITLE[0], font=fk, fill=GOLD + (255,)); y += 46 * k + gap
    d.rectangle((W / 2 - 60 * k, y, W / 2 + 60 * k, y + rule), fill=GOLD + (255,)); y += rule + gap
    for l in lines:
        d.text(((W - d.textlength(l, font=ft)) / 2, y), l, font=ft, fill=WHITE + (255,)); y += lh
    img.save(path); return path


def title_hold(caps, lo=1.2, hi=3.0):
    """How long the title screen holds: through the first spoken sentence, kept between lo and hi seconds."""
    for c in caps:
        if c["text"].rstrip().endswith((".", "?", "!")):
            return min(hi, max(lo, c["end"]))
    return lo


def split_captions(caps, maxw=4):
    """The Clipper's caption chunks run long; house style is at most four words on screen. Split each chunk at
    sentence ends first, then every four words, sharing its time by character count."""
    out = []
    for c in caps:
        words = c["text"].split(); groups, cur = [], []
        for w in words:
            cur.append(w)
            if w.endswith((".", "?", "!", "…", ",")) or len(cur) >= maxw:
                groups.append(cur); cur = []
        if cur: groups.append(cur)
        total = sum(len(" ".join(g)) for g in groups); t = c["start"]
        for g in groups:
            d = (c["end"] - c["start"]) * len(" ".join(g)) / total
            out.append({"start": round(t, 3), "end": round(t + d, 3), "text": " ".join(g)}); t += d
    for i in range(len(out) - 1):
        out[i]["end"] = max(out[i]["end"], out[i + 1]["start"] - 0.02)
    return out


def beat_times(caps, dur):
    """Each card's window from the caption it opens on to the caption it closes before (text match, not clock)."""
    def at(prefix):
        for c in caps:
            if prefix.lower() in c["text"].lower():
                i = c["text"].lower().index(prefix.lower())
                n = len(c["text"].split()); before = len(c["text"][:i].split())
                return c["start"] + (c["end"] - c["start"]) * before / max(1, n)
        raise ValueError(f"no caption contains {prefix!r}")
    return [(kind, at(a), (at(b) - 0.05) if b else dur - 0.05) for kind, a, b in BEATS]


def quiet_point(take, a, b):
    """The quietest 10 ms inside [a, b] of the take's audio, so a cut never clips a word."""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{max(0.02, b - a):.3f}", "-i", take,
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.float32)
    if len(x) < 320: return (a + b) / 2
    rms = np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, mode="valid"))[::160]
    return a + int(np.argmin(rms)) * 0.01 + 0.005


def drop_sentences(take, caps, dur):
    """Kept stretches of the take with the DROP sentences cut out at the quietest point either side, and the
    captions moved onto the new timeline."""
    keep, t = [], 0.0
    if TRIM_LEAD and caps and caps[0]["start"] > 0.6:
        t = quiet_point(take, max(0.0, caps[0]["start"] - 0.5), caps[0]["start"] - 0.05)
    for i, c in enumerate(caps):
        if any(c["text"].startswith(p) for p in DROP):
            prev_end = caps[i - 1]["end"] if i else 0.0
            nxt = caps[i + 1]["start"] if i + 1 < len(caps) else dur
            a = quiet_point(take, prev_end, c["start"]); b = quiet_point(take, c["end"], nxt)
            keep.append((t, a)); t = b
    keep.append((t, dur))
    segs = [(s, e, 0, True) for s, e in keep if e - s > 0.05]
    O, new_dur = timeline_any(segs)
    inside = lambda c: any(s - 1e-3 <= c["start"] and c["end"] <= e + 1e-3 for s, e, _, _ in segs)
    kept = [dict(c, start=O(c["start"]), end=O(c["end"])) for c in caps if inside(c)]
    return segs, kept, new_dur


def build(take, caps, assets, ratio, crop, outdir, tag="v1"):
    lay = LAYOUT[ratio]
    tmp = os.path.join(outdir, f".tmp_{ratio}"); os.makedirs(tmp, exist_ok=True)
    dur = float(os.popen(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{take}'").read().strip())
    segs, caps, dur = drop_sentences(take, caps, dur)
    base = cut(take, segs, [("all", 0, 0)], lay, crop, tmp, zoom=False)
    k = 1.0 if lay["H"] > 1500 else 0.74
    lines = split_captions(caps)
    T = title_hold(lines)          # the clean title screen runs 0..T; everything else starts after it
    ov = [(header(lay, f"{tmp}/header.png"), T, dur)]
    for kind, t0, t1 in beat_times(caps, dur):
        t0 = max(t0, T)
        if t1 <= t0: continue
        card = card_img(kind, assets, k); f = 1 / 30
        ov += [(place(card, lay, f"{tmp}/{kind}_p1.png", 0.86, 0.35), t0, t0 + f),
               (place(card, lay, f"{tmp}/{kind}_p2.png", 0.95, 0.8), t0 + f, t0 + 2 * f),
               (place(card, lay, f"{tmp}/{kind}.png"), t0 + 2 * f, t1)]
    for i, c in enumerate(lines):
        if c["end"] <= T + 0.1: continue
        p = f"{tmp}/cap{i:02d}.png"; caption_png(c["text"], lay, p); ov.append((p, max(c["start"], T), c["end"]))
    ov.append((title_screen(lay, f"{tmp}/title.png"), 0, T))
    out = os.path.join(outdir, f"panicci-{NAME}-{tag}_{ratio}.mp4")
    compose(base, dur, ov, out)
    print(f"{out}: {dur:.1f}s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", required=True); ap.add_argument("--captions", required=True)
    ap.add_argument("--assets", required=True); ap.add_argument("--out-dir", default="out")
    ap.add_argument("--crop9", required=True, help="X,Y,W,H camera window for 9:16")
    ap.add_argument("--crop45", required=True, help="X,Y,W,H camera window for 4:5")
    ap.add_argument("--ratios", default="9x16,4x5"); ap.add_argument("--tag", default="v1")
    ap.add_argument("--cards-only", action="store_true", help="write each card as a PNG and stop (no footage needed)")
    ap.add_argument("--cut", default="word-doc", choices=list(CUTS))
    a = ap.parse_args(); os.makedirs(a.out_dir, exist_ok=True)
    spec = CUTS[a.cut]
    NAME, TITLE, DROP, BEATS, LAYOUT, CTA, TRIM_LEAD = (spec["name"], spec["title"], spec["drop"], spec["beats"],
                                                       spec["layout"], spec["cta"], spec["trim_lead"])
    if a.cards_only:
        for r in a.ratios.split(","):
            title_screen(LAYOUT[r], os.path.join(a.out_dir, f"title-{r}.png"))
        for kind, *_ in BEATS:
            card_img(kind, a.assets).save(os.path.join(a.out_dir, f"card-{kind}.png"))
        raise SystemExit(0)
    caps = json.load(open(a.captions))
    crops = {"9x16": tuple(map(int, a.crop9.split(","))), "4x5": tuple(map(int, a.crop45.split(",")))}
    for r in a.ratios.split(","):
        build(a.take, caps, a.assets, r, crops[r], a.out_dir, a.tag)
