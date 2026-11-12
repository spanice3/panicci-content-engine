#!/usr/bin/env python3
"""Panicci talking-head pipeline: raw take(s) -> seamless, de-flubbed,
branded 9:16 + 1:1 (safe-zone) videos.

  python3 run.py TAKE.mp4 [TAKE2.mp4 ...] \
      --script script.txt --formats 9x16,1x1 --out-dir ./out

Steps: silence jump-cut each take (every cut waits for the last word to finish)
-> concat -> collapse repeated retakes (best-effort, printed for review)
-> captions (aligned to script if given) -> brand each format: face-centred
crop, captions kept off the face, animated open/close cards with the hook and a
play button, plus a cover still per format. Run video/setup.sh once first."""
import argparse, os, subprocess, sys
import json
import avcheck, cutlib, captions as capmod, brandkit, opener

def seamless_from(takes, out):
    parts = []
    for i, t in enumerate(takes):
        D, keep, nz = cutlib.silence_keepranges(t)
        kept = sum(e - s for s, e in keep)
        print(f"  {os.path.basename(t)}: {D:.1f}s -> {kept:.1f}s kept ({len(keep)} segs, thr {nz}dB)")
        p = out + f".part{i}.mp4"
        cutlib.render_segments(t, keep, p)
        parts.append(p)
    if len(parts) == 1:
        os.replace(parts[0], out)
    else:
        lst = out + ".concat.txt"
        open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
        subprocess.check_call(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
            "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("takes", nargs="+")
    ap.add_argument("--script", default=None, help="script .txt for exact caption wording")
    ap.add_argument("--meta", default=None, help="the take's Script data .json (optional 'cover' words for the cards)")
    ap.add_argument("--hook", default=None, help="override the big words on the open card")
    ap.add_argument("--no-cards", action="store_true", help="skip the open/close cards")
    ap.add_argument("--formats", default="9x16,1x1")
    ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--no-dedupe", action="store_true", help="skip retake collapse")
    ap.add_argument("--name", default="panicci-branded")
    ap.add_argument("--allow-frozen", action="store_true", help="cut a take even if its picture freezes before the sound ends")
    args = ap.parse_args()
    print("0) frozen-take check:")
    for t in args.takes:
        avcheck.require_ok(t, args.allow_frozen)
    os.makedirs(args.out_dir, exist_ok=True)
    seam = os.path.join(args.out_dir, "seamless.mp4")

    print("1) silence jump-cut:")
    seamless_from(args.takes, seam)

    words = None
    if not args.no_dedupe:
        print("2) scan for repeated retakes:")
        sents, words = capmod.transcribe(seam)          # one Whisper pass serves the retake scan and the captions
        spans = cutlib.find_retakes(sents)
        if spans:
            for s, e in spans:
                print(f"   cutting retake {s:.2f}-{e:.2f}s")
            cutlib.cut_out_spans(seam, spans, seam + ".clean.mp4")
            os.replace(seam + ".clean.mp4", seam)
            words = None                                # the audio changed: captions transcribe again
        else:
            print("   none detected")
    print(f"   seamless: {cutlib.dur(seam):.1f}s")

    print("3) captions:")
    script = open(args.script).read() if args.script else None
    caps_json = os.path.join(args.out_dir, "captions.json")
    caps = capmod.build_captions(seam, script=script, out_json=caps_json, words=words)
    print(f"   {len(caps)} lines ({'script-aligned' if script else 'ASR'})")

    print("4) brand:")
    meta = json.load(open(args.meta)) if args.meta else {}
    cover = dict((meta.get("readyScript") or {}).get("cover") or {}, **(meta.get("cover") or {}))
    if args.hook:
        cover["hook"] = args.hook
    texts = opener.texts_from(script, cover, caps)
    print(f"   cards: \"{texts['hook']}\" / \"{texts['close']}\"")
    outs = []
    for r in [x.strip() for x in args.formats.split(",") if x.strip()]:
        o = os.path.join(args.out_dir, f"{args.name}_{r}.mp4")
        brandkit.render(seam, caps_json, r, o, intro=not args.no_cards, outro=not args.no_cards, texts=texts)
        print(f"   {r} -> {o}  ({cutlib.dur(o):.1f}s)")
        outs.append(o)
    print("done:", ", ".join(outs))

if __name__ == "__main__":
    main()
