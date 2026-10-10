#!/usr/bin/env python3
"""Hormozi 50-5-3 ad builder: one 50-5-3 shoot take -> cut hook / meat / CTA
modules -> stitched ad combos, named H07-M2-C1 to match the ad manifest.

  python3 adbuild.py TAKE.mp4 --meta TAKE.json [--render test|all|clips] \
      [--brand 9x16,1x1] [--out-dir ./ads]

TAKE.json is the studio's "Script data (.json)" download for that take. If it
already has an adMatrix (you hit Find hooks / meats / CTAs in the browser),
that's used. If not, the take is transcribed with Whisper and sent to the
studio's /api/fifty-five-three identify endpoint (same prompt the browser uses).

Either way every cut is snapped to Whisper word timestamps, so module edges
land on real word boundaries, not the browser's approximate speech timings.

--render test  (default) Round 1 hook test: every hook x top meat x top CTA
--render all   every combo (50 x 5 x 3 = 750 files; you probably don't want this)
--render clips just the modules, no combos
--brand        also burn captions + logo bug + lower third per ratio
               (no intro card: an ad has to open on the hook)
"""
import argparse, csv, difflib, json, os, re, subprocess, sys, urllib.request
import cutlib

API = "https://studio.panicciventures.com/api/fifty-five-three"


def norm(s):
    return re.sub(r"[^a-z0-9']", "", s.lower())


def toks(s):
    return [t for t in (norm(x) for x in s.split()) if t]


def find_span(words, quote, lo, hi, anchor="both"):
    """Best fuzzy match of quote's words inside words[] whose start is in [lo, hi].
    Returns (start_time, end_time, ratio) or None."""
    q = toks(quote)
    idx = [i for i, w in enumerate(words) if lo <= w[0] <= hi]
    if not q or not idx:
        return None
    seq = [norm(words[i][2]) for i in idx]
    n = len(q)
    best = None
    for a in range(len(seq)):
        win = seq[a:a + n]
        r = difflib.SequenceMatcher(a=q, b=win, autojunk=False).ratio()
        if best is None or r > best[0]:
            best = (r, a, min(a + n, len(seq)) - 1)
    r, a, b = best
    if r < 0.45:
        return None
    return words[idx[a]][0], words[idx[b]][1], r


def seg_window(meta, n):
    for s in meta.get("segments", []):
        if s["n"] == n:
            return s["start"], s["end"]
    return None


def identify(meta, words, api):
    segs = []
    for s in meta.get("segments", []):
        text = " ".join(w[2] for w in words if s["start"] - 0.3 <= w[0] < s["end"]).strip()
        segs.append({"n": s["n"], "type": s["type"], "prompt": s.get("question", ""),
                     "start": s["start"], "end": s["end"], "transcript": text})
    req = urllib.request.Request(api, data=json.dumps({"action": "identify", "segments": segs}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    pad = lambda i: str(i).zfill(2)
    return {
        "method": "hormozi-50-5-3", "model": data.get("model"),
        "hooks": [dict(h, id="H" + pad(i + 1), on=True) for i, h in enumerate(data.get("hooks", []))],
        "meats": [dict(m, id="M%d" % (i + 1), on=True) for i, m in enumerate(data.get("meats", []))],
        "ctas": [dict(c, id="C%d" % (i + 1), on=True) for i, c in enumerate(data.get("ctas", []))],
        "reshoot": data.get("reshoot", []),
    }


def snap(item, kind, meta, words):
    """Set item['in'], item['out'] from Whisper words. Falls back to the
    browser's approximate start/end, then the whole segment."""
    win = seg_window(meta, item["seg"]) or (item.get("start", 0), item.get("end", 0))
    lo, hi = win[0] - 1.0, win[1] + 0.5
    if kind == "meats":
        a = find_span(words, item["startQuote"], lo, hi)
        b = find_span(words, item["endQuote"], a[0] if a else lo, hi)
        s, e = (a[0] if a else item.get("start", win[0])), (b[1] if b else item.get("end", win[1]))
        how = "whisper" if a and b else "approx"
    else:
        m = find_span(words, item["text"], lo, hi)
        s, e = (m[0], m[1]) if m else (item.get("start", win[0]), item.get("end", win[1]))
        how = "whisper" if m else "approx"
    item["in"], item["out"], item["timing"] = round(max(0, s - 0.08), 2), round(e + 0.18, 2), how
    return item


def cut_module(src, item, out):
    """Trim [in, out], then tighten dead air inside it (keeps natural pauses short)."""
    raw = out + ".raw.mp4"
    cutlib.render_segments(src, [(item["in"], item["out"])], raw)
    _, keep, _ = cutlib.silence_keepranges(raw, keeppad=0.12, minsil=0.45)
    if keep:
        cutlib.render_segments(raw, keep, out)
        os.remove(raw)
    else:
        os.replace(raw, out)
    return out


def concat(parts, out):
    lst = out + ".txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                           "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
    os.remove(lst)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("take")
    ap.add_argument("--meta", required=True, help="the take's Script data .json (or a session .json + --take)")
    ap.add_argument("--take-index", type=int, default=None, help="1-based take number when --meta is a session json")
    ap.add_argument("--matrix", default=None, help="ad-matrix .json (defaults to meta.adMatrix)")
    ap.add_argument("--render", choices=["test", "all", "clips"], default="test")
    ap.add_argument("--brand", default="", help="e.g. 9x16,1x1 (captions + bug + lower third)")
    ap.add_argument("--api", default=API)
    ap.add_argument("--out-dir", default="./ads")
    a = ap.parse_args()

    meta = json.load(open(a.meta))
    if "takes" in meta:
        meta = meta["takes"][(a.take_index or 1) - 1]
    if not meta.get("segments"):
        sys.exit("No segments in that json. Record in the studio's 50-5-3 tab so every hook/meat/CTA is a segment.")
    os.makedirs(a.out_dir, exist_ok=True)
    mods = os.path.join(a.out_dir, "modules")
    os.makedirs(mods, exist_ok=True)

    import captions as capmod  # heavy import (faster-whisper) only once we know we need it
    print("1) transcribing take (Whisper word timestamps)...")
    words = capmod.asr_words(a.take)
    print(f"   {len(words)} words")

    mx = json.load(open(a.matrix)) if a.matrix else meta.get("adMatrix")
    if not mx:
        print("2) no adMatrix in the json, asking the studio to identify hooks / meats / CTAs...")
        mx = identify(meta, words, a.api)
    else:
        print("2) using the adMatrix picked in the studio")

    H = [h for h in mx["hooks"] if h.get("on", True)]
    M = [m for m in mx["meats"] if m.get("on", True)]
    C = [c for c in mx["ctas"] if c.get("on", True)]
    if not (H and M and C):
        sys.exit(f"Need at least one of each. Got {len(H)} hooks, {len(M)} meats, {len(C)} CTAs.")
    print(f"   {len(H)} hooks x {len(M)} meats x {len(C)} CTAs = {len(H) * len(M) * len(C)} combos")
    for r in mx.get("reshoot", []):
        print(f"   reshoot seg {r['seg']}: {r.get('reason', '')}")

    print("3) snapping cuts + cutting modules:")
    files = {}
    for kind, lst in (("hooks", H), ("meats", M), ("ctas", C)):
        for it in lst:
            snap(it, kind, meta, words)
            f = os.path.join(mods, f"{it['id']}.mp4")
            cut_module(a.take, it, f)
            files[it["id"]] = f
            label = it.get("title") or it.get("text", "")
            print(f"   {it['id']:>4} {it['in']:7.2f}-{it['out']:7.2f}s [{it['timing']}] {label[:60]}")
    json.dump(mx, open(os.path.join(a.out_dir, "ad-matrix.snapped.json"), "w"), indent=2)

    if a.render == "clips":
        print("done: modules in", mods)
        return
    if a.render == "test":
        combos = [(h, M[0], C[0]) for h in H]
    else:
        combos = [(h, m, c) for h in H for m in M for c in C]
    print(f"4) stitching {len(combos)} ads ({'Round 1 hook test' if a.render == 'test' else 'every combo'}):")
    ratios = [r.strip() for r in a.brand.split(",") if r.strip()]
    if ratios:
        import brandkit
    rows = []
    for h, m, c in combos:
        name = f"{h['id']}-{m['id']}-{c['id']}"
        out = concat([files[h["id"]], files[m["id"]], files[c["id"]]], os.path.join(a.out_dir, name + ".mp4"))
        outs = [out]
        if ratios:
            cj = os.path.join(a.out_dir, name + ".captions.json")
            capmod.build_captions(out, out_json=cj)
            for r in ratios:
                o = os.path.join(a.out_dir, f"{name}_{r}.mp4")
                brandkit.render(out, cj, r, o, intro=False, outro=False)
                outs.append(o)
        rows.append({"ad_name": f"553 {name}", "file": os.path.basename(outs[-1]),
                     "seconds": round(cutlib.dur(out), 1), "hook": h["text"], "meat": m.get("title", ""), "cta": c["text"]})
        print(f"   {name}  {rows[-1]['seconds']}s")
    with open(os.path.join(a.out_dir, "manifest.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("done:", a.out_dir, "(name each ad in Meta exactly as ad_name in manifest.csv)")


if __name__ == "__main__":
    main()
