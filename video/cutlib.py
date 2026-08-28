#!/usr/bin/env python3
"""Cutting helpers: silence jump-cut and best-effort retake collapse."""
import subprocess, re, difflib, os

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
       "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "1",
       "-video_track_timescale", "30000", "-movflags", "+faststart"]

def dur(f):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", f]).decode())

def mean_volume(f):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af",
        "volumedetect", "-f", "null", "-"], stderr=subprocess.PIPE).stderr.decode()
    m = re.search(r"mean_volume:\s*(-?[\d.]+)", out)
    return float(m.group(1)) if m else -25.0

def detect_silences(f, noise_db, minsil=0.30):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af",
        f"silencedetect=noise={noise_db}dB:d={minsil}", "-f", "null", "-"],
        stderr=subprocess.PIPE).stderr.decode()
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))

def silence_keepranges(f, keeppad=0.10, minsil=0.30, noise_db=None):
    """Keep everything that isn't dead air. Threshold auto-set ~12dB below the
    mean level unless noise_db is given."""
    D = dur(f)
    if noise_db is None:
        noise_db = round(mean_volume(f) - 12)
    cuts = []
    for s, e in detect_silences(f, noise_db, minsil):
        s2, e2 = max(0.0, s + keeppad), min(D, e - keeppad)
        if e2 - s2 > 0.05:
            cuts.append((s2, e2))
    keep, cur = [], 0.0
    for s, e in cuts:
        if s > cur:
            keep.append((cur, s))
        cur = max(cur, e)
    if cur < D:
        keep.append((cur, D))
    return D, [(s, e) for s, e in keep if e - s > 0.12], noise_db

def render_segments(src, keep, out, fade=0.010):
    """Frame-accurate trim+concat of keep ranges into one continuous clip."""
    fc = []
    for i, (s, e) in enumerate(keep):
        L = e - s
        fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS,fps=30,setsar=1[v{i}];")
        fc.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0,L-fade):.3f}:d={fade}[a{i}];")
    n = len(keep)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
        "-filter_complex", "".join(fc), "-map", "[v]", "-map", "[a]", *ENC, out])
    return out

def cut_out_spans(src, spans, out, fade=0.010):
    """Remove the given [start,end] spans from src, keep the rest."""
    D = dur(src)
    spans = sorted(spans)
    keep, cur = [], 0.0
    for s, e in spans:
        if s > cur:
            keep.append((cur, s))
        cur = max(cur, e)
    if cur < D:
        keep.append((cur, D))
    return render_segments(src, keep, out, fade)

def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

def find_retakes(asr_sentences, sim=0.72, window=5):
    """Given [(start,end,text)], return time spans of earlier attempts that are
    near-duplicated by a LATER sentence (i.e. the speaker restarted the line).
    Best-effort: returns spans to cut, keeping the last clean pass."""
    spans = []
    n = len(asr_sentences)
    for i in range(n):
        ni = _norm(asr_sentences[i][2])
        if len(ni.split()) < 3:
            continue
        for j in range(i + 1, min(i + 1 + window, n)):
            nj = _norm(asr_sentences[j][2])
            r = difflib.SequenceMatcher(a=ni, b=nj).ratio()
            # earlier sentence is subsumed by / very similar to a later one
            if r >= sim or (len(ni) > 8 and ni in nj):
                spans.append((asr_sentences[i][0], asr_sentences[i][1]))
                break
    # merge overlapping/adjacent spans
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1] + 0.4:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged
