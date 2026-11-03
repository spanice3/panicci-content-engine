#!/usr/bin/env python3
"""Frozen-take check: does the picture run as long as the sound?

  python3 avcheck.py TAKE.mp4 [MORE ...]    # one line per take; exit 1 if any take is frozen

On 2026-11-03 every iPhone (Safari) studio take froze 11-20 s in while the audio ran the full length: the
MP4 holds one video sample stretched over the rest of the take. Cutting one of those ships a still frame with
a voice over it, so run.py and adbuild.py call require_ok() first and refuse a frozen take (--allow-frozen
overrides, for a human who wants the audio anyway; the Clipper Agent never passes it). The studio runs the
same check in the browser before Send to Clipper (recordingHealth in the take's .json); this one is the
backstop on the agent side.
"""
import json, subprocess, sys

GAP_SEC = 1.5     # a hole this long between video frames = frozen picture
SHORT_SEC = 1.5   # video ending this much before the audio = frozen picture


def _packets(path, sel):
    """[(pts_sec, duration_sec)] for the first stream matching sel ('v:0' / 'a:0'), in presentation order."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", sel, "-show_entries",
         "packet=pts_time,dts_time,duration_time", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    pk = []
    for p in json.loads(out or "{}").get("packets", []):
        t = p.get("pts_time", p.get("dts_time"))
        if t in (None, "N/A"):
            continue
        d = p.get("duration_time")
        pk.append((float(t), float(d) if d not in (None, "N/A") else 0.0))
    pk.sort()
    return pk


def fmt(sec):
    sec = max(0, int(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"


def check(path):
    v, a = _packets(path, "v:0"), _packets(path, "a:0")
    audio = round(a[-1][0] + a[-1][1] - a[0][0], 2) if a else None
    if not v:
        return {"ok": False, "verdict": "no-video", "froze_at": 0.0, "frozen_for": None,
                "video": 0.0, "audio": audio, "frames": 0}
    v0 = v[0][0]
    froze_at = frozen_for = None
    for i, (t, d) in enumerate(v):
        hole = (v[i + 1][0] - t) if i + 1 < len(v) else d   # last frame: its own (possibly stretched) duration
        if hole > GAP_SEC:
            froze_at, frozen_for = round(t - v0, 2), round(hole, 2)
            break
    last_t, last_d = v[-1]
    video = round(last_t - v0 + (last_d if last_d <= GAP_SEC else 0), 2)
    r = {"ok": True, "verdict": "ok", "froze_at": None, "frozen_for": None,
         "video": video, "audio": audio, "frames": len(v)}
    if froze_at is not None:
        r.update(ok=False, verdict="video-froze", froze_at=froze_at, frozen_for=frozen_for)
    elif audio is not None and audio - video > SHORT_SEC:
        r.update(ok=False, verdict="video-ends-early", froze_at=video)
    return r


def describe(r):
    if r["ok"]:
        return f"ok: picture and sound both run {fmt(r['video'])}"
    if r["verdict"] == "no-video":
        return "FROZEN: no picture in this take"
    return f"FROZEN: picture freezes at {fmt(r['froze_at'])} while the sound runs to {fmt(r['audio'])}"


def require_ok(path, allow=False):
    """Print the check; exit with a one-line reason if the take is frozen (unless allow)."""
    r = check(path)
    print(f"   av check: {describe(r)}")
    if not r["ok"] and not allow:
        # No override hint here on purpose: an agent reading this line should report it, not force the cut.
        sys.exit(f"Frozen take, not cutting it: {describe(r)[8:]}. Re-record this take in the studio.")
    return r


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bad = 0
    for f in sys.argv[1:]:
        try:
            r = check(f)
        except subprocess.CalledProcessError as e:
            print(f"{f}: UNREADABLE ({(e.stderr or '').strip()[:120]})")
            bad += 1
            continue
        print(f"{f}: {describe(r)}")
        bad += not r["ok"]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
