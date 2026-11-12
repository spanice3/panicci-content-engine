#!/usr/bin/env python3
"""Cutting helpers: silence jump-cut and best-effort retake collapse."""
import subprocess, re, difflib, os
import numpy as np

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

class Env:
    """10 ms RMS envelope of a clip's audio. Word edges come from the sound itself, not from Whisper's
    timestamps (which end early) or a loudness gate (which misses soft endings: "s", "f", a trailing vowel)."""
    HOP = 0.01

    def __init__(self, f):
        raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", f, "-ac", "1", "-ar", "16000",
                              "-f", "s16le", "-"], check=True, capture_output=True).stdout
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        n = len(x) // 160
        self.rms = np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) if n else np.zeros(1)
        room = float(np.percentile(self.rms, 12)) if n else 0.0          # room tone between lines
        speech = float(np.percentile(self.rms, 85)) if n else 1.0
        self.floor = max(0.004, room * 2.2, speech * 0.035)               # quieter than this = the word is over
        self.D = n * self.HOP

    def _i(self, t):
        return int(min(max(t, 0), self.D) / self.HOP)

    def land(self, t, cap=0.6, limit=None, quiet=0.06):
        """First moment at/after t where the sound stays under the floor for `quiet` s: where a word really ends."""
        lim = min(self.D, t + cap, limit if limit is not None else self.D)
        i, end, need, run = self._i(t), self._i(lim), max(1, round(quiet / self.HOP)), 0
        while i < end:
            run = run + 1 if self.rms[i] < self.floor else 0
            if run >= need:
                return (i - need + 1) * self.HOP
            i += 1
        return lim

    def rise(self, t, cap=0.25, limit=None, quiet=0.05):
        """Mirror of land(): walk back from t to where the word's soft onset starts."""
        lim = max(0.0, t - cap, limit if limit is not None else 0.0)
        i, end, need, run = self._i(t) - 1, self._i(lim), max(1, round(quiet / self.HOP)), 0
        while i >= end:
            run = run + 1 if self.rms[i] < self.floor else 0
            if run >= need:
                return (i + need) * self.HOP
            i -= 1
        return lim

    def quiet_point(self, t, back=0.25, fwd=0.25):
        """Quietest 30 ms around t: the safe place to splice."""
        a, b = self._i(t - back), self._i(t + fwd)
        if b - a < 3:
            return t
        sm = np.convolve(self.rms[a:b], np.ones(3) / 3, mode="same")
        return (a + int(np.argmin(sm))) * self.HOP


def silence_keepranges(f, keeppad=0.10, minsil=0.30, noise_db=None, env=None):
    """Keep everything that isn't dead air. Threshold auto-set ~12dB below the mean level unless noise_db is
    given. Every kept stretch then runs until its last word has actually finished (Env.land) and starts where
    its first word really begins (Env.rise), so a cut never clips a word."""
    D = dur(f)
    if noise_db is None:
        noise_db = round(mean_volume(f) - 12)
    env = env or Env(f)
    cuts = []
    for s, e in detect_silences(f, noise_db, minsil):
        s2, e2 = max(0.0, s + keeppad), min(D, e - keeppad)
        if e2 - s2 > 0.05:
            cuts.append((s2, e2, s, e))
    keep, cur = [], 0.0
    for s2, e2, s, e in cuts:
        if s2 > cur:
            keep.append([cur, s2, s, e])
        cur = max(cur, e2)
    if cur < D:
        keep.append([cur, D, D, D])
    for i, k in enumerate(keep):
        nxt = keep[i + 1][0] if i + 1 < len(keep) else D
        if k[1] < D:                                      # tail: let the word land, then breathe 60 ms
            k[1] = min(max(k[1], env.land(k[2], cap=0.7, limit=k[3]) + 0.06), nxt - 0.02, D)
        if k[0] > 0:                                      # onset: catch a soft first sound
            prev = keep[i - 1][1] if i else 0.0
            k[0] = max(min(k[0], env.rise(k[0] + keeppad, cap=0.25) - 0.03), prev + 0.02, 0.0)
    return D, [(s, e) for s, e, *_ in keep if e - s > 0.12], noise_db

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

def cut_out_spans(src, spans, out, fade=0.010, env=None):
    """Remove the given [start,end] spans from src, keep the rest. Whisper's span edges are rough, so each
    edge moves to the quietest point nearby: the line before keeps its last word whole."""
    D = dur(src)
    env = env or Env(src)
    spans = sorted((env.quiet_point(s, 0.30, 0.12), env.quiet_point(e, 0.10, 0.30)) for s, e in spans)
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
