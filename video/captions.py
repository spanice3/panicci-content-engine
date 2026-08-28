#!/usr/bin/env python3
"""Caption building. Transcribes the seamless clip and, when a script is given,
aligns caption TEXT to the script (so brand terms and wording are exact) while
taking timing from the audio. Falls back to raw ASR text when no script."""
import re, json, difflib, subprocess, os, tempfile
from faster_whisper import WhisperModel

_MODEL = None
def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = WhisperModel("small", device="cpu", compute_type="int8")
    return _MODEL

def _wav(mp4):
    w = tempfile.mktemp(suffix=".wav")
    subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", mp4, "-ac", "1", "-ar", "16000", w])
    return w

def _norm(x):
    return re.sub(r"[^a-z0-9]", "", x.lower())

def asr_words(mp4):
    segs, _ = _model().transcribe(_wav(mp4), vad_filter=True, word_timestamps=True)
    W = []
    for s in segs:
        for w in (s.words or []):
            W.append((w.start, w.end, w.word.strip()))
    return W

def asr_sentences(mp4):
    segs, _ = _model().transcribe(_wav(mp4), vad_filter=True)
    return [(s.start, s.end, s.text.strip()) for s in segs]

def _chunks_from_script(script, W):
    toks = []
    for raw in re.findall(r"\S+", script):
        toks.append({"disp": raw, "n": _norm(raw),
                     "hard": bool(re.search(r"[.!?]$", raw))})
    sn = [t["n"] for t in toks]
    an = [_norm(w[2]) for w in W]
    sm = difflib.SequenceMatcher(a=sn, b=an, autojunk=False)
    for t in toks:
        t["t"] = None
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for kk in range(i2 - i1):
                toks[i1 + kk]["t"] = W[j1 + kk][0]
        elif tag == "replace":
            span = W[j1:j2]
            for k in range(i1, i2):
                if span:
                    idx = min(len(span) - 1, int((k - i1) / max(1, i2 - i1) * len(span)))
                    toks[k]["t"] = span[idx][0]
    last = 0.0
    for i, t in enumerate(toks):
        if t["t"] is None:
            nxt = next((toks[j]["t"] for j in range(i + 1, len(toks)) if toks[j]["t"] is not None), None)
            t["t"] = last if nxt is None else (last + nxt) / 2
        last = t["t"]
    for i in range(1, len(toks)):
        if toks[i]["t"] < toks[i - 1]["t"]:
            toks[i]["t"] = toks[i - 1]["t"]
    caps, cur = [], []
    def flush():
        if not cur:
            return
        s = cur[0]["t"]; e = max(cur[-1]["t"] + 0.5, s + 0.5)
        txt = re.sub(r"\s+([,.!?])", r"\1", " ".join(x["disp"] for x in cur))
        caps.append({"start": round(s, 2), "end": round(e, 2), "text": txt})
    for t in toks:
        cur.append(t)
        if t["hard"] or len(cur) >= 4 or (cur[-1]["t"] - cur[0]["t"]) >= 1.8:
            flush(); cur = []
    flush()
    return caps

def _chunks_from_asr(W):
    caps, cur = [], []
    def flush():
        if cur:
            caps.append({"start": round(cur[0][0], 2),
                         "end": round(max(cur[-1][1], cur[0][0] + 0.5), 2),
                         "text": re.sub(r"\s+([,.!?])", r"\1", " ".join(x[2] for x in cur))})
    for w in W:
        cur.append(w)
        if w[2].endswith((".", "!", "?", ",")) or len(cur) >= 4 or (cur[-1][1] - cur[0][0]) >= 1.8:
            flush(); cur = []
    flush()
    return caps

def _postprocess(caps):
    # clamp ends to next start; merge sub-0.7s lines into the previous
    for i in range(len(caps) - 1):
        if caps[i + 1]["start"] > caps[i]["start"]:
            caps[i]["end"] = round(min(caps[i]["end"], caps[i + 1]["start"] - 0.02), 2)
        if caps[i]["end"] <= caps[i]["start"]:
            caps[i]["end"] = round(caps[i]["start"] + 0.4, 2)
    out = []
    for c in caps:
        if out and (c["end"] - c["start"] < 0.7):
            out[-1]["text"] = re.sub(r"\s+([,.!?])", r"\1", (out[-1]["text"] + " " + c["text"]).strip())
            out[-1]["end"] = c["end"]
        else:
            out.append(dict(c))
    return out

def build_captions(mp4, script=None, out_json=None):
    W = asr_words(mp4)
    caps = _chunks_from_script(script, W) if script else _chunks_from_asr(W)
    caps = _postprocess(caps)
    if out_json:
        json.dump(caps, open(out_json, "w"), indent=1)
    return caps
